from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.services.research_api import router

def test_research_api_endpoints():
    app=FastAPI()
    app.include_router(router)
    client=TestClient(app)
    resp=client.post('/api/research/evaluate',json={'records':[]})
    assert resp.status_code == 200
    assert resp.json()['overall']['n_total']==0
    assert resp.json()['overall']['brier_over'] is None
    evidence=client.post('/api/research/evidence',json={
        'sport':'CBB','provider':'PrizePicks','player':'X','market':'points','line':15.5
    })
    assert evidence.status_code == 200
    assert evidence.json()['status']=='RESEARCH_ONLY'
    assert evidence.json()['certified_grade'] is None
