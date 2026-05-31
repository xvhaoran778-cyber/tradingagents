"""公告层 — 从 SKILL.md (a-stock-data V3.2.1) 集成
巨潮 cninfo 公告 + mootdx 公告摘要
"""
import requests
from datetime import datetime
from data.cache import cached
from data.signals_utils import UA


def _cninfo_ts_to_date(ts):
    """巨潮 announcementTime 返回 Unix 毫秒整数"""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
    return str(ts)[:10] if ts else ""


@cached(ttl=3600)
def get_cninfo_announcements(code: str, page_size: int = 30) -> list[dict]:
    """巨潮公告全文检索
    返回: [{title, type, date, url}]
    """
    if code.startswith("6"):
        org_id = f"gssh0{code}"
    elif code.startswith(("8", "4")):
        org_id = f"gsbj0{code}"
    else:
        org_id = f"gssz0{code}"

    payload = {
        "stock": f"{code},{org_id}",
        "tabName": "fulltext",
        "pageSize": str(page_size),
        "pageNum": "1",
        "column": "",
        "category": "",
        "plate": "",
        "seDate": "",
        "searchkey": "",
        "secid": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.cninfo.com.cn/new/disclosure",
        "Origin": "https://www.cninfo.com.cn",
    }
    try:
        r = requests.post("https://www.cninfo.com.cn/new/hisAnnouncement/query",
                          data=payload, headers=headers, timeout=15)
        d = r.json()
        rows = []
        for item in d.get("announcements", []) or []:
            rows.append({
                "title": item.get("announcementTitle", ""),
                "type": item.get("announcementTypeName", ""),
                "date": _cninfo_ts_to_date(item.get("announcementTime")),
                "url": f"https://www.cninfo.com.cn/new/disclosure/detail?annoId={item.get('announcementId', '')}",
            })
        return rows
    except Exception:
        return []


@cached(ttl=3600)
def get_f10_latest_notice(code: str) -> str:
    """mootdx F10 最新提示（最近公告/分红/决议摘要）"""
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market='std')
        text = client.F10(symbol=code, name='最新提示')
        return str(text) if text else ""
    except Exception:
        return ""
