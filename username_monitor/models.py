from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Project:
    name: str
    symbol: str
    source: str
    liquidity_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    trend_score: Optional[float] = None
    url: Optional[str] = None
    raw_strength: float = 0.0


@dataclass(frozen=True)
class UsernameOpportunity:
    project: Project
    username: str
    fragment_status: str
    score: int
    reason: str
