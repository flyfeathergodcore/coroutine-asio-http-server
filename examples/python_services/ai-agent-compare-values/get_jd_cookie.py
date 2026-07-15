#!/usr/bin/env python3
"""打开京东登录页，手动登录后自动保存 Cookie 到文件"""
import asyncio, json, os

OUTPUT = os.environ.get("JD_COOKIE_OUTPUT", "jd_cookie.json")

async def main():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        # 非无头模式（显示浏览器窗口）
        browser = await p.chromium.launch(
            headless=False,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = await browser.new_context()
        page = await context.new_page()

        print(f"正在打开京东登录页...")
        await page.goto("https://www.jd.com", wait_until="domcontentloaded")

        print("=" * 50)
        print("请在打开的浏览器窗口中手动登录京东")
        print("登录完成后，按 Enter 键保存 Cookie...")
        print("=" * 50)
        input()

        # 保存 Cookie
        cookies = await context.cookies()
        with open(OUTPUT, "w") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"Cookie 已保存到: {OUTPUT} ({len(cookies)} 条)")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
