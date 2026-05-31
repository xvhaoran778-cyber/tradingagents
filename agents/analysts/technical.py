from agents.base import BaseAgent
from llm.prompts import TECHNICAL_ANALYST_SYSTEM
from data.market import get_kline_data, get_technical_indicators, compute_trend_analysis
from config import DEEP_MODEL


class TechnicalAnalyst(BaseAgent):
    name = "technical"
    system_prompt = TECHNICAL_ANALYST_SYSTEM

    def _build_context(self, state, **kwargs):
        rt = state.raw_data.get("realtime", {})

        realtime_price = None
        try:
            realtime_price = float(rt.get("current", 0))
        except Exception:
            pass

        df = get_kline_data(state.ticker, count=120)
        indicators = get_technical_indicators(df, realtime_price=realtime_price)
        trend = compute_trend_analysis(df, realtime_price=realtime_price)

        current_price = realtime_price if realtime_price else rt.get("current", "N/A")
        try: current_price = round(float(current_price), 2)
        except: current_price = "N/A"

        change_pct = rt.get("change_pct", "N/A")
        pe = rt.get("pe", "N/A")
        turnover = rt.get("turnover_rate", "N/A")
        amount = rt.get("amount", 0)
        amplitude = rt.get("amplitude", "N/A")

        if change_pct != "N/A":
            try:
                cp = float(change_pct)
                price_extreme = "跌停" if cp <= -9.5 else ("涨停" if cp >= 9.5 else "正常")
            except:
                price_extreme = "正常"
        else:
            price_extreme = "正常"

        if pe != "N/A":
            try:
                pe_val = float(pe)
                pe_note = "亏损" if pe_val < 0 else ("极高(>100)" if pe_val > 100 else "正常")
            except:
                pe_note = "正常"
        else:
            pe_note = "正常"

        # ---- 均线分析 ----
        ma5 = indicators.get("ma5")
        ma10 = indicators.get("ma10")
        ma20 = indicators.get("ma20")
        ma60 = indicators.get("ma60")
        ema5 = indicators.get("ema5")
        ema10 = indicators.get("ema10")
        ema20 = indicators.get("ema20")
        ema60 = indicators.get("ema60")

        ma_text = ""
        if ma5 and ma10 and ma20 and ma60:
            ma_text = (
                f"MA5={ma5:.2f}  MA10={ma10:.2f}  MA20={ma20:.2f}  MA60={ma60:.2f}. "
                f"{trend.get('ma_alignment', '')}."
            )
            # 价格相对均线
            cp_val = float(current_price) if current_price != "N/A" else 0
            parts = []
            if cp_val >= ma5: parts.append(f"价格在MA5({ma5:.2f})之上")
            else: parts.append(f"价格跌破MA5({ma5:.2f})")
            if cp_val < ma10: parts.append(f"在MA10({ma10:.2f})之下")
            else: parts.append(f"在MA10({ma10:.2f})之上")
            if cp_val < ma20: parts.append(f"在MA20({ma20:.2f})之下")
            else: parts.append(f"在MA20({ma20:.2f})之上")
            ma_text += " ".join(parts) + "。"

        # ---- MACD ----
        dif = indicators.get("macd_dif")
        dea = indicators.get("macd_dea")
        bar = indicators.get("macd_bar")
        macd_text = ""
        if dif is not None and dea is not None and bar is not None:
            pos = "零轴之上偏多" if dif > 0 else "零轴之下偏空"
            cross = "金叉" if dif > dea else "死叉" if dif < dea else "粘合"
            bar_dir = "柱线缩短" if bar < 0 else "柱线增长"
            macd_text = f"DIF={dif:.4f} DEA={dea:.4f} BAR={bar:.4f}. DIF在{pos}，DIF与DEA{ cross}，{bar_dir}。"

        # ---- KDJ ----
        k = indicators.get("kdj_k")
        d = indicators.get("kdj_d")
        j = indicators.get("kdj_j")
        kdj_text = ""
        if k is not None and d is not None and j is not None:
            if j > 80: kdj_text = f"KDJ J={j:.1f} > 80，超买区域需警惕回调。"
            elif j < 20: kdj_text = f"KDJ J={j:.1f} < 20，超卖区域可能反弹。"
            elif j < 0: kdj_text = f"KDJ J={j:.1f} 为负值，极度超卖。"
            else: kdj_text = f"KDJ J={j:.1f} 处于中性区间。"

        # ---- RSI ----
        rsi = indicators.get("rsi")
        rsi_text = ""
        if rsi is not None:
            if rsi > 70: rsi_text = f"RSI={rsi:.1f} > 70，超买。"
            elif rsi < 30: rsi_text = f"RSI={rsi:.1f} < 30，超卖。"
            else: rsi_text = f"RSI={rsi:.1f}，中性区间。"

        # ---- 成交量 ----
        vol_text = trend.get("volume_analysis", "量能数据不足") + "。"

        # ---- 支撑/压力 ----
        sl = sorted(trend.get("support_levels", []), reverse=True)
        rl = sorted(trend.get("resistance_levels", []))
        support_text = ""
        if sl:
            support_text = f"第一支撑{sl[0]}元"
            if len(sl) > 1: support_text += f"，第二支撑{sl[1]}元"
            if len(sl) > 2: support_text += f"，第三支撑{sl[2]}元"
        else:
            support_text = "当前无明显技术支撑位"
        resistance_text = ""
        if rl:
            resistance_text = f"第一压力{rl[0]}元"
            if len(rl) > 1: resistance_text += f"，第二压力{rl[1]}元"
            if len(rl) > 2: resistance_text += f"，第三压力{rl[2]}元"
        else:
            resistance_text = "当前无明显技术压力位"

        # ---- 换手率/成交额分析 ----
        turnover_text = ""
        if turnover != "N/A":
            try:
                tv = float(turnover)
                if tv > 20:
                    turnover_text = f"换手率{tv}%极高，筹码剧烈交换"
                elif tv > 10:
                    turnover_text = f"换手率{tv}%较高，交投活跃"
                elif tv > 3:
                    turnover_text = f"换手率{tv}%正常水平"
                else:
                    turnover_text = f"换手率{tv}%偏低，交投清淡"
            except: pass

        # 构造已完成的结论（LLM只需要润色）
        ema_text = ""
        if ema5 and ema10:
            ema_text = f"EMA5={ema5:.2f}  EMA10={ema10:.2f}  EMA20={ema20:.2f}" if ema20 else f"EMA5={ema5:.2f}  EMA10={ema10:.2f}"

        conclusions = (
            f"【实时状态】价格{current_price}元，{change_pct}%（{price_extreme}），PE={pe}{'（亏损）' if '亏损' in pe_note else '' if '极高' in pe_note else ''}，{turnover_text}。\n"
            f"【均线】{ma_text}\n"
            f"【EMA】{ema_text}\n"
            f"【MACD】{macd_text}\n"
            f"【KDJ】{kdj_text}\n"
            f"【RSI】{rsi_text}\n"
            f"【成交量】{vol_text}\n"
            f"【支撑位】{support_text}\n"
            f"【压力位】{resistance_text}\n"
        )

        return conclusions


