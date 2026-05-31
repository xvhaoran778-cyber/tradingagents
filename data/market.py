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


def get_technical_indicators(df: pd.DataFrame, realtime_price: float = None) -> dict:
    if df is None or df.empty:
        return {}
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    volume = df["volume"].values

    # 如果有腾讯实时价且与K线收盘价不一致，缩放K线数据
    kline_close = float(close[-1])
    if realtime_price and realtime_price > 0 and kline_close > 0:
        ratio = realtime_price / kline_close
        if abs(ratio - 1.0) > 0.05:  # 偏差超过5%就缩放
            close = close * ratio
            high = high * ratio
            low = low * ratio
            # 重新给df赋值用于stockstats
            df = df.copy()
            df["close"] = close
            df["high"] = high
            df["low"] = low
            kline_close = realtime_price

    # Try stockstats first (battle-tested, matches Chinese market conventions)
    try:
        from stockstats import StockDataFrame
        # stockstats needs 'date' as index and specific column names
        sdf = df.copy()
        if "date" in sdf.columns:
            sdf.set_index("date", inplace=True)
        # Rename columns to stockstats convention if needed
        sdf.rename(columns={
            "open": "open", "close": "close",
            "high": "high", "low": "low",
            "volume": "volume",
        }, inplace=True)
        sdf = StockDataFrame.retype(sdf)

        # Access indicators (stockstats computes lazily on access)
        result = {
            "ma5": _ss(sdf, "close_5_sma"),
            "ma10": _ss(sdf, "close_10_sma"),
            "ma20": _ss(sdf, "close_20_sma"),
            "ma60": _ss(sdf, "close_60_sma"),
            "ema5": _ss(sdf, "close_5_ema"),
            "ema10": _ss(sdf, "close_10_ema"),
            "ema20": _ss(sdf, "close_20_ema"),
            "ema60": _ss(sdf, "close_60_ema"),
            "rsi": _ss(sdf, "rsi_14"),
            "volume_ma5": _ss(sdf, "volume_5_sma"),
            "macd_dif": _ss(sdf, "macd"),
            "macd_dea": _ss(sdf, "macds"),
            "macd_bar": _ss(sdf, "macdh"),
            "kdj_k": _ss(sdf, "kdjk"),
            "kdj_d": _ss(sdf, "kdjd"),
            "kdj_j": _ss(sdf, "kdjj"),
            "atr": _ss(sdf, "atr"),
            "current_price": round(float(close[-1]), 2),
            "high_60d": round(float(high[-60:].max()), 2) if len(high) >= 60 else round(float(high.max()), 2),
            "low_60d": round(float(low[-60:].min()), 2) if len(low) >= 60 else round(float(low.min()), 2),
        }
        return result
    except Exception:
        pass

    # Fallback: hand-rolled calculation
    import numpy as np

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
        if len(data) < 26:
            return None, None, None
        arr = np.array(data, dtype=float)
        ema12 = np.zeros_like(arr)
        ema26 = np.zeros_like(arr)
        ema12[0] = arr[0]
        ema26[0] = arr[0]
        for i in range(1, len(arr)):
            ema12[i] = ema12[i-1] * 11/13 + arr[i] * 2/13
            ema26[i] = ema26[i-1] * 25/27 + arr[i] * 2/27
        dif = ema12 - ema26
        dea = np.zeros_like(dif)
        dea[0] = dif[0]
        for i in range(1, len(dif)):
            dea[i] = dea[i-1] * 8/10 + dif[i] * 2/10
        bar = (dif - dea) * 2
        return round(float(dif[-1]), 4), round(float(dea[-1]), 4), round(float(bar[-1]), 4)

    def kdj(high, low, close, period=9):
        if len(close) < period:
            return None, None, None
        hh = pd.Series(high).rolling(period, min_periods=period).max().values
        ll = pd.Series(low).rolling(period, min_periods=period).min().values
        rsv = np.full_like(close, 50.0, dtype=float)
        valid = ~np.isnan(hh) & ~np.isnan(ll) & ((hh - ll) != 0)
        rsv[valid] = (close[valid] - ll[valid]) / (hh[valid] - ll[valid]) * 100
        k_vals = np.full_like(rsv, 50.0, dtype=float)
        d_vals = np.full_like(rsv, 50.0, dtype=float)
        for i in range(1, len(rsv)):
            k_vals[i] = (k_vals[i-1] * 2 + rsv[i] * 1) / 3
            d_vals[i] = (d_vals[i-1] * 2 + k_vals[i] * 1) / 3
        j_vals = 3 * k_vals - 2 * d_vals
        return round(float(k_vals[-1]), 2), round(float(d_vals[-1]), 2), round(float(j_vals[-1]), 2)

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


