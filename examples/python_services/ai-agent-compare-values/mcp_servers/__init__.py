"""
MCP Server & Client 模块

当前结构 (2026-07):
  server.py          — MCPServer 主入口
  client.py          — MCPClient (SSE 客户端，工具发现与调用)
  depend/            — 可复用工具模块
    db.py            — 数据库连接与配置加载
    manmanbuy_price.py — 慢慢买比价爬虫
  skills/            — agent skill 工具注册
    guide.py         — 导购技能 (会话管理/用户画像)
    product.py       — 商品技能 (京东搜索/比价)
"""

from .client import MCPClient

__all__ = ["MCPClient"]
