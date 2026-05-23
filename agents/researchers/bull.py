from agents.base import BaseAgent
from llm.prompts import BULL_RESEARCHER_SYSTEM
from config import DEEP_MODEL


class BullResearcher(BaseAgent):
    name = "bull"
    system_prompt = BULL_RESEARCHER_SYSTEM

    def _build_context(self, state, **kwargs):
        round_num = kwargs.get("round_num", 0)
        reports = (
            f"【技术分析师报告】\n{state.technical_report}\n\n"
            f"【情绪分析师报告】\n{state.sentiment_report}\n\n"
            f"【新闻分析师报告】\n{state.news_report}\n\n"
            f"【基本面分析师报告】\n{state.fundamental_report}\n"
        )

        debate_history = ""
        for i, round_ in enumerate(state.debate_history):
            debate_history += (
                f"\n--- 第{i+1}轮辩论 ---\n"
                f"多头: {round_.bull_argument}\n"
                f"空头: {round_.bear_argument}\n"
            )

        return (
            f"股票: {state.ticker} ({state.ticker_name})\n"
            f"当前辩论轮次: 第{round_num + 1}轮\n\n"
            f"【分析师报告】\n{reports}\n"
            f"{'【历史辩论】' + debate_history if debate_history else ''}\n\n"
            f"请基于以上信息，从多头立场构建你的看多论证。"
        )
