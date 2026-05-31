"""信号层 + 资金面 — 从 SKILL.md (a-stock-data V3.2.1) 集成
同花顺热点 / 概念板块 / 北向资金 / 东财资金流向 / 龙虎榜 / 全市场龙虎榜
/ 解禁 / 行业板块排名 / 融资融券 / 大宗交易 / 股东户数 / 分红 / 资金流120日
"""
import requests
from datetime import datetime, timedelta
from data.cache import cached
from data.signals_utils import em_get, eastmoney_datacenter, UA, get_prefix
from config import detect_market


# ═══════════════════════════════════════════════════════════
# 3.1 同花顺热点 — 当日强势股 + 题材归因
# ═══════════════════════════════════════════════════════════

@cached(ttl=180)
def get_hot_stocks(date: str = None) -> list[dict]:
    """同花顺当日强势股 + 题材归因 reason tags (独家)"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    url = f"http://zx.10jqka.com.cn/event/api/getharden/date/{date}/orderby/date/orderway/desc/charset/GBK/"
    headers = {"User-Agent": UA}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        if data.get("errocode", 0) != 0:
            return []
        rows = data.get("data") or []
        results = []
        for row in rows:
            results.append({
                "code": row.get("code", ""),
                "name": row.get("name", ""),
                "price": row.get("close", 0),
                "change_pct": row.get("zhangfu", 0),
                "reason": row.get("reason", ""),
                "turnover_pct": row.get("huanshou", 0),
                "volume": row.get("chengjiaoe", 0),
            })
        return results
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════
# 3.2 北向资金 — 同花顺 hsgtApi 实时分钟流向
# ═══════════════════════════════════════════════════════════

@cached(ttl=120)
def get_northbound_realtime() -> dict:
    """沪深股通当日实时分钟流向（含集合竞价 09:10–15:00，262 个时间点）"""
    url = "https://data.hexin.cn/market/hsgtApi/method/dayChart/"
    headers = {
        "User-Agent": UA,
        "Host": "data.hexin.cn",
        "Referer": "https://data.hexin.cn/",
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        d = r.json()
        times = d.get("time", [])
        hgt = d.get("hgt", [])
        sgt = d.get("sgt", [])
        n = len(times)
        result = {
            "points": [],
            "hgt_close": hgt[-1] if hgt else 0,
            "sgt_close": sgt[-1] if sgt else 0,
        }
        for i in range(n):
            result["points"].append({
                "time": times[i],
                "hgt_yi": hgt[i] if i < len(hgt) else None,
                "sgt_yi": sgt[i] if i < len(sgt) else None,
            })
        return result
    except Exception:
        return {}


# ═══════════════════════════════════════════════════════════
# 3.3 百度概念板块归属
# ═══════════════════════════════════════════════════════════

@cached(ttl=3600)
def get_concept_blocks(code: str) -> dict:
    """百度股市通概念板块归属 — 行业/概念/地域三维"""
    url = f"https://finance.pae.baidu.com/api/getrelatedblock?code={code}&market=ab&typeCode=all&finClientType=pc"
    headers = {
        "User-Agent": UA,
        "Accept": "application/vnd.finance-web.v1+json",
        "Referer": "https://gushitong.baidu.com/",
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        d = r.json()
        if str(d.get("ResultCode", -1)) != "0":
            return {"industry": [], "concept": [], "region": [], "concept_tags": []}
        result = {"industry": [], "concept": [], "region": [], "concept_tags": []}
        for block in d.get("Result", []):
            block_type = block.get("type", "")
            for item in block.get("list", []):
                entry = {
                    "name": item.get("name", ""),
                    "change_pct": item.get("increase", ""),
                }
                if "行业" in block_type:
                    result["industry"].append(entry)
                elif "概念" in block_type:
                    result["concept"].append(entry)
                    result["concept_tags"].append(entry["name"])
                elif "地域" in block_type:
                    result["region"].append(entry)
        return result
    except Exception:
        return {"industry": [], "concept": [], "region": [], "concept_tags": []}


# ═══════════════════════════════════════════════════════════
# 3.4 东财 push2 — 个股资金流向（分钟级）
# ═══════════════════════════════════════════════════════════

@cached(ttl=120)
def get_money_flow_minute(code: str) -> list[dict]:
    """个股资金流向（分钟级，当日盘中）
    返回: [{time, main_net, small_net, mid_net, large_net, super_net}] 单位元"""
    secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    url = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
    params = {
        "secid": secid, "klt": 1,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }
    headers = {
        "User-Agent": UA,
        "Referer": "https://quote.eastmoney.com/",
    }
    try:
        r = em_get(url, params=params, headers=headers, timeout=10)
        d = r.json()
        rows = []
        for line in d.get("data", {}).get("klines", []):
            parts = line.split(",")
            if len(parts) >= 6:
                rows.append({
                    "time": parts[0],
                    "main_net": float(parts[1]),
                    "small_net": float(parts[2]),
                    "mid_net": float(parts[3]),
                    "large_net": float(parts[4]),
                    "super_net": float(parts[5]),
                })
        return rows
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════
# 4.5 个股资金流（120日，日级）
# ═══════════════════════════════════════════════════════════

@cached(ttl=300)
def get_money_flow_120d(code: str) -> list[dict]:
    """个股资金流（日级，最近120个交易日）
    返回: [{date, main_net, small_net, mid_net, large_net, super_net}] 单位元"""
    market_code = 1 if code.startswith("6") else 0
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": f"{market_code}.{code}",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "lmt": "120",
    }
    headers = {
        "User-Agent": UA,
        "Referer": "https://quote.eastmoney.com/",
    }
    try:
        r = em_get(url, params=params, headers=headers, timeout=15)
        d = r.json()
        rows = []
        for line in d.get("data", {}).get("klines", []):
            parts = line.split(",")
            if len(parts) >= 7:
                rows.append({
                    "date": parts[0],
                    "main_net": float(parts[1]) if parts[1] != "-" else 0,
                    "small_net": float(parts[2]) if parts[2] != "-" else 0,
                    "mid_net": float(parts[3]) if parts[3] != "-" else 0,
                    "large_net": float(parts[4]) if parts[4] != "-" else 0,
                    "super_net": float(parts[5]) if parts[5] != "-" else 0,
                })
        return rows
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════
# 3.5 龙虎榜席位
# ═══════════════════════════════════════════════════════════

@cached(ttl=3600)
def get_dragon_tiger(code: str, trade_date: str = None, look_back: int = 30) -> dict:
    """龙虎榜数据聚合 — 上榜记录 + 买卖席位 TOP5 + 机构动向"""
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")
    start = datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=look_back)
    start_str = start.strftime("%Y-%m-%d")

    records = []
    try:
        data = eastmoney_datacenter(
            "RPT_DAILYBILLBOARD_DETAILSNEW",
            filter_str=f"(TRADE_DATE>='{start_str}')(TRADE_DATE<='{trade_date}')(SECURITY_CODE=\"{code}\")",
            page_size=50,
            sort_columns="TRADE_DATE", sort_types="-1",
        )
        for row in data:
            records.append({
                "date": str(row.get("TRADE_DATE", ""))[:10],
                "reason": row.get("EXPLANATION", ""),
                "net_buy_wan": round((row.get("BILLBOARD_NET_AMT") or 0) / 10000, 1),
                "turnover_pct": round(float(row.get("TURNOVERRATE") or 0), 2),
            })
    except Exception:
        pass

    seats = {"buy": [], "sell": []}
    institution = {"buy_amt_wan": 0, "sell_amt_wan": 0, "net_amt_wan": 0}

    if records:
        latest_date = records[0]["date"]
        try:
            buy_data = eastmoney_datacenter(
                "RPT_BILLBOARD_DAILYDETAILSBUY",
                filter_str=f"(TRADE_DATE='{latest_date}')(SECURITY_CODE=\"{code}\")",
                page_size=10,
                sort_columns="BUY", sort_types="-1",
            )
            for row in buy_data[:5]:
                seats["buy"].append({
                    "name": row.get("OPERATEDEPT_NAME", ""),
                    "buy_wan": round((row.get("BUY") or 0) / 10000, 1),
                    "sell_wan": round((row.get("SELL") or 0) / 10000, 1),
                    "net_wan": round((row.get("NET") or 0) / 10000, 1),
                })

            sell_data = eastmoney_datacenter(
                "RPT_BILLBOARD_DAILYDETAILSSELL",
                filter_str=f"(TRADE_DATE='{latest_date}')(SECURITY_CODE=\"{code}\")",
                page_size=10,
                sort_columns="SELL", sort_types="-1",
            )
            for row in sell_data[:5]:
                seats["sell"].append({
                    "name": row.get("OPERATEDEPT_NAME", ""),
                    "buy_wan": round((row.get("BUY") or 0) / 10000, 1),
                    "sell_wan": round((row.get("SELL") or 0) / 10000, 1),
                    "net_wan": round((row.get("NET") or 0) / 10000, 1),
                })

            for row in buy_data:
                if str(row.get("OPERATEDEPT_CODE", "")) == "0":
                    institution["buy_amt_wan"] += (row.get("BUY") or 0) / 10000
            for row in sell_data:
                if str(row.get("OPERATEDEPT_CODE", "")) == "0":
                    institution["sell_amt_wan"] += (row.get("SELL") or 0) / 10000
            institution["buy_amt_wan"] = round(institution["buy_amt_wan"], 1)
            institution["sell_amt_wan"] = round(institution["sell_amt_wan"], 1)
            institution["net_amt_wan"] = round(institution["buy_amt_wan"] - institution["sell_amt_wan"], 1)
        except Exception:
            pass

    return {"records": records, "seats": seats, "institution": institution}


# ═══════════════════════════════════════════════════════════
# 3.6 限售解禁日历
# ═══════════════════════════════════════════════════════════

@cached(ttl=3600)
def get_lockup_expiry(code: str, trade_date: str = None, forward_days: int = 90) -> dict:
    """限售解禁日历 — 历史 + 未来待解禁"""
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")
    end_date = datetime.strptime(trade_date, "%Y-%m-%d") + timedelta(days=forward_days)
    end_str = end_date.strftime("%Y-%m-%d")

    history, upcoming = [], []
    try:
        history_data = eastmoney_datacenter(
            "RPT_LIFT_STAGE",
            filter_str=f"(SECURITY_CODE=\"{code}\")",
            page_size=15,
            sort_columns="FREE_DATE", sort_types="-1",
        )
        for row in history_data:
            history.append({
                "date": str(row.get("FREE_DATE", ""))[:10],
                "type": row.get("LIMITED_STOCK_TYPE", ""),
                "shares": row.get("FREE_SHARES_NUM", 0),
                "ratio": row.get("FREE_RATIO", 0),
            })

        upcoming_data = eastmoney_datacenter(
            "RPT_LIFT_STAGE",
            filter_str=f"(SECURITY_CODE=\"{code}\")(FREE_DATE>='{trade_date}')(FREE_DATE<='{end_str}')",
            page_size=20,
            sort_columns="FREE_DATE", sort_types="1",
        )
        for row in upcoming_data:
            upcoming.append({
                "date": str(row.get("FREE_DATE", ""))[:10],
                "type": row.get("LIMITED_STOCK_TYPE", ""),
                "shares": row.get("FREE_SHARES_NUM", 0),
                "ratio": row.get("FREE_RATIO", 0),
            })
    except Exception:
        pass

    return {"history": history, "upcoming": upcoming}


# ═══════════════════════════════════════════════════════════
# 3.7 行业板块排名
# ═══════════════════════════════════════════════════════════

@cached(ttl=180)
def get_industry_comparison(top_n: int = 20) -> dict:
    """全行业涨跌幅排名（东财行业板块，~100 个行业）"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "fltt": "2", "invt": "2",
        "fs": "m:90+t:2",
        "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
    }
    headers = {"User-Agent": UA}
    try:
        r = em_get(url, params=params, headers=headers, timeout=15)
        d = r.json()
        items = d.get("data", {}).get("diff", [])
        if not items:
            return {"top": [], "bottom": [], "total": 0}
        rows = []
        for item in items:
            rows.append({
                "rank": len(rows) + 1,
                "name": item.get("f14", ""),
                "change_pct": item.get("f3", 0),
                "code": item.get("f12", ""),
                "up_count": item.get("f104", 0),
                "down_count": item.get("f105", 0),
                "leader": item.get("f140", ""),
                "leader_change": item.get("f136", 0),
            })
        return {
            "top": rows[:top_n],
            "bottom": rows[-top_n:],
            "total": len(rows),
        }
    except Exception:
        return {"top": [], "bottom": [], "total": 0}


