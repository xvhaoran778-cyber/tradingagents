import os
from datetime import datetime
from config import MEMORY_DIR, MEMORY_LOG_PATH


def ensure_dirs():
    os.makedirs(MEMORY_DIR, exist_ok=True)


def log_decision(state):
    ensure_dirs()
    decision = state.final_decision
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entry = (
        f"## {timestamp} | {state.ticker} ({state.ticker_name})\n"
        f"- 评级: {decision.rating_cn if decision else 'N/A'}\n"
        f"- 摘要: {decision.executive_summary if decision else 'N/A'}\n"
        f"- 目标价: {decision.price_target if decision and decision.price_target else 'N/A'}\n"
        f"- 周期: {decision.time_horizon if decision else 'N/A'}\n"
        f"- 风险提示: {decision.risk_warning if decision else 'N/A'}\n"
        f"---\n\n"
    )

    with open(MEMORY_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)


def get_past_context(ticker: str, max_entries: int = 3) -> str:
    if not os.path.exists(MEMORY_LOG_PATH):
        return ""
    try:
        with open(MEMORY_LOG_PATH, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return ""

    sections = content.split("\n## ")
    matched = []
    for section in sections:
        if f"| {ticker}" in section or f"({ticker})" in section:
            matched.append("## " + section.strip())

    if not matched:
        return ""

    recent = matched[-max_entries:]
    return "\n\n".join(recent)
