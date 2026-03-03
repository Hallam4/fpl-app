# FPL Advisor

**Live app: https://fpl-app-1.onrender.com**

A Fantasy Premier League web app that analyses your squad and helps you make better decisions.

![Stack](https://img.shields.io/badge/backend-FastAPI-009688?style=flat-square) ![Stack](https://img.shields.io/badge/frontend-React%20%2B%20Vite-646CFF?style=flat-square)

## Features

- **Squad view** — your current 15 players with form, cost, and injury status
- **Transfer recommender** — simulation-powered sell/buy suggestions with 3-GW projected points and -4 hit break-even analysis
- **Captain picker** — top 3 captain options ranked by Student-t expected points with P90 upside
- **Chip strategy advisor** — best gameweeks for Bench Boost, Triple Captain, and Free Hit across a 10-GW window
- **Fixture difficulty heatmap** — next 6 GW FDR for all Premier League teams, with your squad highlighted
- **Monte Carlo simulation** — 10,000-run points distribution for the next GW using t-copula with antithetic variates, stratified sampling, and control variates
- **10-GW player projections** — all-player expected points heatmap with per-player detail drilldowns
- **Prediction calibration** — Brier score tracking to measure forecast accuracy over time
- **Live GW tracker** — real-time points for your squad during active gameweeks
- **WhatsApp notifications** — live goal/assist/clean sheet alerts via Twilio

No login required — just enter your public FPL team ID.

## Getting started

### Prerequisites

- Python 3.10+
- Node 18+

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
# API running at http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# App running at http://localhost:5173
```

Open http://localhost:5173, enter your FPL team ID (found in the URL on the FPL website: `/entry/YOUR_ID/`), and explore the tabs.

## How it works

### Transfer recommender

Each squad player is fitted to a **Student-t distribution** from their last 5 GW points using `scipy.stats.t.fit`. The fitted parameters `(mu, sigma, df)` are scaled by fixture difficulty rating (FDR) for the next 3 gameweeks:

```
fdr_scale = (6 - fdr) / 3.0
expected_gw = max(0, mu * fdr_scale)
sell_3gw = sum of expected over 3 GWs
```

Candidates are scored using a lightweight fit from bootstrap data (form/points_per_game) to avoid expensive API calls. The top 5 transfers by `buy_3gw - sell_3gw` (threshold >= 0.5 pts) are returned.

#### Hit analysis (-4 break-even)

For each recommended transfer, 1,000 antithetic + stratified Student-t samples are drawn per gameweek to compute:

- **1-GW break-even probability** — `P(buy_pts - sell_pts > 4)` for just the next GW
- **3-GW break-even probability** — `P(sum_buy_3gw - sum_sell_3gw > 4)` over 3 GWs
- **Expected net (1-GW and 3-GW)** — `E[buy - sell] - 4`

This tells you the probability that a -4 hit pays off immediately vs over a 3-GW window.

### Captain picker

For each non-GK squad player:

1. Fit Student-t from last 5 GWs (via batch API fetch of 15 player summaries)
2. Scale by next-GW FDR: `expected_pts = max(0, mu * (6 - fdr) / 3.0)`
3. Compute P90 analytically: `p90 = max(0, mu_scaled + sigma * t.ppf(0.9, df))`

Ranked by simulation expected points. Shows expected, P90 upside, and form.

### Chip strategy advisor

Analyses the next 10 gameweeks to recommend optimal chip timing:

- **Bench Boost (BB)** — sum of bench players' FDR-scaled expected points per GW. Best when bench players have easy fixtures.
- **Triple Captain (TC)** — best squad player's FDR-scaled expected per GW (the extra 1x captain value). Best when a top player has a very easy fixture.
- **Free Hit (FH)** — top 11 from all players (by form) minus your current XI, per GW. Best when your squad has blanks or tough fixtures.

Each chip is ranked across all 10 GWs (rank 1 = best GW for that chip). Summary cards show the best GW for each chip with point values; the breakdown table shows all 10 GWs colour-coded by rank.

### Monte Carlo simulation

The team simulation (10,000 runs) uses several variance-reduction techniques stacked together:

1. **Student-t fitting** — `scipy.stats.t.fit` on last 5 GW points per player (captures heavy tails better than Gaussian)
2. **t-copula** — Cholesky-correlated draws give realistic tail dependence between same-team players (ρ = 0.35)
3. **Stratified sampling** — 50 strata partition [0,1] for more uniform coverage
4. **Antithetic variates** — U and 1-U paired to halve variance
5. **Control variate** — analytical mean correction using known fitted distributions

### 10-GW player projections

For every active player in the league (~700), fits Student-t from history and projects expected points across the next 10 GWs with FDR scaling per fixture. Uses the same stratified + antithetic variance reduction as the team sim.

Results shown as a heatmap (green = high expected, gray = blank GW). Click any player row for a detailed single-player simulation with histogram and percentile stats.

## API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/team/{team_id}` | GET | Squad, bank, current GW |
| `/api/transfers/{team_id}` | GET | Top 5 transfer recs with hit analysis |
| `/api/captain/{team_id}` | GET | Top 3 captain picks with expected + P90 |
| `/api/chips/{team_id}` | GET | Chip timing advisor (BB/TC/FH) |
| `/api/simulate/{team_id}` | GET | 10,000-run team GW simulation |
| `/api/player-simulations?team_id=X` | GET | All-player 10-GW projections |
| `/api/player-detail/{player_id}` | GET | Single player simulation detail |
| `/api/fixtures` | GET | FDR for next 6 GWs, all teams |
| `/api/live/{team_id}` | GET | Live GW points |
| `/api/brier/{team_id}` | GET | Prediction calibration scores |
| `/webhook/whatsapp` | POST | Twilio WhatsApp webhook |
| `/health` | GET | Health check |

## Project structure

```
fpl-app/
├── backend/
│   ├── main.py             # FastAPI app, CORS, endpoints
│   ├── fpl_client.py       # Async FPL API client with 15-min cache
│   ├── models.py           # Pydantic response models
│   ├── recommender.py      # Transfer, captain, and chip logic
│   ├── simulator.py        # Monte Carlo engine (t-copula, antithetic, stratified)
│   ├── brier.py            # Prediction calibration scoring
│   ├── notifier.py         # Live GW WhatsApp notifications
│   ├── whatsapp.py         # Twilio message handler
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api/fpl.ts          # Types + API client
│   │   └── components/
│   │       ├── TeamView.tsx
│   │       ├── TransferRecommender.tsx
│   │       ├── CaptainPicker.tsx
│   │       ├── ChipAdvisor.tsx
│   │       ├── Projections.tsx
│   │       ├── TeamForecast.tsx
│   │       ├── SimulationChart.tsx
│   │       ├── PlayerDetailPanel.tsx
│   │       ├── FixtureDifficulty.tsx
│   │       ├── BrierScore.tsx
│   │       └── LivePoints.tsx
│   └── package.json
└── render.yaml                 # Render deployment blueprint
```

## Architecture decisions

### Lightweight vs full simulation

The app has two modes of projection:

1. **Lightweight** (used by transfers, captain, chips) — fits Student-t from player history (15 squad API calls) or bootstrap form data (zero API calls for candidates). Returns in ~10s.
2. **Full simulation** (used by player-simulations endpoint) — fits all ~700 active players via batch API calls, runs stratified + antithetic Student-t per GW. Returns in 1-3 min.

This split exists because the Render free tier (512 MB RAM, shared CPU) cannot handle 700+ player API fetches within endpoint timeout limits. The lightweight path gives accurate results for squad-scoped decisions while keeping response times reasonable.

### Simulation cache

`simulator.py` maintains a module-level 5-min TTL cache for the full player simulations. The cache key includes `(current_gw, squad_player_ids)` so the same computation is shared across page loads. Fit parameters `(mu, sigma, df)` per player are also cached as a side-effect for downstream use.

## Data source

All data is fetched from the official [FPL API](https://fantasy.premierleague.com/api/bootstrap-static/). No API key required.

## Deployment

Deployed on [Render](https://render.com) via `render.yaml`:

- **Backend**: Python web service (free tier) — auto-deploys from `main`
- **Frontend**: Static site — Vite build, auto-deploys from `main`
- **Env vars**: `VITE_API_URL` on frontend points to backend hostname
