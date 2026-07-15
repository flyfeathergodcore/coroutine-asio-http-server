"""
MCP 权限隔离测试脚本。

通过 X-Agent-Role header 传递角色身份。
测试可见性过滤 + 调用时权限检查。
"""

import asyncio, sys
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from mcp.types import TextContent


GUIDE = ["find_product_prompt", "load_session", "save_session", "load_user_profile"]
PRODUCT = ["search_category", "find_price"]
ALL = GUIDE + PRODUCT
PASS = "✅"
FAIL = "❌"


ARGS = {
    "find_product_prompt": {"product": "手机"},
    "load_session": {"session_id": "t"},
    "save_session": {"session_id": "t", "role": "user", "dialogues": "h"},
    "load_user_profile": {"user_id": "t"},
    "search_category": {"keyword": "测试", "price_min": 1000, "price_max": 2000},
    "find_price": {"products": ["测试手机"]},
}


async def _inner(url: str, headers: dict | None, expect: list[str]):
    """连接、初始化、测试逻辑——发生异常直接抛"""
    async with sse_client(url, headers=headers) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            result = await s.list_tools()
            names = [t.name for t in result.tools]

            visible_set = set(names)
            hidden = set(ALL) - set(expect)

            results = {}
            for tool in expect:
                if tool in visible_set:
                    r2 = await s.call_tool(tool, ARGS[tool])
                    text = " ".join(c.text for c in r2.content if isinstance(c, TextContent))
                    denied = "权限拒绝" in text
                    results[tool] = ("visible_denied" if denied else "ok")
                else:
                    results[tool] = ("hidden" if tool not in visible_set else "visible")
            for tool in hidden:
                results[tool] = "hidden" if tool not in visible_set else "visible_unexpected"
            return results


async def test(label: str, headers: dict | None, expect: list[str]):
    print(f"\n{'=' * 60}")
    print(f"🔑 {label}  header={headers}")
    print(f"{'=' * 60}")

    try:
        results = await _inner("http://localhost:8888/sse", headers, expect)
    except BaseException as e:
        print(f"\n  {FAIL} 连接/执行异常: {type(e).__name__}")
        if hasattr(e, 'exceptions'):
            for sub in e.exceptions:
                print(f"    ↳ {type(sub).__name__}: {str(sub)[:150]}")
                if hasattr(sub, 'exceptions'):
                    for sub2 in sub.exceptions:
                        print(f"      ↳ {type(sub2).__name__}: {str(sub2)[:150]}")
        return False
    # 如果 _inner 没抛异常，但 results 是异常——不会发生
    except BaseException as e2:
        print(f"  cleanup异常（可忽略）: {e2}")

    all_ok = True
    for tool in expect:
        v = results.get(tool, "?")
        if v == "ok":
            print(f"  {PASS} {tool} 可见+可调用")
        elif v == "visible_denied":
            print(f"  {FAIL} {tool} 可见但被拒绝")
            all_ok = False
        else:
            print(f"  {FAIL} {tool} 异常状态={v}")
            all_ok = False

    hidden_expected = set(ALL) - set(expect)
    for tool in hidden_expected:
        v = results.get(tool, "?")
        if v == "hidden":
            print(f"  {PASS} {tool} 已隐藏")
        elif v == "visible_unexpected":
            print(f"  {FAIL} {tool} 应隐藏但可见")
            all_ok = False
        else:
            print(f"  {FAIL} {tool} 异常状态={v}")
            all_ok = False

    print(f"\n  {'✅ 通过' if all_ok else '❌ 失败'}")
    return all_ok


async def main():
    print("🚀 MCP 权限隔离测试\n")

    r1 = await test("无角色", None, [])
    r2 = await test("guide_agent", {"X-Agent-Role": "guide_agent"}, GUIDE)
    r3 = await test("product_agent", {"X-Agent-Role": "product_agent"}, PRODUCT)

    total = sum([r1, r2, r3])
    print(f"\n{'=' * 60}")
    print(f"结果: {total}/3 通过")
    print(f"  无角色: {'通过' if r1 else '失败'}")
    print(f"  guide_agent: {'通过' if r2 else '失败'}")
    print(f"  product_agent: {'通过' if r3 else '失败'}")
    sys.exit(0 if total == 3 else 1)


asyncio.run(main())
