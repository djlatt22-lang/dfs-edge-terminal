# Player-prop reliability upgrade

## Status (2026-11-26)

This is a **code and unit-test improvement**, not proof of a predictive advantage.
No historical forecast ledger, settled results, calibrated probabilities,
validated A/A+ grades, or production deployment is claimed.

### New endpoints

`POST /api/research/evaluate` takes `{"records": [...]}` and returns
sample sizes, MAE, RMSE, signed error, Brier score, calibration bins, ECE,
push/void counts, selected MORE/LESS results, Wilson hit-rate intervals,
and sport, market, sport-market, provider, model-version and side splits.

An example forecast row:

```json
{
  "sport": "CBB",
  "market": "player_points",
  "player": "Example Player",
  "provider": "PrizePicks",
  "model_version": "market-ensemble-v2",
  "projected_at": "2026-11-25T16:00:00Z",
  "event_start": "2026-11-25T19:00:00Z",
  "line": 15.5,
  "projection": 17.2,
  "p_over": 0.65,
  "result": 18,
  "status": "settled",
  "actual_source": "Official box score"
}
```

`POST /api/research/evidence` accepts a market line with an observed
timestamp, event start, independent sportsbook source count, role/injury
checks, outdoor weather check where relevant, independent projection,
and historical calibration validation. Missing evidence produces
`RESEARCH_ONLY` with specific reasons. Even evidence complete does not
automatically manufacture an A/A+ grade or positive EV.

### Quality protections

- A game-start timestamp must be later than the *frozen* forecast timestamp.
- Timezone-naive timestamps and non-finite prediction inputs are rejected.
- Pending and void rows are excluded from settled performance calculations.
- Pushes contribute to projection-error metrics but not binary probabilities.
- Probabilities of exactly 50% are not counted as recommended sides.
- Brier scores evaluate the forecast of OVER against the observed OVER result.
- Source counts treat each sportsbook as one independent source.
- Shared basketball/esports assist market variance is sport-specific.
- Live board and imported lines are marked `RESEARCH`, not certified A/A+;
  the previous model label is retained as `heuristic_grade` for diagnostics.
- A sportsbook consensus is a **market-derived** estimate, not independent
  offensive/defensive matchup analysis and not historically calibrated.

### Gaps requiring real data or deployment configuration

1. Durable append-only storage (Postgres or equivalent) for exact lines,
   selection decisions, source timestamps and post-event settlement.
2. Verified historical outcomes and rolling pregame injury/roster snapshots.
3. Officially authorized provider line feeds with coverage/freshness checks.
4. Walk-forward testing by event date against a naive baseline, with
   model versions frozen before evaluation.
5. Learning sigma/count distributions and calibrators on past events only,
   then testing on strictly later events by sport, market and role.
6. Evaluating joint distributions and payout rules for correlated slips.
7. Source-verified EPA/success rate, expected pace, minutes and roster feeds.
8. Deploying and monitoring the proposed code changes after review.

### Testing

```bash
pip install -r requirements.txt
python -m pytest -q
```

Local model research tests ran successfully on 2026-11-26.
An automated GitHub Actions workflow is included for PR validation.
