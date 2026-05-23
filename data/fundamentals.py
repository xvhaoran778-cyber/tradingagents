import pandas as pd
from data.cache import cached


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
        from config import detect_market
        import requests
        market = detect_market(code)
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


def _safe_float(val) -> float:
    try:
        return float(val) if val is not None and val != "" else 0.0
    except (ValueError, TypeError):
        return 0.0
