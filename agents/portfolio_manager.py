from agents.base import BaseAgent
from agents.schemas import PortfolioDecision
from llm.prompts import PORTFOLIO_MANAGER_SYSTEM
from config import DEEP_MODEL


class PortfolioManager(BaseAgent):
    name = "portfolio_manager"
    system_prompt = PORTFOLIO_MANAGER_SYSTEM

    def _build_context(self, state, **kwargs):
        decision_input = (
            f"【技术面】\n{state.technical_report}\n\n"
            f"【情绪面】\n{state.sentiment_report}\n\n"
            f"【新闻面】\n{state.news_report}\n\n"
            f"【基本面】\n{state.fundamental_report}\n\n"
            f"【研究结论】\n"
            f"{state.research_plan.model_dump_json(indent=2) if state.research_plan else '暂无'}\n\n"
            f"【交易方案】\n"
            f"{state.trade_proposal.model_dump_json(indent=2) if state.trade_proposal else '暂无'}\n\n"
            f"【风控意见】\n"
        )
        risk_text = "\n".join(
            f"--- {r.agent} ---\n{r.assessment}" for r in state.risk_assessments
        )
        decision_input += risk_text

        past_context = state.raw_data.get("past_context", "")
        if past_context:
            decision_input += f"\n\n【历史决策参考】\n{past_context}"

        return decision_input

    def decide(self, state, **kwargs) -> PortfolioDecision:
        messages = self.build_messages(state, **kwargs)
        try:
            data = self.llm.chat_json(messages, model=self.model, temperature=0.3)
            return PortfolioDecision(**data)
        except Exception as e:
            text = self.llm.chat(messages, model=self.model)
            return PortfolioDecision(
                rating="Hold",
                rating_cn="持有",
                executive_summary=f"解析失败，参考原始输出",
                investment_thesis=text,
                risk_warning="决策过程出现异常，建议谨慎参考",
                time_horizon="短期",
            )
