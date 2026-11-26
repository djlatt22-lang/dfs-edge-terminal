from datetime import datetime, timezone, timedelta
import pytest
from pydantic import ValidationError
from app.services.audit import ForecastRecord, evaluate
from app.services.quality import MarketEvidence, check_evidence

BASE = datetime(2026,11,25,18,tzinfo=timezone.utc)

def row(**kwargs):
    data = dict(sport='CBB', market='points', player='Example Player',
                provider='PrizePicks', model_version='v0', projected_at=BASE,
                event_start=BASE + timedelta(hours=3), line=15.5,
                projection=17.2, p_over=.7, status='settled',result=18,
                actual_source='Official box score')
    data.update(kwargs)
    return ForecastRecord(**data)

def test_metrics_scoring_and_splits():
    r=[row(),row(player='Second',result=14,p_over=.2,projection=13,market='assists'),
       row(player='Push',line=15,projection=17,result=15,p_over=.7),
       row(player='Void',status='void',result=None),
       row(player='Pending',status='pending',result=None)]
    o=evaluate(r)
    s=o['overall']
    assert s['n_total']==5 and s['n_settled']==3 and s['n_scored']==2
    assert s['n_void']==1 and s['n_pending']==1 and s['n_push']==1
    assert s['selected_side_wins']==2 and s['selected_side_hit_rate']==1
    assert abs(s['brier_over']-0.065)<1e-9
    assert s['mae']==round((.8+1+2)/3,4)
    assert s['over_rate']==.5 and s['under_rate']==.5
    assert 'CBB::assists' in o['by_sport_market']
    assert s['hit_rate_wilson95'][0] < 1

def test_no_outcomes_no_fake_stats():
    o=evaluate([row(status='pending',result=None)])['overall']
    assert o['mae'] is None and o['brier_over'] is None
    assert o['selected_side_hit_rate'] is None

@pytest.mark.parametrize('patch',[
    {'projected_at':BASE+timedelta(hours=5)},
    {'projected_at':datetime(2026,11,25)},
    {'status':'settled','result':None},
    {'status':'pending','result':20},
    {'p_over':1.2},
])
def test_reject_unsupported_or_leaked_rows(patch):
    with pytest.raises(ValidationError): row(**patch)

def test_side_tie_not_counted_as_pick():
    s=evaluate([row(p_over=.5)])['overall']
    assert s['n_side_ties']==1 and s['selected_side_n']==0
    assert s['brier_over']==.25

def test_evidence_gate_and_timezone():
    now=BASE
    e=MarketEvidence(sport='NFL',provider='PrizePicks',player='Example',market='pass_yds',
                     line=249.5,line_observed_at=now-timedelta(minutes=20),
                     event_start=now+timedelta(hours=2),sportsbook_sources=2,
                     role_status='confirmed',injury_checked=True,outdoor_football=True)
    o=check_evidence(e,now)
    assert o['status']=='RESEARCH_ONLY'
    assert 'Stale provider line' in o['reasons']
    assert 'Outdoor football weather not checked' in o['reasons']
    assert o['certified_grade'] is None
    with pytest.raises(ValidationError):
        MarketEvidence(sport='NFL',provider='P',player='X',market='Y',line=1,
                       line_observed_at=datetime(2026,11,25))

def test_evidence_ready_does_not_claim_grade():
    now=BASE
    e=MarketEvidence(sport='NBA',provider='PrizePicks',player='Example',market='points',
                     line=19.5,line_observed_at=now-timedelta(minutes=2),
                     event_start=now+timedelta(hours=2),sportsbook_sources=4,
                     role_status='confirmed',injury_checked=True,
                     independent_projection=True,historical_calibration_validated=True)
    result=check_evidence(e,now)
    assert result['status']=='EVIDENCE_READY_FOR_REVIEW'
    assert result['certified_grade'] is None
