"""
导购Agent 加载测试 — 展示 skill_context 注入 L1 prompt 后的完整效果

真实 MCP：通过 create_mcp_services 启动完整服务栈。
"""

import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("CONFIG_PATH", os.path.join(_PROJECT_ROOT, "config.yaml"))
sys.path.insert(0, _PROJECT_ROOT)

from mcp_servers.mcp_setup import create_mcp_services
from core.guide_agent import ShoppingGuideAgent
from core.config import load_config

cfg = load_config()
guide_mcp, product_mcp, llm = create_mcp_services(cfg)

agent = ShoppingGuideAgent(llm=llm, mcp=guide_mcp, config=cfg)
agent.start_session("test_demo")

# ── 1. 展示 skill_context ──
print("=" * 60)
print("  1. skill_context（从真实 MCP 加载）")
print("=" * 60)
try:
    sc = json.loads(agent._skill_context) if isinstance(agent._skill_context, str) else agent._skill_context
    print(json.dumps(sc, ensure_ascii=False, indent=2))
except Exception:
    print(agent._skill_context[:500] if agent._skill_context else "(空)")

# ── 2. 展示格式化后的 L1 prompt ──
print()
print("=" * 60)
print("  2. 注入后的完整 L1 Prompt")
print("=" * 60)
print()

formatted = agent._l1_prompt.format(
    user_summary=agent._user_summary or "（无）",
    skills_context=agent._skill_context,
    product_prompt=agent._product_prompt or "",
    tool_call_content=str(agent._tool_call_content),
    session_dialogues="[user]: 想买一台笔记本，预算8000左右",
    previous_analyses=str(agent._previous_analyses),
)

print(formatted)
