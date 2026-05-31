"""东财妙想金融数据封装 — 查询真实技术指标，禁止 LLM 推算

使用东方财富权威数据库返回预计算的技术指标，避免 LLM 编造 MA/MACD/KDJ。
"""
import os
import sys
import json
import requests
from data.cache import cached
from data.miaoxiang_data import MXData, table_to_rows
from config import detect_market


@cached(ttl=120)
def get_mx_realtime(code: str) -> dict:
    """获取个股实时行情 + 估值（妙想API，自然语言查询）"""
    name = _resolve_name(code)
    query = f"{name}({code})最新价 涨跌幅 今开 昨收 最高 最低 成交量 成交额 换手率 PE PB 总市值 流通市值 量比 振幅 涨停价 跌停价"
    return _mx_query_single(query)


@cached(ttl=300)
def get_mx_technical_indicators(code: str) -> dict:
    """获取完整的预计算技术指标（MA/MACD/KDJ/RSI等）"""
    name = _resolve_name(code)
    query = (f"{name}({code})最新收盘价 MA5 MA10 MA20 MA60 "
             f"MACD_DIF MACD_DEA MACD_BAR KDJ_K KDJ_D KDJ_J RSI 换手率 量比")
    return _mx_query_single(query)


@cached(ttl=300)
def get_mx_kline(code: str, days: int = 20) -> list[dict]:
    """获取最近N日K线数据（OHLCV）"""
    name = _resolve_name(code)
    query = f"{name}({code})近{days}个交易日开盘价 收盘价 最高价 最低价 成交量"
    result = _mx_query(query)
    return result.get("rows", [])


@cached(ttl=120)
def get_mx_money_flow(code: str) -> dict:
    """获取主力资金流向"""
    name = _resolve_name(code)
    query = f"{name}({code})今日主力净流入 超大单净流入 大单净流入 中单净流入 小单净流入"
    return _mx_query_single(query)


@cached(ttl=600)
def get_mx_financial(code: str) -> dict:
    """获取财务指标"""
    name = _resolve_name(code)
    query = f"{name}({code})最新净利润 营业收入 每股收益 ROE 毛利率 净利率 资产负债率"
    return _mx_query_single(query)


@cached(ttl=3600)
def get_mx_f10(code: str) -> dict:
    """获取公司基本信息"""
    name = _resolve_name(code)
    query = f"{name}({code})总股本 流通股本 所属行业 上市日期 董事长 主营业务"
    return _mx_query_single(query)


def _resolve_name(code: str) -> str:
    """尝试获取股票名称，失败则用代码"""
    try:
        from data.market import get_stock_name
        name = get_stock_name(code)
        if name:
            return name
    except Exception:
        pass
    return code


def _mx_query_single(query: str) -> dict:
    """执行妙想查询并返回单行结果字典"""
    result = _mx_query(query)
    rows = result.get("rows", [])
    if rows:
        return {k: v for k, v in rows[0].items() if not k.startswith("_")}
    return {}


def _mx_query(query: str) -> dict:
    """执行妙想API查询，返回结构化表格数据"""
    api_key = os.getenv("MX_APIKEY")
    if not api_key:
        return {"rows": [], "error": "MX_APIKEY not configured"}

    try:
        mx = MXData(api_key=api_key)
        resp = mx.query(query)

        tables, _, total_rows, err = mx.parse_result(resp)
        if err or not tables:
            return {"rows": [], "error": err or "no data"}

        return {"rows": tables[0]["rows"], "total": total_rows}
    except Exception as e:
        return {"rows": [], "error": str(e)}
