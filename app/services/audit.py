"""Leakage-aware audit of timestamped player-prop predictions.

Provides descriptive scoring only. No historical accuracy is invented.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ForecastRecord(BaseModel):
    sport: str = Field(min_length=1)
    market: str = Field(min_length=1)
    player: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    projected_at: datetime
    event_start: datetime
    line: float = Field(allow_inf_nan=False)
    projection: float = Field(allow_inf_nan=False)
    p_over: float = Field(ge=0, le=1, allow_inf_nan=False)
    result: float | None = Field(default=None, allow_inf_nan=False)
    status: Literal['settled', 'pending', 'void'] = 'pending'
    actual_source: str | None = None

    @field_validator('projected_at', 'event_start')
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('timestamps must include a timezone')
        return value.astimezone(timezone.utc)

    @model_validator(mode='after')
    def consistency(self):
        if self.projected_at >= self.event_start:
            raise ValueError('forecast must precede event start (prevents look-ahead leakage)')
        if self.status == 'settled' and self.result is None:
            raise ValueError('settled rows require an actual result')
        if self.status != 'settled' and self.result is not None:
            raise ValueError('only settled rows can include an actual result')
        return self


def _wilson(wins: int, attempts: int) -> list[float] | None:
    if not attempts:
        return None
    z = 1.959963984540054
    p = wins / attempts
    d = 1 + z*z/attempts
    center = (p + z*z/(2*attempts))/d
    radius = z*math.sqrt(p*(1-p)/attempts + z*z/(4*attempts*attempts))/d
    return [round(max(0, center-radius),4), round(min(1, center+radius),4)]


def summarize(records: list[ForecastRecord]) -> dict:
    total = len(records)
    pending = sum(r.status == 'pending' for r in records)
    void = sum(r.status == 'void' for r in records)
    settled = [r for r in records if r.status == 'settled']
    pushes = [r for r in settled if r.result == r.line]
    scored = [r for r in settled if r.result != r.line]
    errors = [r.projection - r.result for r in settled]
    wins = sum((r.p_over > .5 and r.result > r.line) or
               (r.p_over < .5 and r.result < r.line) for r in scored)
    ties = sum(r.p_over == .5 for r in scored)
    resolved = len(scored) - ties
    briers = [(r.p_over - int(r.result > r.line))**2 for r in scored]
    bins = []
    weighted_error = 0.0
    for start in range(10):
        inside = [r for r in scored if min(9, int(r.p_over*10)) == start]
        if not inside:
            continue
        observed = sum(r.result > r.line for r in inside)/len(inside)
        predicted = sum(r.p_over for r in inside)/len(inside)
        weighted_error += len(inside)/len(scored) * abs(observed-predicted)
        bins.append({'bin':f'{start/10:.1f}-{(start+1)/10:.1f}',
                     'n':len(inside),'predicted_over_rate':round(predicted,4),
                     'actual_over_rate':round(observed,4)})
    return {
        'n_total':total,'n_settled':len(settled),'n_scored':len(scored),
        'n_pending':pending,'n_void':void,'n_push':len(pushes),'n_side_ties':ties,
        'mae':round(sum(abs(v) for v in errors)/len(errors),4) if errors else None,
        'rmse':round(math.sqrt(sum(v*v for v in errors)/len(errors)),4) if errors else None,
        'mean_error':round(sum(errors)/len(errors),4) if errors else None,
        'brier_over':round(sum(briers)/len(briers),5) if briers else None,
        'brier_50pct_baseline':0.25 if scored else None,
        'over_rate':round(sum(r.result>r.line for r in scored)/len(scored),4) if scored else None,
        'under_rate':round(sum(r.result<r.line for r in scored)/len(scored),4) if scored else None,
        'selected_side_wins':wins,'selected_side_n':resolved,
        'recommended_more_n':sum(r.p_over > .5 for r in scored),
        'recommended_less_n':sum(r.p_over < .5 for r in scored),
        'recommended_more_wins':sum(r.p_over > .5 and r.result > r.line for r in scored),
        'recommended_less_wins':sum(r.p_over < .5 and r.result < r.line for r in scored),
        'selected_side_hit_rate':round(wins/resolved,4) if resolved else None,
        'hit_rate_wilson95':_wilson(wins,resolved),
        'expected_calibration_error':round(weighted_error,5) if scored else None,
        'calibration_bins':bins,
    }


def evaluate(records: list[ForecastRecord]) -> dict:
    """Report descriptive historical performance, not an out-of-sample claim."""
    by_sport: dict[str,list[ForecastRecord]] = defaultdict(list)
    by_market: dict[str,list[ForecastRecord]] = defaultdict(list)
    by_sport_market: dict[str,list[ForecastRecord]] = defaultdict(list)
    by_model_version: dict[str,list[ForecastRecord]] = defaultdict(list)
    by_provider: dict[str,list[ForecastRecord]] = defaultdict(list)
    by_recommended_side: dict[str,list[ForecastRecord]] = defaultdict(list)
    for r in records:
        by_sport[r.sport].append(r)
        by_market[r.market].append(r)
        by_sport_market[f'{r.sport}::{r.market}'].append(r)
        by_model_version[r.model_version].append(r)
        by_provider[r.provider].append(r)
        by_recommended_side['MORE' if r.p_over > .5 else 'LESS' if r.p_over < .5 else 'PASS'].append(r)
    return {
        'overall':summarize(records),
        'by_sport':{k:summarize(v) for k,v in sorted(by_sport.items())},
        'by_market':{k:summarize(v) for k,v in sorted(by_market.items())},
        'by_sport_market':{k:summarize(v) for k,v in sorted(by_sport_market.items())},
        'by_model_version':{k:summarize(v) for k,v in sorted(by_model_version.items())},
        'by_provider':{k:summarize(v) for k,v in sorted(by_provider.items())},
        'by_recommended_side':{k:summarize(v) for k,v in sorted(by_recommended_side.items())},
        'interpretation':'Descriptive only. Out-of-sample validity requires pre-registered walk-forward splits and frozen pre-event forecasts.'
    }
