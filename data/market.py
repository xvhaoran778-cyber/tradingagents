import pandas as pd
from config import detect_market
from data.cache import cached


@cached(ttl=600)
def get_kline_data(code: str, count: int = 120) -> pd.DataFrame:
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market='std')
        df = client.bars(symbol=code, frequency=9, start=0, count=count)
        if df is not None and not df.empty:
            df.columns = [c.lower() for c in df.columns]
            return df
    except Exception as e:
        pass
    return _mock_kline(code, count)


@cached(ttl=120)
def get_minute_data(code: str) -> pd.DataFrame:
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market='std')
        df = client.bars(symbol=code, frequency=1, start=0, count=60)
        if df is not None and not df.empty:
            df.columns = [c.lower() for c in df.columns]
            return df
    except Exception as e:
        pass
    return pd.DataFrame()


@cached(ttl=3600)
def get_industry(code: str) -> str:
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market='std')
        info = client.index(symbol=code)
        if info is not None:
            return info.get("industry", "")
    except Exception:
        pass
    return ""


@cached(ttl=3600)
def get_stock_name(code: str) -> str:
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market='std')
        quotes = client.quotes(symbol=code)
        if quotes and len(quotes) > 0:
            return quotes[0].get("name", "")
    except Exception:
        pass

    try:
        import requests
        mkt = detect_market(code)
        url = f"http://qt.gtimg.cn/q={mkt}{code}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            parts = resp.text.strip().split("~")
            if len(parts) > 1:
                return parts[1]
    except Exception:
        pass
    return ""


def _mock_kline(code: str, count: int = 120) -> pd.DataFrame:
    import numpy as np
    from datetime import datetime, timedelta
    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(count, 0, -1)]
    base_price = 15.0
    n = len(dates)
    closes = base_price + np.cumsum(np.random.randn(n) * 0.3)
    closes = np.maximum(closes, 5)
    opens = closes + np.random.randn(n) * 0.2
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(n) * 0.3)
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(n) * 0.3)
    volumes = np.random.randint(1000000, 10000000, n)
    df = pd.DataFrame({
        "date": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })
    return df


def get_technical_indicators(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    volume = df["volume"].values

    def ma(data, period):
        if len(data) < period:
            return None
        return round(float(data[-period:].mean()), 2)

    def rsi(data, period=14):
        if len(data) <= period:
            return None
        deltas = np.diff(data)
        gains = deltas[deltas > 0].sum()
        losses = -deltas[deltas < 0].sum()
        if losses == 0:
            return 100.0
        rs = gains / losses if losses > 0 else 0
        return round(100 - 100 / (1 + rs), 2)

    def macd(data):
        import numpy as np
        if len(data) < 26:
            return None, None, None
        ema12 = pd.Series(data).ewm(span=12).mean().values
        ema26 = pd.Series(data).ewm(span=26).mean().values
        dif = ema12 - ema26
        dea = pd.Series(dif).ewm(span=9).mean().values
        bar = dif - dea
        return round(float(dif[-1]), 4), round(float(dea[-1]), 4), round(float(bar[-1]), 4)

    def kdj(high, low, close, period=9):
        if len(close) < period:
            return None, None, None
        import numpy as np
        hh = pd.Series(high).rolling(period).max().values
        ll = pd.Series(low).rolling(period).min().values
        rsv = np.where((hh - ll) != 0, (close - ll) / (hh - ll) * 100, 50)
        k = pd.Series(rsv).ewm(com=2).mean().values
        d = pd.Series(k).ewm(com=2).mean().values
        j = 3 * k - 2 * d
        return round(float(k[-1]), 2), round(float(d[-1]), 2), round(float(j[-1]), 2)

    import numpy as np
    result = {
        "ma5": ma(close, 5),
        "ma10": ma(close, 10),
        "ma20": ma(close, 20),
        "ma60": ma(close, 60),
        "rsi": rsi(close, 14),
        "volume_ma5": ma(volume, 5),
        "current_price": round(float(close[-1]), 2),
        "high_60d": round(float(high[-60:].max()), 2) if len(high) >= 60 else round(float(high.max()), 2),
        "low_60d": round(float(low[-60:].min()), 2) if len(low) >= 60 else round(float(low.min()), 2),
    }
    dif, dea, bar = macd(close)
    result["macd_dif"] = dif
    result["macd_dea"] = dea
    result["macd_bar"] = bar
    k, d, j = kdj(high, low, close)
    result["kdj_k"] = k
    result["kdj_d"] = d
    result["kdj_j"] = j

    pct_chg = (close[-1] / close[0] - 1) * 100 if len(close) > 1 else 0
    result["period_return_pct"] = round(float(pct_chg), 2)
    return result
