from agents.base import BaseAgent
from llm.prompts import RISK_NEUTRAL_SYSTEM
from config import DEEP_MODEL


class NeutralRisk(BaseAgent):
    name = "risk_neutral"
    system_prompt = RISK_NEUTRAL_SYSTEM

    def _build_context(self, state, **kwargs):
        proposal = state.trade_proposal
        proposal_text = (
            f"操作: {proposal.action}\n"
            f"理由: {proposal.reasoning}\n"
            f"入场区间: {proposal.entry_price_range}\n"
            f"仓位: {proposal.position_sizing}\n"
            f"止损: {proposal.stop_loss}\n"
            f"目标: {proposal.target_price}"
        ) if proposal else "暂无交易方案"

        return (
            f"股票: {state.ticker} ({state.ticker_name})\n\n"
            f"【交易方案】\n{proposal_text}\n\n"
            f"请从中立型风控角度客观评估该方案的风险。"
        )
