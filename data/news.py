"""新闻层 — 新浪 + 东财个股新闻 + 东财全球资讯（从 SKILL.md 集成）"""
import requests
import json
import re
from data.cache import cached
from data.signals_utils import UA, em_get


@cached(ttl=120)
def get_sina_news(code: str, count: int = 10) -> list[dict]:
    try:
        url = f"https://searchapi.sina.com.cn/?c=news&q={code}&range=all&time=all&num={count}&site=finance&sort=time"
        headers = {"User-Agent": UA}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return _fallback_news(code, count)
        data = resp.json()
        items = []
        for item in data.get("result", {}).get("items", [])[:count]:
            items.append({
                "title": item.get("title", ""),
                "summary": item.get("content", "") or item.get("summary", ""),
                "time": item.get("ctime", ""),
                "source": item.get("source", ""),
            })
        return items
    except Exception:
        return _fallback_news(code, count)


@cached(ttl=120)
def get_eastmoney_news(code: str, count: int = 10) -> list[dict]:
    """东财个股新闻流 — 直连 search-api-web"""
    try:
        url = "https://search-api-web.eastmoney.com/search/jsonp"
        params = {
            "cb": "callback",
            "param": f'{{"uid":"","keyword":"{code}","type":["cmsArticleWebOld"],"client":"web","clientType":"web","clientVersion":"curr"}}',
            "page": 1,
            "pageSize": count,
        }
        headers = {
            "User-Agent": UA,
            "Referer": "https://so.eastmoney.com/",
        }
        resp = em_get(url, params=params, headers=headers, timeout=10)
        text = resp.text.strip()
        # strip jsonp wrapper
        start = text.find("(")
        end = text.rfind(")")
        if start >= 0 and end > start:
            text = text[start + 1:end]
        data = json.loads(text)
        # result.cmsArticleWebOld is directly a list
        articles = data.get("result", {}).get("cmsArticleWebOld", []) or []
        items = []
        for item in articles[:count]:
            items.append({
                "title": re.sub(r"<[^>]+>", "", item.get("title", "")),
                "summary": re.sub(r"<[^>]+>", "", item.get("summary", "") or ""),
                "time": (item.get("date") or "")[:10],
                "source": item.get("source", ""),
            })
        return items
    except Exception:
        return []


@cached(ttl=120)
def get_global_news(count: int = 20) -> list[dict]:
    """东财全球财经资讯（7×24，替代已下线的财联社快讯）"""
    try:
        url = "https://np-weblist.eastmoney.com/comm/web/list"
        params = {
            "client": "web",
            "biz": "global",
            "type": "global",
            "page": 1,
            "size": count,
        }
        headers = {
            "User-Agent": UA,
            "Referer": "https://finance.eastmoney.com/",
        }
        resp = em_get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        items = []
        for item in data.get("list", [])[:count]:
            items.append({
                "title": item.get("title", ""),
                "time": (item.get("showDate") or "")[:10],
                "content": item.get("content", ""),
                "source": "东财全球资讯",
            })
        return items
    except Exception:
        return []


def _to_sec_code(code: str) -> str:
    return code


def _fallback_news(code: str, count: int = 10) -> list[dict]:
    try:
        import yfinance as yf
        ticker = yf.Ticker(f"{code}.SS" if code.startswith(("60", "68")) else f"{code}.SZ")
        news = ticker.news[:count] if ticker.news else []
        return [
            {"title": n.get("title", ""), "summary": n.get("summary", ""),
             "time": str(n.get("providerPublishTime", "")), "source": "Yahoo Finance"}
            for n in news
        ]
    except Exception:
        return []


def get_all_news(code: str, count: int = 10) -> list[dict]:
    seen = set()
    all_news = []
    for source_func in [get_sina_news, get_eastmoney_news]:
        for item in source_func(code, count):
            title = item.get("title", "")
            if title and title not in seen:
                seen.add(title)
                all_news.append(item)
        if len(all_news) >= count:
            break
    return all_news[:count]
