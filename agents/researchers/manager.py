from agents.base import BaseAgent
from agents.schemas import ResearchPlan
from llm.prompts import RESEARCH_MANAGER_SYSTEM
from config import DEEP_MODEL


class ResearchManager(BaseAgent):
    name = "research_manager"
    system_prompt = RESEARCH_MANAGER_SYSTEM

    def _build_context(self, state, **kwargs):
        debate_text = "\n\n".join(
            f"第{i+1}轮辩论:\n多头: {r.bull_argument}\n空头: {r.bear_argument}"
            for i, r in enumerate(state.debate_history)
        )

        return (
            f"股票: {state.ticker} ({state.ticker_name})\n\n"
            f"【辩论记录】\n{debate_text}\n\n"
            f"请综合多空双方观点，给出客观的研究结论（JSON格式）。"
        )

    def analyze(self, state, **kwargs) -> ResearchPlan:
        messages = self.build_messages(state, **kwargs)
        try:
            data = self.llm.chat_json(messages, model=self.model, temperature=0.3)
            return ResearchPlan(**data)
        except Exception as e:
            text = self.llm.chat(messages, model=self.model)
            return ResearchPlan(
                recommendation="持有",
                confidence=0.5,
                rationale=f"解析失败，使用原始输出:\n{text}",
                key_risks=["无法获取结构化输出"],
                time_horizon="短期",
            )