# ═══════════════════════════════════════════════════════════
# 3.8 全市场龙虎榜
# ═══════════════════════════════════════════════════════════

@cached(ttl=180)
def get_daily_dragon_tiger(trade_date: str = None, min_net_buy: float = None) -> dict:
    """每日全市场龙虎榜汇总"""
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")
    try:
        data = eastmoney_datacenter(
            "RPT_DAILYBILLBOARD_DETAILSNEW",
            filter_str=f"(TRADE_DATE>='{trade_date}')(TRADE_DATE<='{trade_date}')",
            page_size=500,
            sort_columns="BILLBOARD_NET_AMT", sort_types="-1",
        )
        if not data:
            return {"date": trade_date, "total_records": 0, "stocks": []}
        stocks = []
        for row in data:
            net_buy = (row.get("BILLBOARD_NET_AMT") or 0) / 10000
            if min_net_buy is not None and net_buy < min_net_buy:
                continue
            stocks.append({
                "code": row.get("SECURITY_CODE", ""),
                "name": row.get("SECURITY_NAME_ABBR", ""),
                "reason": row.get("EXPLANATION", ""),
                "close": row.get("CLOSE_PRICE") or 0,
                "change_pct": round(float(row.get("CHANGE_RATE") or 0), 2),
                "net_buy_wan": round(net_buy, 1),
                "turnover_pct": round(float(row.get("TURNOVERRATE") or 0), 2),
            })
        return {"date": trade_date, "total_records": len(stocks), "stocks": stocks}
    except Exception:
        return {"date": trade_date, "total_records": 0, "stocks": []}


