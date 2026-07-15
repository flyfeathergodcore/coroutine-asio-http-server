"""
统一日志配置模块。

初始化后所有模块的 logger 自动输出到 stderr，同时 FastMCP 会捕获
日志记录并转发到 MCP 客户端显示。

用法:
    # 在 server.py 入口调用一次
    from depend.log_config import setup_logging
    setup_logging()

    # 各模块直接使用标准 logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info("工具调用成功")
    logger.error("工具调用失败: %s", err)
"""

import logging
import sys

_initialized = False


def setup_logging(level: int = logging.INFO) -> None:
    """
    配置全局日志格式和级别。

    只会生效一次（后续重复调用无副作用）。

    Args:
        level: 日志级别，默认 INFO
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    # 避免重复添加
    if not root.handlers:
        root.addHandler(handler)
    else:
        root.handlers[0].setFormatter(fmt)
