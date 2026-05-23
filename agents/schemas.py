from pydantic import BaseModel
from typing import Optional


class ResearchPlan(BaseModel):
    recommendation: str
    confidence: float
    rationale: str
    key_risks: list[str]
    time_horizon: str


class TradeProposal(BaseModel):
    action: str
    reasoning: str
    entry_price_range: Optional[str] = None
    position_sizing: Optional[str] = None
    stop_loss: Optional[str] = None
    target_price: Optional[str] = None


class PortfolioDecision(BaseModel):
    rating: str
    rating_cn: str
    executive_summary: str
    investment_thesis: str
    risk_warning: str
    price_target: Optional[str] = None
    time_horizon: str
