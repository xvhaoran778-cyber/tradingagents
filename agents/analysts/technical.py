from agents.base import BaseAgent
from llm.prompts import TECHNICAL_ANALYST_SYSTEM
from data.market import get_kline_data, get_technical_indicators
from config import DEEP_MODEL


class TechnicalAnalyst(BaseAgent):
    name = "technical"
    system_prompt = TECHNICAL_ANALYST_SYSTEM

    def _build_context(self, state, **kwargs):
        df = get_kline_data(state.ticker, count=120)
        indicators = get_technical_indicators(df)

        kline_summary = ""
        if df is not None and not df.empty:
            recent = df.tail(5)
            rows = []
            for _, r in recent.iterrows():
                rows.append(
                    f"日期:{r.get('date','')} 开:{r.get('open',0):.2f} "
                    f"高:{r.get('high',0):.2f} 低:{r.get('low',0):.2f} "
                    f"收:{r.get('close',0):.2f} 量:{r.get('volume',0):.0f}"
                )
            kline_summary = "\n".join(rows)

        tech_text = "\n".join(f"{k}: {v}" for k, v in indicators.items() if v is not None)

        return (
            f"股票代码: {state.ticker} ({state.ticker_name})\n\n"
            f"【最近5日K线数据】\n{kline_summary}\n\n"
            f"【技术指标】\n{tech_text}\n\n"
            f"请基于以上数据进行技术分析。"
        )


class SentimentAnalyst(BaseAgent):
    name = "sentiment"
    system_prompt = (
        "你是一位A股市场情绪分析师，擅长捕捉市场情绪变化。\n"
        "请基于提供的新闻和社交媒体信息进行分析：\n"
        "1. 整体市场情绪判断（乐观/中性/悲观）\n"
        "2. 情绪强度评估\n"
        "3. 主要情绪驱动因素分析\n"
        "4. 市场关注焦点\n"
        "5. 情绪与价格走势的背离情况\n\n"
        "请用中文给出详细分析报告，最后给出明确的市场情绪结论。"
    )

    def _build_context(self, state, **kwargs):
        news_list = state.raw_data.get("news", [])
        news_text = "\n".join(
            f"- [{n.get('time','')}] {n.get('title','')}: {n.get('summary','')}"
            for n in news_list[:10]
        ) if news_list else "暂无新闻数据"

        current_price = state.raw_data.get("realtime", {}).get("current", "N/A")
        change_pct = state.raw_data.get("realtime", {}).get("change_pct", "N/A")

        return (
            f"股票: {state.ticker} ({state.ticker_name})\n"
            f"当前价: {current_price}  涨跌幅: {change_pct}%\n\n"
            f"【相关新闻】\n{news_text}\n\n"
            f"请基于以上信息分析市场情绪。"
        )


class NewsAnalyst(BaseAgent):
    name = "news"
    system_prompt = (
        "你是一位专业的A股新闻分析师。\n"
        "请基于提供的新闻资讯进行分析：\n"
        "1. 公司层面新闻（公告、业绩、合同、股东变化等）\n"
        "2. 行业政策新闻及其影响\n"
        "3. 宏观经济环境变化\n"
        "4. 新闻事件的性质（利好/利空/中性）\n"
        "5. 对股价的潜在影响程度和持续时间\n\n"
        "请用中文给出详细分析报告，最后给出明确的新闻面判断结论。"
    )

    def _build_context(self, state, **kwargs):
        news_list = state.raw_data.get("news", [])
        news_text = "\n".join(
            f"[{n.get('time','')}] {n.get('title','')}\n"
            f"来源: {n.get('source','')}\n"
            f"摘要: {n.get('summary','')}\n"
            for n in news_list[:15]
        ) if news_list else "暂无新闻数据"

        return (
            f"股票: {state.ticker} ({state.ticker_name})\n\n"
            f"【新闻资讯】\n{news_text}\n\n"
            f"请对以上新闻进行深入分析，评估对股价的影响。"
        )


class FundamentalAnalyst(BaseAgent):
    name = "fundamental"
    system_prompt = (
        "你是一位专业的A股基本面分析师。\n"
        "请基于提供的财务数据和基本面信息进行分析：\n"
        "1. 盈利能力：毛利率、净利率、ROE等指标分析\n"
        "2. 成长性：营收增长、利润增长趋势\n"
        "3. 估值水平：PE、PB等估值指标的合理性\n"
        "4. 财务健康度：资产负债率、现金流状况\n"
        "5. 行业地位和竞争优势\n\n"
        "请用中文给出详细分析报告，最后给出明确的基本面判断结论。"
    )

    def _build_context(self, state, **kwargs):
        fin = state.raw_data.get("fundamentals", {})
        realtime = state.raw_data.get("realtime", {})
        industry = state.raw_data.get("industry", "未知")

        fin_text = "\n".join(f"{k}: {v}" for k, v in fin.items() if v)
        rt_text = f"PE: {realtime.get('pe','N/A')}  总市值: {realtime.get('total_market_cap','N/A')}亿"

        return (
            f"股票: {state.ticker} ({state.ticker_name})\n"
            f"所属行业: {industry}\n\n"
            f"【实时估值】\n{rt_text}\n\n"
            f"【财务数据】\n{fin_text}\n\n"
            f"请基于以上数据进行基本面分析。"
        )
