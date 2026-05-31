import sys
from llm.client import LLMClient
from workflow.state import AgentState, DebateRound, RiskAssessment
from agents.analysts.technical import TechnicalAnalyst, SentimentAnalyst, NewsAnalyst, FundamentalAnalyst
from agents.researchers.bull import BullResearcher
from agents.researchers.bear import BearResearcher
from agents.researchers.manager import ResearchManager
from agents.trader.trader import Trader
from agents.risk.aggressive import AggressiveRisk
from agents.risk.conservative import ConservativeRisk
from agents.risk.neutral import NeutralRisk
from agents.portfolio_manager import PortfolioManager
from data.market import get_kline_data, get_technical_indicators, get_industry, get_stock_name
from data.realtime import get_realtime_quote
from data.news import get_all_news, get_global_news
from data.fundamentals import get_financial_data, get_f10_data, get_sina_financial_statements
from data.signals import (get_money_flow_minute, get_money_flow_120d, get_margin,
    get_block_trade, get_research_reports, get_dragon_tiger, get_lockup_expiry,
    get_industry_comparison, get_baidu_kline, get_holder_count, get_dividend_history,
    get_concept_blocks, get_northbound_realtime, get_hot_stocks)
from data.filings import get_cninfo_announcements, get_f10_latest_notice
from memory.logger import log_decision, get_past_context
from config import MAX_DEBATE_ROUNDS


def _log(msg):
    print(f"[PIPELINE] {msg}", file=sys.stderr, flush=True)


class TradingPipeline:
    def __init__(self):
        self.llm = LLMClient()
        self._init_agents()

    def _init_agents(self):
        self.analysts = [
            TechnicalAnalyst(self.llm),
            SentimentAnalyst(self.llm),
            NewsAnalyst(self.llm),
            FundamentalAnalyst(self.llm),
        ]
        self.bull = BullResearcher(self.llm)
        self.bear = BearResearcher(self.llm)
        self.research_manager = ResearchManager(self.llm)
        self.trader = Trader(self.llm)
        self.risk_team = [
            AggressiveRisk(self.llm),
            ConservativeRisk(self.llm),
            NeutralRisk(self.llm),
        ]
        self.pm = PortfolioManager(self.llm)

    def _collect_data(self, state: AgentState):
        ticker = state.ticker
        state.ticker_name = get_stock_name(ticker) or ticker
        state.raw_data["industry"] = get_industry(ticker)
        state.raw_data["kline"] = get_kline_data(ticker)
        state.raw_data["indicators"] = get_technical_indicators(state.raw_data["kline"])
        state.raw_data["realtime"] = get_realtime_quote(ticker)
        state.raw_data["news"] = get_all_news(ticker)
        state.raw_data["global_news"] = get_global_news()
        state.raw_data["fundamentals"] = get_financial_data(ticker)
        state.raw_data["f10"] = get_f10_data(ticker)
        state.raw_data["sina_statements"] = get_sina_financial_statements(ticker)
        state.raw_data["past_context"] = get_past_context(ticker)

        # 信号层 + 资金面
        state.raw_data["money_flow"] = get_money_flow_minute(ticker)
        state.raw_data["money_flow_120d"] = get_money_flow_120d(ticker)
        state.raw_data["margin"] = get_margin(ticker)
        state.raw_data["block_trade"] = get_block_trade(ticker)
        state.raw_data["research_reports"] = get_research_reports(ticker)
        state.raw_data["dragon_tiger"] = get_dragon_tiger(ticker)
        state.raw_data["lockup"] = get_lockup_expiry(ticker)
        state.raw_data["holder_count"] = get_holder_count(ticker)
        state.raw_data["dividend"] = get_dividend_history(ticker)
        state.raw_data["industry_rank"] = get_industry_comparison()
        state.raw_data["concept_blocks"] = get_concept_blocks(ticker)
        state.raw_data["northbound"] = get_northbound_realtime()
        state.raw_data["hot_stocks"] = get_hot_stocks()
        state.raw_data["baidu_kline"] = get_baidu_kline(ticker)

        # 公告层
        state.raw_data["announcements"] = get_cninfo_announcements(ticker)
        state.raw_data["latest_notice"] = get_f10_latest_notice(ticker)

    def _phase_analysts(self, state: AgentState):
        for analyst in self.analysts:
            print(f"  📊 运行 {analyst.name} 分析师...")
            report = analyst.analyze(state)
            attr_map = {
                "technical": "technical_report",
                "sentiment": "sentiment_report",
                "news": "news_report",
                "fundamental": "fundamental_report",
            }
            setattr(state, attr_map[analyst.name], report)

    def _phase_debate(self, state: AgentState):
        for round_num in range(MAX_DEBATE_ROUNDS):
            print(f"  💬 研究员辩论第 {round_num + 1} 轮...")
            bull_arg = self.bull.analyze(state, round_num=round_num)
            bear_arg = self.bear.analyze(state, round_num=round_num)
            state.debate_history.append(DebateRound(bull_argument=bull_arg, bear_argument=bear_arg))

        print("  📋 研究经理综合结论...")
        state.research_plan = self.research_manager.analyze(state)

    def _phase_trader(self, state: AgentState):
        print("  💼 交易员制定方案...")
        state.trade_proposal = self.trader.analyze(state)

    def _phase_risk(self, state: AgentState):
        for risk_agent in self.risk_team:
            print(f"  🛡️ {risk_agent.name} 评估风险...")
            assessment = risk_agent.analyze(state)
            state.risk_assessments.append(RiskAssessment(
                agent=risk_agent.name,
                assessment=assessment,
            ))

    def _phase_portfolio_manager(self, state: AgentState, on_progress=None):
        print("  🏛️ 投资组合经理做出最终决策...")
        state.final_decision = self.pm.decide(state, on_progress=on_progress)

    def run(self, ticker: str, on_progress=None) -> AgentState:
        state = AgentState(ticker=ticker)

        if on_progress:
            on_progress("collect", f"正在采集 {ticker} 数据...")
        self._collect_data(state)
        if on_progress:
            on_progress("collect", "数据采集完成")

        if on_progress:
            on_progress("analysts", "技术分析师分析中...")
        self._phase_analysts(state)
        if on_progress:
            on_progress("analysts", "分析师团队完成")

        if on_progress:
            on_progress("debate", "研究员辩论中...")
        self._phase_debate(state)
        if on_progress:
            on_progress("debate", "研究员辩论完成")

        if on_progress:
            on_progress("trader", "交易员制定方案...")
        self._phase_trader(state)
        if on_progress:
            on_progress("trader", "交易方案完成")

        if on_progress:
            on_progress("risk", "风控评估中...")
        self._phase_risk(state)
        if on_progress:
            on_progress("risk", "风险评估完成")

        if on_progress:
            on_progress("decision", "投资组合经理决策中...")
        self._phase_portfolio_manager(state, on_progress=on_progress)
        _log("_phase_portfolio_manager 完成")
        if on_progress:
            on_progress("decision", "最终决策完成")

        _log("开始 log_decision")
        log_decision(state)
        _log("log_decision 完成")

        if on_progress:
            on_progress("done", "分析完成")
        _log("run() 返回 state")

        return state
