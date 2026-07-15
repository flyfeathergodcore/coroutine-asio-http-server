"""
httpx 爬取慢慢买商品比价信息。

慢慢买是一个商品比价/查历史价格网站，作为价格查询的辅助方案。
- 不需要浏览器/登录/Cookie
"""
import json
import re
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)


def handle(keyword: str) -> dict:
    """
    爬取慢慢买搜索指定商品获取价格信息。

    参数:
        keyword — 商品关键词，如 "小米手机"

    返回:
        {
            "success": true,
            "keyword": "小米手机",
            "products": [
                {
                    "title": "商品标题",
                    "price": "2620.99",
                    "original_price": "",
                    "platform": "京东自营",
                    "url": "商品链接",
                    "image": "图片URL",
                }
            ]
        }
        失败时返回:
        {
            "success": false,
            "error": "错误描述"
        }
    """
    try:
        return _crawl_price(keyword)
    except Exception as e:
        logger.error("manmanbuy 爬取异常: %s", e)
        return {"success": False, "error": str(e)}


def _crawl_price(keyword: str) -> dict:
    """执行慢慢买价格爬取"""
    url = f"https://s.manmanbuy.com/pc/search/result?keyword={quote(keyword)}&c=discount"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
    }

    try:
        import httpx
    except ImportError:
        return {"success": False, "error": "httpx 未安装，无法发送请求"}

    try:
        resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        resp.encoding = "utf-8"
        html = resp.text
    except Exception as e:
        return {"success": False, "error": f"请求异常: {e}"}

    if "verify" in resp.url.host or len(html) < 100:
        return {"success": False, "error": "被慢慢买拦截"}

    products = _parse_html(html)
    if products:
        return {
            "success": True,
            "keyword": keyword,
            "products": products,
            "source": "manmanbuy",
        }
    else:
        return {
            "success": False,
            "error": "未解析到商品信息",
            "keyword": keyword,
        }


def _parse_html(html: str) -> list:
    """从 HTML 中解析商品列表"""
    products = []
    # 按商品卡片切分
    blocks = re.split(r'(?=<div[^>]*class="[^"]*?DiscountItemPC_itemTitle__)', html)

    for block in blocks[:10]:
        product = _parse_product(block)
        if product and product.get("title"):
            products.append(product)

    return products


def _parse_product(block: str) -> dict:
    """解析单个商品卡片"""
    title = ""
    price = ""
    platform = ""
    item_url = ""
    image = ""

    # 标题 + 链接
    m = re.search(r'<a[^>]*title="([^"]*)"[^>]*href="([^"]*)"', block)
    if m:
        title = m.group(1).strip()
        item_url = m.group(2).strip()

    # 价格：itemSubTitle 里的 "2620.99元" 格式
    m = re.search(r'itemSubTitle[^>]*>.*?([\d]+\.\d{2})元', block)
    if m:
        price = m.group(1)

    # 平台：itemMall 里的文字
    m = re.search(r'itemMall[^>]*>([^<]+)<', block)
    if m:
        platform = m.group(1).strip()

    # 图片
    m = re.search(r'<img[^>]*src="(https?://[^"]*)"', block)
    if m:
        image = m.group(1).strip()

    if title:
        return {
            "title": title,
            "price": price,
            "original_price": "",
            "platform": platform,
            "url": item_url,
            "image": image,
        }
    return {}
