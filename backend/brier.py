"""
Brier score calibration tracking.

Stores per-GW predictions and compares against actual outcomes.
Brier score = (1/N) * sum((predicted_prob - actual_outcome)^2)
  - 0.0 = perfect calibration
  - 0.25 = coin-flip baseline
  - < 0.20 = good; < 0.10 = excellent (per the article)
"""

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import numpy as np

DATA_DIR = Path(__file__).parent / "data"
PREDICTIONS_FILE = DATA_DIR / "predictions.json"


def _load() -> dict:
    if PREDICTIONS_FILE.exists():
        return json.loads(PREDICTIONS_FILE.read_text())
    return {}


def _save(data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    PREDICTIONS_FILE.write_text(json.dumps(data, indent=2))


def store_predictions(
    team_id: int, gw: int, predictions: list[dict]
) -> None:
    """Save player predictions for a given GW so we can score later."""
    data = _load()
    key = f"gw_{gw}_team_{team_id}"
    data[key] = {
        "team_id": team_id,
        "gw": gw,
        "timestamp": time.time(),
        "predictions": predictions,
    }
    _save(data)


async def _fetch_live_stats(gw: int) -> dict[int, dict]:
    """Fetch actual GW stats from FPL API."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://fantasy.premierleague.com/api/event/{gw}/live/",
            timeout=15,
        )
        r.raise_for_status()
        live = r.json()
    return {e["id"]: e["stats"] for e in live.get("elements", [])}


async def compute_brier_scores(
    team_id: int, current_gw: int
) -> dict[str, Any]:
    """
    Compare stored predictions against actuals for all completed GWs.

    Returns:
        brier_score  — mean Brier score for P(4+ pts) predictions
        mse          — mean squared error of predicted vs actual points
        calibration  — bucketed calibration data for the UI chart
        gw_details   — per-GW breakdown
    """
    data = _load()
    if not data:
        return {"brier_score": None, "mse": None, "calibration": [], "gw_details": []}

    all_probs: list[float] = []
    all_outcomes: list[int] = []
    all_pred_pts: list[float] = []
    all_actual_pts: list[int] = []
    gw_details: list[dict] = []

    # Find all past GW predictions for this team
    for key, entry in sorted(data.items()):
        if entry.get("team_id") != team_id:
            continue
        gw = entry["gw"]
        if gw >= current_gw:
            continue  # GW not yet completed

        try:
            live_stats = await _fetch_live_stats(gw)
        except Exception:
            continue

        predictions = entry.get("predictions", [])
        if not predictions:
            continue

        gw_probs: list[float] = []
        gw_outcomes: list[int] = []
        gw_pred: list[float] = []
        gw_actual: list[int] = []

        for pred in predictions:
            pid = pred["player_id"]
            stats = live_stats.get(pid)
            if stats is None:
                continue
            actual = stats.get("total_points", 0)

            prob_4plus = pred.get("prob_4plus", 0.5)
            predicted_mean = pred.get("predicted_mean", 0)
            outcome_4plus = 1 if actual >= 4 else 0

            gw_probs.append(prob_4plus)
            gw_outcomes.append(outcome_4plus)
            gw_pred.append(predicted_mean)
            gw_actual.append(actual)

        if gw_probs:
            probs_arr = np.array(gw_probs)
            outcomes_arr = np.array(gw_outcomes)
            gw_brier = float(np.mean((probs_arr - outcomes_arr) ** 2))
            gw_mse = float(np.mean((np.array(gw_pred) - np.array(gw_actual)) ** 2))

            gw_details.append({
                "gw": gw,
                "brier_score": round(gw_brier, 4),
                "mse": round(gw_mse, 2),
                "n_players": len(gw_probs),
            })

            all_probs.extend(gw_probs)
            all_outcomes.extend(gw_outcomes)
            all_pred_pts.extend(gw_pred)
            all_actual_pts.extend(gw_actual)

    if not all_probs:
        return {"brier_score": None, "mse": None, "calibration": [], "gw_details": []}

    # Overall Brier score
    probs = np.array(all_probs)
    outcomes = np.array(all_outcomes)
    brier = float(np.mean((probs - outcomes) ** 2))

    # Overall MSE
    mse = float(np.mean((np.array(all_pred_pts) - np.array(all_actual_pts)) ** 2))

    # Calibration buckets: group predictions into 10 bins by predicted probability
    calibration = []
    bin_edges = np.linspace(0, 1, 11)
    for i in range(10):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = (probs >= lo) & (probs < hi)
        if mask.sum() == 0:
            continue
        calibration.append({
            "bin_start": round(float(lo), 2),
            "bin_end": round(float(hi), 2),
            "predicted_avg": round(float(probs[mask].mean()), 4),
            "actual_rate": round(float(outcomes[mask].mean()), 4),
            "count": int(mask.sum()),
        })

    return {
        "brier_score": round(brier, 4),
        "mse": round(mse, 2),
        "calibration": calibration,
        "gw_details": gw_details,
    }
