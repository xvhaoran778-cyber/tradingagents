"""基础数据层 — mootdx 财务/F10 + 东财个股信息 + 新浪财报三表（从 SKILL.md 集成）"""
import pandas as pd
import requests
from io import StringIO
from data.cache import cached
from data.signals_utils import UA, get_prefix


@cached(ttl=3600)
def get_financial_data(code: str) -> dict:
    result = {}

    try:
        from mootdx.affairs import Affairs
        affairs = Affairs()
        financial = affairs.financial(code=code)
        if financial is not None and not financial.empty:
            latest = financial.iloc[-1] if len(financial) > 0 else {}
            result["revenue"] = _safe_float(latest.get("revenue"))
            result["profit"] = _safe_float(latest.get("profit"))
            result["total_assets"] = _safe_float(latest.get("total_assets"))
            result["total_liabilities"] = _safe_float(latest.get("total_liabilities"))
            result["equity"] = _safe_float(latest.get("equity"))
    except Exception:
        pass

    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market='std')
        quotes = client.quotes(symbol=code)
        if quotes and len(quotes) > 0:
            q = quotes[0] if isinstance(quotes, list) else quotes
            result["pe"] = _safe_float(q.get("pe") or q.get("PE", 0))
            result["pb"] = _safe_float(q.get("pb") or q.get("PB", 0))
            result["market_cap"] = _safe_float(q.get("market_cap") or q.get("流通市值", 0))
            result["total_capital"] = _safe_float(q.get("total_capital") or 0)
    except Exception:
        pass

    try:
        market = get_prefix(code)
        url = f"http://qt.gtimg.cn/q={market}{code}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            parts = resp.text.strip().split("~")
            if len(parts) > 45:
                result["pe"] = _safe_float(parts[39])
                result["amplitude"] = _safe_float(parts[43])
                result["circulating_market_cap"] = _safe_float(parts[44])
                result["total_market_cap"] = _safe_float(parts[45])
    except Exception:
        pass

    return result


@cached(ttl=3600)
def get_f10_data(code: str) -> dict:
    """mootdx F10 公司资料（9 大类文本）"""
    result = {}
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market='std')
        categories = ["公司概况", "最新提示", "分红配股", "财务数据",
                       "行业新闻", "股东结构", "股本结构"]
        for cat in categories:
            try:
                text = client.F10(symbol=code, name=cat)
                if text:
                    text_str = str(text)
                    if len(text_str) > 800:
                        text_str = text_str[:800] + "..."
                    result[cat] = text_str
            except Exception:
                pass
    except Exception:
        pass
    return result


@cached(ttl=3600)
def get_sina_financial_statements(code: str) -> dict:
    """新浪财报三表 — 资产负债表/利润表/现金流量表"""
    result = {}
    prefix = get_prefix(code)
    table_map = {
        "lrb": "利润表",
        "zcfzb": "资产负债表",
        "xjllb": "现金流量表",
    }
    headers = {"User-Agent": UA}
    try:
        for key, label in table_map.items():
            url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20info/CN_MarketDataService.getFinanceData?type={key}&code={prefix}{code}"
            resp = requests.get(url, headers=headers, timeout=10)
            text = resp.text.strip()
            # jsonp
            start = text.find("(")
            end = text.rfind(")")
            if start >= 0 and end > start:
                text = text[start + 1:end]
            import json
            data = json.loads(text)
            rows = {}
            # result.data.report_list: {period_key: {data: [{item_title, ...}]}}
            report_list = data.get("result", {}).get("data", {}).get("report_list", {})
            for period, period_data in report_list.items():
                items = period_data.get("data", []) if isinstance(period_data, dict) else []
                period_rows = {}
                for item in items:
                    period_rows[item.get("item_title", "")] = item.get("item_value", "")
                rows[period[:10]] = period_rows
            result[label] = rows
    except Exception:
        pass
    return result


def _safe_float(val) -> float:
    try:
        return float(val) if val is not None and val != "" else 0.0
    except (ValueError, TypeError):
        return 0.0