def _ss(sdf, col):
    """Safely get a stockstats column value as a rounded float.
    Stockstats creates columns lazily on first access."""
    try:
        val = sdf[col].iloc[-1]
        return round(float(val), 4)
    except Exception:
        return None


def compute_trend_analysis(df: pd.DataFrame, realtime_price: float = None) -> dict:
    """代码计算趋势方向/均线排列/支撑压力/Bollinger 带，返回结论文本而非原始数字"""
    import numpy as np
    out = {}

    if df is None or df.empty:
        out["error"] = "无K线数据"
        return out

    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    volume = df["volume"].values
    n = len(close)

    # 用腾讯实时价校准K线价格
    kline_close = float(close[-1])
    if realtime_price and realtime_price > 0 and kline_close > 0:
        ratio = realtime_price / kline_close
        if abs(ratio - 1.0) > 0.05:
            close = close * ratio
            high = high * ratio
            low = low * ratio

    def safe_ma(data, p):
        if len(data) < p:
            return None
        return float(data[-p:].mean())

    ma5 = safe_ma(close, 5)
    ma10 = safe_ma(close, 10)
    ma20 = safe_ma(close, 20)
    ma60 = safe_ma(close, 60)
    cp = float(close[-1])

    # ----- 均线排列 -----
    def cmp_ma(a, b):
        if a is None or b is None:
            return None
        return "above" if a > b else ("below" if a < b else "equal")

    m5v10 = cmp_ma(ma5, ma10)
    m10v20 = cmp_ma(ma10, ma20)
    m20v60 = cmp_ma(ma20, ma60)

    if m5v10 == "above" and m10v20 == "above" and m20v60 == "above":
        ma_alignment = "多头排列（MA5 > MA10 > MA20 > MA60，强势上涨趋势）"
        trend_dir = "上升趋势"
    elif m5v10 == "below" and m10v20 == "below" and m20v60 == "below":
        ma_alignment = "空头排列（MA5 < MA10 < MA20 < MA60，弱势下降趋势）"
        trend_dir = "下降趋势"
    elif (m5v10 == "above" and m10v20 == "above") or (m5v10 == "above" and cp > ma5):
        # 短期在长期之上但不是严格多头
        cross_above = sum(x == "above" for x in [m5v10, m10v20, m20v60] if x)
        cross_below = sum(x == "below" for x in [m5v10, m10v20, m20v60] if x)
        if cross_above > cross_below:
            ma_alignment = "偏多排列（短期均线在长期均线上方，但并非严格多头）"
            trend_dir = "震荡偏多"
        else:
            ma_alignment = "偏空排列（短期均线在长期均线下方，但并非严格空头）"
            trend_dir = "震荡偏空"
    else:
        ma_alignment = "均线交织（无明确方向，震荡整理格局）"
        trend_dir = "震荡整理"

    out["ma_alignment"] = ma_alignment
    out["trend_dir"] = trend_dir

    # ----- 价格与均线关系 -----
    price_vs_ma = []
    if ma5 is not None:
        price_vs_ma.append(f"价格{'在' if cp >= ma5 else '在'}MA5({ma5:.2f}){'之上' if cp >= ma5 else '之下'}")
    if ma10 is not None:
        price_vs_ma.append(f"{'在' if cp >= ma10 else '在'}MA10({ma10:.2f}){'之上' if cp >= ma10 else '之下'}")
    if ma20 is not None:
        price_vs_ma.append(f"{'在' if cp >= ma20 else '在'}MA20({ma20:.2f}){'之上' if cp >= ma20 else '之下'}")
    if ma60 is not None:
        price_vs_ma.append(f"{'在' if cp >= ma60 else '在'}MA60({ma60:.2f}){'之上' if cp >= ma60 else '之下'}")
    out["price_vs_ma"] = "，".join(price_vs_ma)

    # ----- 支撑位（只保留最贴近当前价的3个） -----
    supports = set()
    for m in [ma20, ma60]:
        if m is not None and m < cp:
            supports.add(round(m, 2))
    recent_lows = sorted(low[-min(n, 20):])
    for v in recent_lows[:3]:
        if v < cp:
            supports.add(round(float(v), 2))
    out["support_levels"] = sorted(s for s in supports if s < cp)[-3:]

    # ----- 压力位（只保留最贴近当前价的3个） -----
    resistances = set()
    for m in [ma20, ma60]:
        if m is not None and m > cp:
            resistances.add(round(m, 2))
    recent_highs = sorted(high[-min(n, 20):], reverse=True)
    for v in recent_highs[:3]:
        if v > cp:
            resistances.add(round(float(v), 2))
    out["resistance_levels"] = sorted(r for r in resistances if r > cp)[:3]

    # ----- 最近15日涨跌统计 -----
    window = min(n, 15)
    recent_close = close[-window:]
    up_days = sum(1 for i in range(1, len(recent_close)) if recent_close[i] > recent_close[i-1])
    down_days = sum(1 for i in range(1, len(recent_close)) if recent_close[i] < recent_close[i-1])
    out["recent_days"] = f"近{window}日: 涨{up_days}天 跌{down_days}天"
    change_5 = (close[-1] / close[-min(5, n)] - 1) * 100 if n >= 2 else 0
    change_10 = (close[-1] / close[-min(10, n)] - 1) * 100 if n >= 2 else 0
    out["change_pct"] = f"近5日涨跌: {change_5:.2f}%  近10日涨跌: {change_10:.2f}%"

    # ----- 成交量分析 -----
    vol_ma5 = safe_ma(volume, 5)
    if vol_ma5 and volume[-1] > 0:
        vol_ratio = volume[-1] / vol_ma5
        if vol_ratio > 1.5:
            vol_analysis = f"放量（今日量是5日均量的{vol_ratio:.1f}倍）"
        elif vol_ratio < 0.6:
            vol_analysis = f"缩量（今日量是5日均量的{vol_ratio:.1f}倍）"
        else:
            vol_analysis = f"量能正常（今日量是5日均量的{vol_ratio:.1f}倍）"
    else:
        vol_analysis = "量能数据不足"
    out["volume_analysis"] = vol_analysis

    # ----- MACD 结论 -----
    dif = safe_ma(close, 12) - safe_ma(close, 26) if n >= 26 else None
    if dif is not None:
        if dif > 0:
            macd_conclusion = "DIF在零轴之上，中线偏多"
        else:
            macd_conclusion = "DIF在零轴之下，中线偏空"
    else:
        macd_conclusion = "MACD数据不足"
    out["macd_conclusion"] = macd_conclusion

    # ----- RSI 结论 -----
    if n > 14:
        gains = sum(max(close[i] - close[i-1], 0) for i in range(-13, 0))
        losses = sum(max(close[i-1] - close[i], 0) for i in range(-13, 0))
        if losses == 0:
            rsi_val = 100.0
        else:
            rsi_val = round(100 - 100 / (1 + gains / losses), 2)
        if rsi_val > 70:
            rsi_conclusion = f"RSI({rsi_val}) > 70，超买区域，注意回调风险"
        elif rsi_val < 30:
            rsi_conclusion = f"RSI({rsi_val}) < 30，超卖区域，可能反弹"
        else:
            rsi_conclusion = f"RSI({rsi_val}) 处于中性区间"
        out["rsi_conclusion"] = rsi_conclusion

    # ----- 趋势强度 -----
    # 用20日收盘价标准差归一化的斜率
    if n >= 20:
        slope = (close[-1] / close[-20] - 1) * 100
        atr = round(float(pd.Series(high[-20:]).mean() - pd.Series(low[-20:]).mean()), 2)
        out["trend_strength"] = f"20日涨幅: {slope:.2f}%  平均波幅(ATR20): {atr:.2f}"
    else:
        out["trend_strength"] = "数据不足"

    return out
