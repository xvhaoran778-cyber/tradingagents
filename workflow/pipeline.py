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
from data.news import get_all_news
from data.fundamentals import get_financial_data
from memory.logger import log_decision, get_past_context
from config import MAX_DEBATE_ROUNDS


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
        state.raw_data["fundamentals"] = get_financial_data(ticker)
        state.raw_data["past_context"] = get_past_context(ticker)

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

    def _phase_portfolio_manager(self, state: AgentState):
        print("  🏛️ 投资组合经理做出最终决策...")
        state.final_decision = self.pm.decide(state)

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
        self._phase_portfolio_manager(state)
        if on_progress:
            on_progress("decision", "最终决策完成")

        log_decision(state)
        if on_progress:
            on_progress("done", "分析完成")

        return state
