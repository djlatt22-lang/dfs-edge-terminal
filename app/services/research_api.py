"""Stateless analysis endpoints: supply real snapshots and settled outcomes."""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from .audit import ForecastRecord, evaluate
from .quality import MarketEvidence, check_evidence

router = APIRouter(prefix='/api/research', tags=['research'])

class AuditRequest(BaseModel):
    records: list[ForecastRecord] = Field(default_factory=list, max_length=20000)

@router.post('/evaluate')
def evaluate_endpoint(body: AuditRequest):
    return evaluate(body.records)

@router.post('/evidence')
def evidence_endpoint(body: MarketEvidence):
    return check_evidence(body)
