from dataclasses import dataclass, field
from typing import Optional
from agents.schemas import ResearchPlan, TradeProposal, PortfolioDecision


@dataclass
class DebateRound:
    bull_argument: str
    bear_argument: str


@dataclass
class RiskAssessment:
    agent: str
    assessment: str


@dataclass
class AgentState:
    ticker: str
    ticker_name: str = ""

    technical_report: str = ""
    sentiment_report: str = ""
    news_report: str = ""
    fundamental_report: str = ""

    debate_history: list[DebateRound] = field(default_factory=list)
    research_plan: Optional[ResearchPlan] = None

    trade_proposal: Optional[TradeProposal] = None

    risk_assessments: list[RiskAssessment] = field(default_factory=list)

    final_decision: Optional[PortfolioDecision] = None

    raw_data: dict = field(default_factory=dict)
    error: Optional[str] = None
