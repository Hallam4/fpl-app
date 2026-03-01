# FPL Advisor

A Fantasy Premier League web app that analyses your squad and helps you make better decisions.

![Stack](https://img.shields.io/badge/backend-FastAPI-009688?style=flat-square) ![Stack](https://img.shields.io/badge/frontend-React%20%2B%20Vite-646CFF?style=flat-square)

## Features

- **Squad view** — your current 15 players with form, cost, and injury status
- **Transfer recommender** — ranked sell/buy suggestions based on form, fixture difficulty, and ICT index
- **Fixture difficulty heatmap** — next 6 GW FDR for all Premier League teams, with your squad highlighted
- **Monte Carlo simulation** — 10,000-run points distribution for the next GW with P25/P50/P75/P90 bands
- **Captain picker** — top 3 captain options with scores and reasoning

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

Each player in your squad gets a **sell score**:

```
sell_score = (5 - avg_fdr_next3) × 0.3 + (1 - form/10) × 0.4 + injury_flag × 0.3
```

Each candidate replacement gets a **buy score**:

```
buy_score = form × 0.3 + ict_index/100 × 0.3 + (1/cost) × 100 × 0.2 + (1 - avg_fdr_next3/5) × 0.2
```

The top 5 transfers by estimated points gain are returned.

### Captain picker

```
captain_score = form × 0.35 + ict_index/100 × 0.35 + (1 - avg_fdr_next1/5) × 0.3
```

### Monte Carlo simulation

For each starting player, the last 5 GW points are fitted to a Gaussian (μ, σ), scaled by the next fixture's FDR, then sampled 10,000 times to produce a team total distribution.

## Project structure

```
fpl-app/
├── backend/
│   ├── main.py           # FastAPI app + CORS
│   ├── fpl_client.py     # Async FPL API client with 15-min cache
│   ├── models.py         # Pydantic response models
│   ├── recommender.py    # Transfer & captain logic
│   ├── simulator.py      # Monte Carlo engine
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.tsx
    │   ├── api/fpl.ts
    │   └── components/
    │       ├── TeamView.tsx
    │       ├── TransferRecommender.tsx
    │       ├── FixtureDifficulty.tsx
    │       ├── CaptainPicker.tsx
    │       └── SimulationChart.tsx
    └── package.json
```

## Data source

All data is fetched from the official [FPL API](https://fantasy.premierleague.com/api/bootstrap-static/). No API key required.
