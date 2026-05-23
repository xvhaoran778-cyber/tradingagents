import requests
from lxml import etree


def get_sina_news(code: str, count: int = 10) -> list[dict]:
    try:
        url = f"https://searchapi.sina.com.cn/?c=news&q={code}&range=all&time=all&num={count}&site=finance&sort=time"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
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


def get_eastmoney_news(code: str, count: int = 10) -> list[dict]:
    try:
        sec_code = f"1.{_to_sec_code(code)}"
        url = f"https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            "secid": sec_code,
            "fields": "f58,f152",
            "invt": 2,
            "fltt": 2,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://finance.eastmoney.com/",
        }
        news_url = f"https://so.eastmoney.com/news/s?keyword={code}&pageindex=1&pagesize={count}&searchrange=114"
        resp = requests.get(news_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        items = []
        for item in data.get("Datas", [])[:count]:
            items.append({
                "title": item.get("Title", "").replace("<em>", "").replace("</em>", ""),
                "summary": item.get("Summary", "").replace("<em>", "").replace("</em>", ""),
                "time": item.get("ShowDate", ""),
                "source": item.get("Source", ""),
            })
        return items
    except Exception:
        return []


def _to_sec_code(code: str) -> str:
    if code.startswith(("60", "68")):
        return f"{code}"
    return f"{code}"


def _fallback_news(code: str, count: int = 10) -> list[dict]:
    try:
        import pandas as pd
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