# ═══════════════════════════════════════════════════════════
# 4.1 融资融券明细
# ═══════════════════════════════════════════════════════════

@cached(ttl=600)
def get_margin(code: str, page_size: int = 30) -> list[dict]:
    """融资融券明细（日级）"""
    try:
        data = eastmoney_datacenter(
            "RPTA_WEB_RZRQ_GGMX",
            filter_str=f'(SCODE="{code}")',
            page_size=page_size,
            sort_columns="DATE", sort_types="-1",
        )
        rows = []
        for row in data:
            rows.append({
                "date": str(row.get("DATE", ""))[:10],
                "rzye": row.get("RZYE", 0),
                "rzmre": row.get("RZMRE", 0),
                "rzche": row.get("RZCHE", 0),
                "rqye": row.get("RQYE", 0),
                "rqmcl": row.get("RQMCL", 0),
                "rqchl": row.get("RQCHL", 0),
                "rzrqye": row.get("RZRQYE", 0),
            })
        return rows
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════
# 4.2 大宗交易
# ═══════════════════════════════════════════════════════════

@cached(ttl=600)
def get_block_trade(code: str, page_size: int = 20) -> list[dict]:
    """大宗交易记录
    返回: [{date, price, close, premium_pct, vol, amount, buyer, seller}]"""
    try:
        data = eastmoney_datacenter(
            "RPT_DATA_BLOCKTRADE",
            filter_str=f'(SECURITY_CODE="{code}")',
            page_size=page_size,
            sort_columns="TRADE_DATE", sort_types="-1",
        )
        rows = []
        for row in data:
            close = row.get("CLOSE_PRICE") or 0
            deal_price = row.get("DEAL_PRICE") or 0
            premium = ((deal_price / close - 1) * 100) if close else 0
            rows.append({
                "date": str(row.get("TRADE_DATE", ""))[:10],
                "price": deal_price,
                "close": close,
                "premium_pct": round(premium, 2),
                "vol": row.get("DEAL_VOLUME", 0),
                "amount": row.get("DEAL_AMT", 0),
                "buyer": row.get("BUYER_NAME", ""),
                "seller": row.get("SELLER_NAME", ""),
            })
        return rows
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════
# 4.3 股东户数变化
# ═══════════════════════════════════════════════════════════

