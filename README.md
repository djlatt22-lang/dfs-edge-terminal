# DFS Edge Terminal

A deployable DFS projection dashboard for PrizePicks, Underdog, Dabble and DraftKings Pick6, with a universal import path for esports and niche markets.

## What it does

- Dynamically discovers active sports, events and player-prop markets.
- Pulls DFS lines through The Odds API's `us_dfs` coverage.
- Pulls matching sportsbook prop prices and removes the two-way vig.
- Converts fair Over/Under prices into implied statistical means.
- Ensembles multiple books with modest source weighting.
- Scores More/Less probability, raw edge, standardized edge, confidence and an A+/A/B/C model-strength label.
- Shows the sportsbook evidence behind each projection.
- Supports live PrizePicks / Underdog / Dabble / DraftKings Pick6 where the upstream feed has coverage.
- Adds PandaScore-powered esports fixture/stat endpoints plus a CSV importer so CS2 / LoL / Dota 2 / Valorant and other DFS boards can be analyzed even when the aggregator does not expose their lines.
- Runs in demo mode with no keys, so the UI can be evaluated immediately.

## Quick start

```bash
cp .env.example .env
# Put your API keys in .env
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://localhost:8000`.

Or with Docker:

```bash
cp .env.example .env
docker compose up --build
```

## API keys

### `ODDS_API_KEY`
Used for current sports, events, DFS sites and sportsbook comparison markets. The app discovers event markets first and only requests the player-prop markets currently seen for DFS books. This reduces false assumptions about what is available on a given slate.

### `PANDASCORE_TOKEN`
Optional. Used for esports schedules and historical/player-stat endpoints. Deep historical player stats require an eligible PandaScore plan.

## Data architecture

`DFS source line -> matching sportsbook O/U pairs -> de-vig -> fair P(over) -> implied mean -> weighted consensus projection -> P(More/Less at DFS line)`

If an O/U pair has fair Over probability `p` at line `L` and the market's calibrated standard deviation is `sigma`, the implied mean is approximated by:

`mu = L + sigma * Φ^-1(p)`

The final DFS probability is then estimated from the ensemble mean and variance.

## Important modeling note

The included variance table is a sensible baseline for software demonstration and early model development, not a claim that one variance fits every athlete, league, role or game state. For production use, replace these priors with backtested distributions by sport/stat/role and add your own feature models (usage, pace, EPA, success rate, DvP, injuries, weather, projected minutes, starting lineup, opponent scheme, map pool, etc.).

## Universal import format

Paste or upload CSV with:

```csv
provider,sport,player,market,line,projection,sigma,matchup,notes
PrizePicks,Esports - CS2,Player Name,kills_maps_1_2,31.5,34.1,5.8,Team A vs Team B,Example
```

`projection` is optional. If omitted, the row is left unscored rather than inventing a projection.

## Recommended production upgrades

1. Add PostgreSQL for snapshots, closing-line tracking and backtests.
2. Calibrate sigma and probability bins from settled historical props.
3. Blend market-implied projections with independent sport-specific models.
4. Add injury/lineup/weather/pace/opponent feeds.
5. Add authentication, user watchlists and saved slips.
6. Add scheduled ingestion with a queue (Celery/RQ) and Redis cache.
7. Add stale-line detection and provider-specific alternate-line / multiplier modeling.
8. Add observability and API-credit budgeting.

## Legal / operational note

This project intentionally uses authorized API integrations and import workflows rather than relying on undocumented scraping. Make sure your deployment complies with provider terms, local law, DFS age restrictions and applicable contest rules.