class SentimentAnalyst(BaseAgent):
    name = "sentiment"
    system_prompt = (
        "你是一位A股市场情绪分析师，擅长捕捉市场情绪变化。\n"
        "请基于提供的新闻和价格数据进行分析：\n"
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

        global_news = state.raw_data.get("global_news", [])
        global_text = "\n".join(
            f"- [{n.get('time','')}] {n.get('title','')}"
            for n in global_news[:5]
        ) if global_news else ""

        northbound = state.raw_data.get("northbound", {})
        nb_text = ""
        if northbound.get("hgt_close") is not None:
            nb_text = (f"北向资金: 沪股通净流入{northbound['hgt_close']:.2f}亿  "
                       f"深股通净流入{northbound['sgt_close']:.2f}亿")

        current_price = state.raw_data.get("realtime", {}).get("current", "N/A")
        change_pct = state.raw_data.get("realtime", {}).get("change_pct", "N/A")

        return (
            f"股票: {state.ticker} ({state.ticker_name})\n"
            f"当前价: {current_price}  涨跌幅: {change_pct}%\n\n"
            f"{nb_text}\n\n"
            f"【相关新闻】\n{news_text}\n\n"
            f"【全球资讯】\n{global_text}\n\n"
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

        reports = state.raw_data.get("research_reports", [])
        report_text = ""
        if reports:
            lines = []
            for r in reports[:3]:
                lines.append(f"- {r['date']} {r['org']}: {r['title']} (评级: {r.get('rating','N/A')})")
            report_text = "\n".join(lines)

        global_news = state.raw_data.get("global_news", [])
        global_text = "\n".join(
            f"- [{n.get('time','')}] {n.get('title','')}"
            for n in global_news[:5]
        ) if global_news else ""

        return (
            f"股票: {state.ticker} ({state.ticker_name})\n\n"
            f"【新闻资讯】\n{news_text}\n\n"
            f"【券商研报】\n{report_text if report_text else '暂无近期研报'}\n\n"
            f"【全球财经资讯】\n{global_text if global_text else '暂无'}\n\n"
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
        f10 = state.raw_data.get("f10", {})
        holder = state.raw_data.get("holder_count", [])
        dividend = state.raw_data.get("dividend", [])

        fin_text = "\n".join(f"{k}: {v}" for k, v in fin.items() if v)
        rt_text = f"PE: {realtime.get('pe','N/A')}  总市值: {realtime.get('total_market_cap','N/A')}亿"

        f10_text = ""
        for cat in ["公司概况", "分红配股", "股东结构"]:
            val = f10.get(cat, "")
            if val:
                f10_text += f"【{cat}】\n{val}\n\n"

        holder_text = ""
        if holder:
            latest_h = holder[0]
            holder_text = (f"最新股东户数: {latest_h['holder_num']}  "
                           f"环比变化: {latest_h['change_ratio']}%  "
                           f"户均持股: {latest_h['avg_shares']}")

        dividend_text = ""
        if dividend:
            d = dividend[0]
            dividend_text = f"最近分红: {d['date']} 每股派息{d['bonus_rmb']}元 转增{d['transfer_ratio']} 送{d['bonus_ratio']}"

        return (
            f"股票: {state.ticker} ({state.ticker_name})\n"
            f"所属行业: {industry}\n\n"
            f"【实时估值】\n{rt_text}\n\n"
            f"【财务数据】\n{fin_text}\n\n"
            f"【股东与分红】\n{holder_text}\n{dividend_text}\n\n"
            f"【公司资料】\n{f10_text}\n\n"
            f"请基于以上数据进行基本面分析。"
        )
