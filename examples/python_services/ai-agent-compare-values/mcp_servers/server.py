import logging
import importlib
import pkgutil
import contextvars
from pathlib import Path
from depend.log_config import setup_logging
from depend.auth import set_role
from typing import Any

logger = logging.getLogger(__name__)

# 当前请求的角色（contextvars → 每个 asyncio 任务独立）
_current_role: contextvars.ContextVar[str | None] = contextvars.ContextVar('current_role', default=None)


# ============ 带权限的 FastMCP 子类 ============

from mcp.server.fastmcp import FastMCP as BaseFastMCP


class AuthFastMCP(BaseFastMCP):
    """
    带权限检查的 FastMCP。
    通过 Starlette 中间件 + contextvars 传递角色身份。
    """

    def sse_app(self, mount_path=None):
        """在 SSE app 上挂载纯 ASGI 中间件（不破坏 SSE 流）"""
        app = super().sse_app(mount_path)
        inner = app  # Starlette ASGI app

        # 纯 ASGI 包装层：不解析响应体，只读请求 header
        async def role_middleware(scope, receive, send):
            if scope["type"] == "http":
                headers = dict(scope.get("headers", []))
                role = None
                for k, v in headers.items():
                    if isinstance(k, bytes) and k.lower() == b"x-agent-role":
                        role = v.decode()
                        break
                _current_role.set(role)
            await inner(scope, receive, send)

        return role_middleware

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        """调用工具前校验角色权限"""
        role = _current_role.get()
        set_role(role)
        logger.info("工具调用: %s, 角色: %s", name, role)
        return await super().call_tool(name, arguments)

    async def list_tools(self):
        """按角色过滤可见工具列表"""
        role = _current_role.get()
        from depend.auth import list_protected_tools
        permissions = list_protected_tools()

        all_tools = await super().list_tools()
        filtered = []
        for t in all_tools:
            allowed_roles = permissions.get(t.name)
            if allowed_roles is None or (role and role in allowed_roles):
                filtered.append(t)
        logger.debug("工具列表: %s 可见 %d/%d 个", role or "无角色", len(filtered), len(all_tools))
        return filtered


# ============ MCP 服务器类 ============

class MCPServer:
    """基于 AuthFastMCP 的 MCP 服务器，支持工具权限隔离。"""

    def __init__(self, port: int = 8888, host: str = '0.0.0.0',
                 tool_path: str = None, config_path: str = None):
        self.server = AuthFastMCP(host=host, port=port)
        self.port = port
        self.host = host
        self.config_path = config_path
        if tool_path is None:
            self.tool_path = Path(__file__).parent / "skills"
        else:
            self.tool_path = Path(tool_path)
        self.running = False

    def find_tools(self) -> None:
        """自动发现工具模块并加载。"""
        if self.tool_path.is_file() and self.tool_path.suffix == '.py':
            module_name = self.tool_path.stem
            try:
                spec = importlib.util.spec_from_file_location(module_name, self.tool_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    logger.info("已加载工具模块: %s", module_name)
                    if hasattr(module, 'register_skill'):
                        module.register_skill(self.server)
                        logger.info("  已注册技能: %s", module_name)
            except Exception as e:
                logger.error("加载模块 %s 失败: %s", module_name, e)
            return

        if self.tool_path.is_dir():
            init_file = self.tool_path / "__init__.py"
            if init_file.exists():
                package_name = self.tool_path.name
                try:
                    package = importlib.import_module(package_name)
                    for module_info in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
                        if module_info.name.endswith(".__init__"):
                            continue
                        try:
                            module = importlib.import_module(module_info.name)
                            logger.info("已加载工具模块: %s", module_info.name)
                            if hasattr(module, 'register_skill'):
                                module.register_skill(self.server)
                                logger.info("  已注册技能: %s", module_info.name)
                        except Exception as e:
                            logger.error("加载模块 %s 失败: %s", module_info.name, e)
                except ImportError as e:
                    logger.warning("无法导入包 '%s'，改用文件扫描: %s", package_name, e)
                    self._scan_directory()
            else:
                self._scan_directory()
            return
        logger.warning("工具路径无效: %s", self.tool_path)

    def _scan_directory(self):
        for py_file in self.tool_path.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            module_name = py_file.stem
            try:
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    logger.info("已加载工具模块: %s", module_name)
                    if hasattr(module, 'register_skill'):
                        module.register_skill(self.server)
                        logger.info("  已注册技能: %s", module_name)
            except Exception as e:
                logger.error("加载模块 %s 失败: %s", module_name, e)

    def start(self):
        self.running = True
        logger.info("正在启动 MCP 服务器...")
        self.find_tools()

        from depend.auth import list_protected_tools
        protected = list_protected_tools()
        if protected:
            logger.info("工具权限配置: %s", protected)

        self.server.run(transport="sse")


# ============ Agent 初始化（替代已弃用的 mcp_setup） ============

def init_agents(config: dict[str, Any] | None = None):
    """
    初始化 Agent 运行所需的所有组件。

    替代已弃用的 mcp_setup.create_mcp_services / create_session_factory。

    Returns:
        (llm, guide_mcp, product_mcp, sessions, get_or_create_session)
    """
    from core.config import load_config
    from core.llm_client import LLMClient
    from .client import MCPClient
    from core.guide_agent import ShoppingGuideAgent
    from core.product_agent import ProductAgent

    cfg = config or load_config()
    llm_cfg = cfg.get("llm", {})
    llm = LLMClient(
        api_key=llm_cfg.get("api_key", "ollama"),
        base_url=llm_cfg.get("base_url", "http://localhost:11434/v1"),
        model=llm_cfg.get("model", "llama3:8b"),
        timeout=llm_cfg.get("timeout", 60),
        temperature=llm_cfg.get("temperature", 0.3),
        max_tokens=llm_cfg.get("max_tokens", 2048),
    )
    guide_mcp = MCPClient(role="guide_agent")
    product_mcp = MCPClient(role="product_agent")

    sessions: dict[str, dict] = {}

    def get_or_create_session(sid: str) -> dict:
        if sid not in sessions:
            sessions[sid] = {
                "guide": ShoppingGuideAgent(llm=llm, config=cfg),
                "product": ProductAgent(llm=llm, mcp=product_mcp, config=cfg),
                "stage": "guide",
                "product_history": [],
                "last_action": "",
            }
        return sessions[sid]

    return llm, guide_mcp, product_mcp, sessions, get_or_create_session


# ============ 入口点 ============

if __name__ == "__main__":
    setup_logging()
    server = MCPServer(port=8888, host="0.0.0.0")
    server.start()
