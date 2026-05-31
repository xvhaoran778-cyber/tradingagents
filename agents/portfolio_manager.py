import sys
from agents.base import BaseAgent
from agents.schemas import PortfolioDecision
from llm.prompts import PORTFOLIO_MANAGER_SYSTEM
from config import DEEP_MODEL


def _log(msg):
    print(f"[PM] {msg}", file=sys.stderr, flush=True)


class PortfolioManager(BaseAgent):
    name = "portfolio_manager"
    system_prompt = PORTFOLIO_MANAGER_SYSTEM

    def _build_context(self, state, **kwargs):
        parts = []
        for label, field in [
            ("技术面", state.technical_report),
            ("情绪面", state.sentiment_report),
            ("新闻面", state.news_report),
            ("基本面", state.fundamental_report),
        ]:
            parts.append(f"【{label}】\n{field or '暂无'}")

        parts.append(f"【研究结论】\n{state.research_plan.model_dump_json(indent=2) if state.research_plan else '暂无'}")
        parts.append(f"【交易方案】\n{state.trade_proposal.model_dump_json(indent=2) if state.trade_proposal else '暂无'}")

        risk_text = "\n".join(f"--- {r.agent} ---\n{r.assessment}" for r in state.risk_assessments)
        parts.append(f"【风控意见】\n{risk_text or '暂无'}")

        past = state.raw_data.get("past_context", "")
        if past:
            parts.append(f"【历史决策参考】\n{past}")

        return "\n\n".join(parts)

    def decide(self, state, on_progress=None, **kwargs) -> PortfolioDecision:
        messages = self.build_messages(state, **kwargs)
        _log(f"开始 decide(), 消息数={len(messages)}, 总字符≈{sum(len(m['content']) for m in messages)}")

        if on_progress:
            on_progress("decision", "投资组合经理正在综合研判...")

        data = self.llm.chat_json(messages, model=self.model, temperature=0.3)
        _log(f"chat_json 返回, data={str(data)[:200] if data else 'None'}")

        if data is None:
            _log("data is None, 进入文本回退")
            if on_progress:
                on_progress("decision", "JSON解析失败，使用文本输出...")
            try:
                text = self.llm.chat(messages, model=self.model)
                _log(f"文本回退成功, len={len(text) if text else 0}")
            except Exception as e:
                _log(f"文本回退也失败: {e}")
                text = f"API调用异常: {e}"
            result = PortfolioDecision(
                rating="Hold", rating_cn="持有",
                executive_summary="请参考详细分析",
                investment_thesis=text,
                risk_warning="决策过程出现异常，建议谨慎参考",
                time_horizon="短期",
            )
            _log("返回 fallback PortfolioDecision (None)")
            return result

        try:
            _log(f"尝试创建 PortfolioDecision, keys={list(data.keys())}")
            result = PortfolioDecision(**data)
            _log("PortfolioDecision 创建成功")
            if on_progress:
                on_progress("decision", "投资组合经理决策完成")
            return result
        except Exception as e:
            _log(f"PortfolioDecision 创建失败: {e}")
            if on_progress:
                on_progress("decision", f"字段解析失败: {e}")
            return PortfolioDecision(
                rating="Hold", rating_cn="持有",
                executive_summary="请参考详细分析",
                investment_thesis=str(data),
                risk_warning=str(e),
                time_horizon="短期",
            )
