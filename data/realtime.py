import requests
from config import detect_market
from data.cache import cached


@cached(ttl=30)
def get_realtime_quote(code: str) -> dict:
    try:
        market = detect_market(code)
        url = f"http://qt.gtimg.cn/q={market}{code}"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return {}
        text = resp.text.strip()
        if not text or "=" not in text:
            return {}

        parts = text.split("~")
        if len(parts) < 40:
            return {}

        fields = {
            "name": parts[1],
            "open": _parse_float(parts[5]),
            "prev_close": _parse_float(parts[4]),
            "current": _parse_float(parts[3]),
            "high": _parse_float(parts[33]),
            "low": _parse_float(parts[34]),
            "bid1": _parse_float(parts[9]),
            "bid1_vol": _parse_int(parts[10]),
            "ask1": _parse_float(parts[11]),
            "ask1_vol": _parse_int(parts[12]),
            "volume": _parse_int(parts[6]),
            "amount": _parse_float(parts[37]),
            "change_pct": _parse_float(parts[32]),
            "turnover_rate": _parse_float(parts[38]),
            "pe": _parse_float(parts[39]),
            "amplitude": _parse_float(parts[43]),
            "circulating_market_cap": _parse_float(parts[44]),
            "total_market_cap": _parse_float(parts[45]),
        }
        return fields
    except Exception:
        return {}


def _parse_float(val) -> float:
    try:
        return float(val) if val else 0.0
    except (ValueError, TypeError):
        return 0.0


def _parse_int(val) -> int:
    try:
        return int(float(val)) if val else 0
    except (ValueError, TypeError):
        return 0