@cached(ttl=3600)
def get_holder_count(code: str, page_size: int = 10) -> list[dict]:
    """股东户数变化（季度级）
    返回: [{date, holder_num, change_num, change_ratio, avg_shares}]"""
    try:
        data = eastmoney_datacenter(
            "RPT_HOLDERNUMLATEST",
            filter_str=f'(SECURITY_CODE="{code}")',
            page_size=page_size,
            sort_columns="END_DATE", sort_types="-1",
        )
        rows = []
        for row in data:
            rows.append({
                "date": str(row.get("END_DATE", ""))[:10],
                "holder_num": row.get("HOLDER_NUM", 0),
                "change_num": row.get("HOLDER_NUM_CHANGE", 0),
                "change_ratio": row.get("HOLDER_NUM_RATIO", 0),
                "avg_shares": row.get("AVG_FREE_SHARES", 0),
            })
        return rows
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════
# 4.4 分红送转历史
# ═══════════════════════════════════════════════════════════

@cached(ttl=3600)
def get_dividend_history(code: str, page_size: int = 20) -> list[dict]:
    """分红送转历史
    返回: [{date, bonus_rmb(每股派息), transfer_ratio(转增), bonus_ratio(送股)}]"""
    try:
        data = eastmoney_datacenter(
            "RPT_SHAREBONUS_DET",
            filter_str=f'(SECURITY_CODE="{code}")',
            page_size=page_size,
            sort_columns="EX_DIVIDEND_DATE", sort_types="-1",
        )
        rows = []
        for row in data:
            rows.append({
                "date": str(row.get("EX_DIVIDEND_DATE", ""))[:10],
                "bonus_rmb": row.get("PRETAX_BONUS_RMB", 0),
                "transfer_ratio": row.get("TRANSFER_RATIO", 0),
                "bonus_ratio": row.get("BONUS_RATIO", 0),
                "plan": row.get("ASSIGN_PROGRESS", ""),
            })
        return rows
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════
# 研报（东财 reportapi）
# ═══════════════════════════════════════════════════════════

