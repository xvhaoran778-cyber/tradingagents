import json
import sqlite3
from datetime import datetime
from pathlib import Path
from workflow.state import AgentState

DB_DIR = Path.home() / ".trading-agent"
DB_PATH = DB_DIR / "history.db"


def _get_db():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT NOT NULL,
            ticker_name TEXT DEFAULT '',
            search_input TEXT DEFAULT '',
            created_at  TEXT NOT NULL,
            state_json  TEXT NOT NULL
        )
    """)
    return conn


def save_analysis(state: AgentState, raw_input: str = ""):
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO analyses (ticker, ticker_name, search_input, created_at, state_json) VALUES (?, ?, ?, ?, ?)",
            (state.ticker, state.ticker_name or "", raw_input,
             datetime.now().isoformat(), _state_to_json(state))
        )
        conn.commit()
    finally:
        conn.close()


def get_history(limit: int = 20) -> list[dict]:
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT id, ticker, ticker_name, search_input, created_at FROM analyses ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_analysis(analysis_id: int) -> dict | None:
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["state"] = json.loads(result.pop("state_json"))
        return result
    finally:
        conn.close()


def _state_to_json(state: AgentState) -> str:
    data = {
        "ticker": state.ticker,
        "ticker_name": state.ticker_name,
        "final_decision": _model_dump(state.final_decision),
        "research_plan": _model_dump(state.research_plan),
        "trade_proposal": _model_dump(state.trade_proposal),
        "risk_assessments": [
            {"agent": r.agent, "assessment": r.assessment}
            for r in state.risk_assessments
        ],
        "reports": {
            "technical": state.technical_report,
            "sentiment": state.sentiment_report,
            "news": state.news_report,
            "fundamental": state.fundamental_report,
        },
        "raw_data": {
            "industry": state.raw_data.get("industry", ""),
            "realtime": state.raw_data.get("realtime", {}),
            "news": state.raw_data.get("news", []),
        },
    }
    return json.dumps(data, ensure_ascii=False, default=str)


def _model_dump(value):
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {k: _model_dump(v) for k, v in value.items()}
    return value
