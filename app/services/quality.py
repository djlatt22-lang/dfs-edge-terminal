"""Evidence gate: unverified lines and uncalibrated estimates cannot earn A/A+."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class MarketEvidence(BaseModel):
    sport: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    player: str = Field(min_length=1)
    market: str = Field(min_length=1)
    line: float = Field(allow_inf_nan=False)
    line_observed_at: datetime | None = None
    event_start: datetime | None = None
    sportsbook_sources: int = Field(default=0, ge=0)
    role_status: Literal['confirmed', 'uncertain', 'unknown'] = 'unknown'
    injury_checked: bool = False
    outdoor_football: bool = False
    weather_checked: bool = False
    independent_projection: bool = False
    historical_calibration_validated: bool = False

    @field_validator('line_observed_at','event_start')
    @classmethod
    def ensure_tz(cls, v):
        if v is not None and (v.tzinfo is None or v.utcoffset() is None):
            raise ValueError('timestamps must include timezone')
        return v.astimezone(timezone.utc) if v else v


def check_evidence(e: MarketEvidence, now: datetime | None = None,
                   max_age_minutes: int = 15) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now must be timezone aware')
    if max_age_minutes < 1:
        raise ValueError('max_age_minutes must be positive')
    reasons = []
    if e.line_observed_at is None:
        reasons.append('No timestamped provider line')
    elif e.line_observed_at > now:
        reasons.append('Line timestamp is in the future')
    elif (now-e.line_observed_at).total_seconds() > max_age_minutes*60:
        reasons.append('Stale provider line')
    if e.event_start is None:
        reasons.append('Event start not verified')
    elif e.event_start <= now:
        reasons.append('Event has started')
    if e.sportsbook_sources < 3:
        reasons.append('Fewer than three independent comparison books')
    if e.role_status != 'confirmed':
        reasons.append('Starting role/minutes not confirmed')
    if not e.injury_checked:
        reasons.append('Injury and availability status not checked')
    if e.outdoor_football and not e.weather_checked:
        reasons.append('Outdoor football weather not checked')
    if not e.independent_projection:
        reasons.append('No independent statistical projection; market-only consensus')
    if not e.historical_calibration_validated:
        reasons.append('No validated out-of-sample probability calibration')
    return {
        'status':'RESEARCH_ONLY' if reasons else 'EVIDENCE_READY_FOR_REVIEW',
        'certified_grade':None,
        'reasons':reasons,
        'note':'Evidence readiness is not a predicted hit rate, grade or proof of positive EV.'
    }