@cached(ttl=3600)
def get_research_reports(code: str, max_pages: int = 3) -> list[dict]:
    """拉取指定股票的研报列表（东财 reportapi）"""
    url = "https://reportapi.eastmoney.com/report/list"
    all_records = []
    try:
        for page in range(1, max_pages + 1):
            params = {
                "industryCode": "*", "pageSize": "50", "industry": "*",
                "rating": "*", "ratingChange": "*",
                "beginTime": "2000-01-01", "endTime": "2030-01-01",
                "pageNo": str(page), "fields": "", "qType": "0",
                "orgCode": "", "code": code, "rcode": "",
                "p": str(page), "pageNum": str(page), "pageNumber": str(page),
            }
            r = em_get(url, params=params,
                       headers={"Referer": "https://data.eastmoney.com/"}, timeout=30)
            d = r.json()
            rows = d.get("data") or []
            if not rows:
                break
            # JSONP stripped by em_get if needed
            for item in rows:
                all_records.append({
                    "title": item.get("title", ""),
                    "org": item.get("orgSName", ""),
                    "analyst": item.get("analystName", ""),
                    "rating": item.get("emRatingName", ""),
                    "date": (item.get("publishDate") or "")[:10],
                    "eps_this": item.get("predictThisYearEps"),
                    "eps_next": item.get("predictNextYearEps"),
                    "eps_next2": item.get("predictNextTwoYearEps"),
                })
            if page >= (d.get("TotalPage", 1) or 1):
                break
    except Exception:
        pass
    return all_records


# ═══════════════════════════════════════════════════════════
# 百度K线（行情层补充 — 带MA）
# ═══════════════════════════════════════════════════════════

@cached(ttl=600)
def get_baidu_kline(code: str, start_time: str = "") -> dict:
    """百度股市通K线 — 返回时自带 ma5/ma10/ma20 均价"""
    url = "https://finance.pae.baidu.com/selfselect/getstockquotation"
    params = {
        "all": "1", "isIndex": "false", "isBk": "false", "isBlock": "false",
        "isFutures": "false", "isStock": "true", "newFormat": "1",
        "group": "quotation_kline_ab", "finClientType": "pc",
        "code": code, "start_time": start_time, "ktype": "1",
    }
    headers = {
        "User-Agent": UA,
        "Accept": "application/vnd.finance-web.v1+json",
        "Referer": "https://gushitong.baidu.com/",
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        d = r.json()
        md = d.get("Result", {}).get("newMarketData", {})
        return {
            "keys": md.get("keys", []),
            "rows": md.get("marketData", "").split(";"),
        }
    except Exception:
        return {"keys": [], "rows": []}
