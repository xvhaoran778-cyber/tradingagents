from agents.base import BaseAgent
from agents.schemas import TradeProposal
from llm.prompts import TRADER_SYSTEM
from config import DEEP_MODEL


class Trader(BaseAgent):
    name = "trader"
    system_prompt = TRADER_SYSTEM

    def _build_context(self, state, **kwargs):
        plan = state.research_plan
        plan_text = (
            f"推荐: {plan.recommendation}\n"
            f"置信度: {plan.confidence}\n"
            f"理由: {plan.rationale}\n"
            f"关键风险: {', '.join(plan.key_risks)}\n"
            f"时间周期: {plan.time_horizon}"
        ) if plan else "暂无研究计划"

        return (
            f"股票: {state.ticker} ({state.ticker_name})\n\n"
            f"【研究经理投资计划】\n{plan_text}\n\n"
            f"请制定具体交易方案（JSON格式）。"
        )

    def analyze(self, state, **kwargs) -> TradeProposal:
        messages = self.build_messages(state, **kwargs)
        try:
            data = self.llm.chat_json(messages, model=self.model, temperature=0.3)
            return TradeProposal(**data)
        except Exception as e:
            text = self.llm.chat(messages, model=self.model)
            return TradeProposal(
                action="持有",
                reasoning=f"解析失败，原始输出:\n{text}",
            )
