from typing import Any
import numpy as np
from scipy import stats
import fpl_client
from models import (
    PlayerInfo,
    TransferRecommendation,
    CaptainCandidate,
    ChipGW,
    ChipAdvice,
)
from simulator import _fit_student_t, _stratified_uniform, N_STRATA

POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def _player_info(element: dict, teams_by_id: dict) -> PlayerInfo:
    team = teams_by_id.get(element["team"], {})
    return PlayerInfo(
        id=element["id"],
        name=element["web_name"],
        team=team.get("short_name", "?"),
        position=POSITION_MAP.get(element["element_type"], "?"),
        now_cost=element["now_cost"] / 10,
        form=float(element.get("form") or 0),
        ict_index=float(element.get("ict_index") or 0),
        total_points=element.get("total_points", 0),
        status=element.get("status", "a"),
        photo=f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{element['photo'].replace('.jpg', '')}.png",
    )


def _avg_fdr(player_fixtures: list[dict], n: int = 3) -> float:
    upcoming = [f for f in player_fixtures if not f.get("finished", True)][:n]
    if not upcoming:
        return 3.0
    return sum(f["difficulty"] for f in upcoming) / len(upcoming)


async def get_squad_players(
    team_id: int, current_gw: int, bootstrap: dict
) -> tuple[list[dict], list[dict], float, dict]:
    """Returns (squad_elements, picks, bank_value, players_by_id)."""
    entry_data = await fpl_client.get_entry(team_id)
    picks_data = await fpl_client.get_entry_picks(team_id, current_gw)

    bank = picks_data["entry_history"]["bank"] / 10
    picks = picks_data["picks"]

    players_by_id = {e["id"]: e for e in bootstrap["elements"]}
    squad_elements = [players_by_id[p["element"]] for p in picks]

    return squad_elements, picks, bank, players_by_id


async def _fit_player(element: dict, summary: dict | None) -> tuple[float, float, float]:
    """Fit Student-t from a player's last 5 GW history, falling back to bootstrap form."""
    history = summary.get("history", []) if summary else []
    last5 = [h["total_points"] for h in history[-5:]] if history else []
    if last5:
        return _fit_student_t(last5)
    form = float(element.get("form") or 0)
    ppg = float(element.get("points_per_game") or 0)
    mu = form if form > 0 else ppg
    return mu, max(mu * 0.5, 1.0), 4.0


def _quick_fit(element: dict) -> tuple[float, float, float]:
    """Lightweight fit from bootstrap data only (no API call)."""
    form = float(element.get("form") or 0)
    ppg = float(element.get("points_per_game") or 0)
    mu = form if form > 0 else ppg
    return mu, max(mu * 0.5, 1.0), 4.0


def _project_gw(mu: float, fdr: float) -> float:
    """FDR-scaled expected points for a single GW."""
    return max(0.0, mu * (6 - fdr) / 3.0)


async def _get_team_gw_fdr(current_gw: int, n_gws: int = 3) -> dict[int, dict[int, float]]:
    """Build team_id → {gw: fdr} for the next n GWs."""
    team_gw_fdr: dict[int, dict[int, float]] = {}
    for gw in range(current_gw, min(current_gw + n_gws, 39)):
        try:
            fixtures = await fpl_client.get_fixtures(gw)
        except Exception:
            continue
        for f in fixtures:
            team_gw_fdr.setdefault(f["team_h"], {})[gw] = f["team_h_difficulty"]
            team_gw_fdr.setdefault(f["team_a"], {})[gw] = f["team_a_difficulty"]
    return team_gw_fdr


def _project_3gw(mu: float, team_id: int, current_gw: int, team_gw_fdr: dict) -> float:
    """Sum of FDR-scaled expected points over 3 GWs."""
    total = 0.0
    for gw in range(current_gw, min(current_gw + 3, 39)):
        fdr = team_gw_fdr.get(team_id, {}).get(gw, 3.0)
        total += _project_gw(mu, fdr)
    return total


async def build_transfer_recommendations(
    team_id: int, current_gw: int, bootstrap: dict
) -> list[TransferRecommendation]:
    squad_elements, picks, bank, players_by_id = await get_squad_players(
        team_id, current_gw, bootstrap
    )
    teams_by_id = {t["id"]: t for t in bootstrap["teams"]}
    squad_ids = {e["id"] for e in squad_elements}

    # Fetch FDR for next 3 GWs
    team_gw_fdr = await _get_team_gw_fdr(current_gw, 3)

    # Fit squad players from their history (only 15 API calls)
    squad_summaries = await fpl_client.get_element_summaries_batch(
        [e["id"] for e in squad_elements]
    )
    squad_fits: dict[int, tuple[float, float, float]] = {}
    for element in squad_elements:
        squad_fits[element["id"]] = await _fit_player(
            element, squad_summaries.get(element["id"])
        )

    recommendations: list[TransferRecommendation] = []

    for element in squad_elements:
        mu, sigma, df = squad_fits[element["id"]]
        sell_3gw = _project_3gw(mu, element["team"], current_gw, team_gw_fdr)
        pos = element["element_type"]
        sell_price = element["now_cost"] / 10

        # Find best replacement — use bootstrap form for candidates (no API calls)
        best_buy = None
        best_buy_3gw = -1.0

        for candidate in bootstrap["elements"]:
            if candidate["id"] in squad_ids:
                continue
            if candidate["element_type"] != pos:
                continue
            buy_price = candidate["now_cost"] / 10
            if buy_price > sell_price + bank:
                continue
            if candidate.get("status") not in ("a", "d"):
                continue

            cand_mu, _, _ = _quick_fit(candidate)
            cand_3gw = _project_3gw(cand_mu, candidate["team"], current_gw, team_gw_fdr)

            if cand_3gw > best_buy_3gw:
                best_buy_3gw = cand_3gw
                best_buy = candidate

        if best_buy is None:
            continue

        points_gain = round(best_buy_3gw - sell_3gw, 1)
        if points_gain < 0.5:
            continue

        sell_info = _player_info(element, teams_by_id)
        buy_info = _player_info(best_buy, teams_by_id)

        reasoning = (
            f"{buy_info.name} projects {best_buy_3gw:.1f} pts vs "
            f"{sell_info.name} {sell_3gw:.1f} pts over 3 GWs (Student-t)"
        )

        recommendations.append(
            TransferRecommendation(
                sell_player=sell_info,
                buy_player=buy_info,
                sell_score=round(sell_3gw, 1),
                buy_score=round(best_buy_3gw, 1),
                points_gain_estimate=points_gain,
                reasoning=reasoning,
            )
        )

    recommendations.sort(key=lambda r: r.points_gain_estimate, reverse=True)
    recommendations = recommendations[:5]

    # Hit analysis for each recommendation
    for rec in recommendations:
        hit = await _compute_hit_analysis(
            rec.sell_player.id, rec.buy_player.id,
            squad_fits, current_gw, bootstrap, team_gw_fdr,
        )
        if hit:
            rec.hit_break_even_1gw = hit["hit_break_even_1gw"]
            rec.hit_break_even_3gw = hit["hit_break_even_3gw"]
            rec.expected_net_1gw = hit["expected_net_1gw"]
            rec.expected_net_3gw = hit["expected_net_3gw"]

    return recommendations


async def _compute_hit_analysis(
    sell_id: int,
    buy_id: int,
    squad_fits: dict[int, tuple[float, float, float]],
    current_gw: int,
    bootstrap: dict,
    team_gw_fdr: dict,
) -> dict:
    """Lightweight hit analysis using pre-computed fits."""
    elements_by_id = {e["id"]: e for e in bootstrap["elements"]}
    sell_el = elements_by_id.get(sell_id)
    buy_el = elements_by_id.get(buy_id)
    if not sell_el or not buy_el:
        return {}

    # Sell player has a full fit; buy player uses quick fit
    sell_mu, sell_sigma, sell_df = squad_fits.get(sell_id, _quick_fit(sell_el))
    buy_mu, buy_sigma, buy_df = _quick_fit(buy_el)

    rng = np.random.default_rng(42)
    n_sims = 1_000
    half = n_sims // 2

    sell_gw_samples = []
    buy_gw_samples = []
    gameweeks = list(range(current_gw, min(current_gw + 3, 39)))

    for gw in gameweeks:
        sell_fdr = team_gw_fdr.get(sell_el["team"], {}).get(gw, 3.0)
        buy_fdr = team_gw_fdr.get(buy_el["team"], {}).get(gw, 3.0)
        sell_mu_s = max(0.0, sell_mu * (6 - sell_fdr) / 3.0)
        buy_mu_s = max(0.0, buy_mu * (6 - buy_fdr) / 3.0)

        U_sell = np.clip(_stratified_uniform(rng, half, N_STRATA), 1e-8, 1 - 1e-8)
        U_buy = np.clip(_stratified_uniform(rng, half, N_STRATA), 1e-8, 1 - 1e-8)

        s1_sell = stats.t.ppf(U_sell, df=sell_df) * sell_sigma + sell_mu_s
        s2_sell = stats.t.ppf(1.0 - U_sell, df=sell_df) * sell_sigma + sell_mu_s
        s1_buy = stats.t.ppf(U_buy, df=buy_df) * buy_sigma + buy_mu_s
        s2_buy = stats.t.ppf(1.0 - U_buy, df=buy_df) * buy_sigma + buy_mu_s

        sell_gw_samples.append(np.maximum(np.concatenate([s1_sell, s2_sell]), 0))
        buy_gw_samples.append(np.maximum(np.concatenate([s1_buy, s2_buy]), 0))

    diff_1gw = buy_gw_samples[0] - sell_gw_samples[0]
    hit_break_even_1gw = float(np.mean(diff_1gw > 4))
    expected_net_1gw = float(np.mean(diff_1gw)) - 4

    sell_3gw = sum(sell_gw_samples[:3])
    buy_3gw = sum(buy_gw_samples[:3])
    diff_3gw = buy_3gw - sell_3gw
    hit_break_even_3gw = float(np.mean(diff_3gw > 4))
    expected_net_3gw = float(np.mean(diff_3gw)) - 4

    return {
        "hit_break_even_1gw": round(hit_break_even_1gw, 3),
        "hit_break_even_3gw": round(hit_break_even_3gw, 3),
        "expected_net_1gw": round(expected_net_1gw, 2),
        "expected_net_3gw": round(expected_net_3gw, 2),
    }


async def build_captain_recommendations(
    team_id: int, current_gw: int, bootstrap: dict
) -> list[CaptainCandidate]:
    squad_elements, picks, bank, players_by_id = await get_squad_players(
        team_id, current_gw, bootstrap
    )
    teams_by_id = {t["id"]: t for t in bootstrap["teams"]}

    # Fetch summaries for squad only (15 players)
    squad_summaries = await fpl_client.get_element_summaries_batch(
        [e["id"] for e in squad_elements]
    )

    # Next GW fixtures
    try:
        next_fixtures = await fpl_client.get_fixtures(current_gw)
    except Exception:
        next_fixtures = []

    team_fdr: dict[int, float] = {}
    for f in next_fixtures:
        team_fdr.setdefault(f["team_h"], f["team_h_difficulty"])
        team_fdr.setdefault(f["team_a"], f["team_a_difficulty"])

    candidates: list[CaptainCandidate] = []

    for element in squad_elements:
        if element["element_type"] == 1:  # skip GKs
            continue

        mu, sigma, df = await _fit_player(element, squad_summaries.get(element["id"]))
        fdr = team_fdr.get(element["team"], 3.0)
        expected_pts = _project_gw(mu, fdr)
        fdr_scale = (6 - fdr) / 3.0
        mu_scaled = max(0.0, mu * fdr_scale)
        p90 = max(0.0, mu_scaled + sigma * stats.t.ppf(0.9, df))

        opponent_teams = [
            teams_by_id.get(
                f["team_h"] if f["team_a"] == element["team"] else f["team_a"], {}
            ).get("short_name", "?")
            for f in next_fixtures
            if f["team_h"] == element["team"] or f["team_a"] == element["team"]
        ]
        opponent = opponent_teams[0] if opponent_teams else "?"

        reasoning = (
            f"Expected: {expected_pts:.1f} pts | "
            f"P90 upside: {p90:.1f} pts | "
            f"vs {opponent} (FDR {fdr:.0f})"
        )

        candidates.append(
            CaptainCandidate(
                player=_player_info(element, teams_by_id),
                captain_score=round(expected_pts, 2),
                expected_pts=round(expected_pts, 2),
                p90_pts=round(p90, 2),
                reasoning=reasoning,
            )
        )

    candidates.sort(key=lambda c: c.captain_score, reverse=True)
    return candidates[:3]


async def build_chip_advice(
    team_id: int, current_gw: int, bootstrap: dict
) -> ChipAdvice:
    squad_elements, picks, bank, players_by_id = await get_squad_players(
        team_id, current_gw, bootstrap
    )

    picks_by_element = {p["element"]: p for p in picks}
    bench_elements = [e for e in squad_elements if picks_by_element[e["id"]]["multiplier"] == 0]
    playing_elements = [e for e in squad_elements if picks_by_element[e["id"]]["multiplier"] > 0]

    # Fit squad players from history
    squad_summaries = await fpl_client.get_element_summaries_batch(
        [e["id"] for e in squad_elements]
    )
    squad_fits: dict[int, float] = {}  # id → mu_base
    for element in squad_elements:
        mu, _, _ = await _fit_player(element, squad_summaries.get(element["id"]))
        squad_fits[element["id"]] = mu

    # FDR for next 10 GWs
    gw_end = min(current_gw + 9, 38)
    gameweeks = list(range(current_gw, gw_end + 1))
    team_gw_fdr = await _get_team_gw_fdr(current_gw, 10)

    # For FH: get top players from bootstrap by form (no API calls)
    all_elements = bootstrap["elements"]
    all_mus: dict[int, float] = {}
    for el in all_elements:
        mu, _, _ = _quick_fit(el)
        all_mus[el["id"]] = mu

    n_gws = len(gameweeks)
    bb_scores = []
    tc_uplifts = []
    fh_gains = []

    for j, gw in enumerate(gameweeks):
        # BB: sum of bench expected
        bb = sum(
            _project_gw(squad_fits[e["id"]], team_gw_fdr.get(e["team"], {}).get(gw, 3.0))
            for e in bench_elements
        )
        bb_scores.append(bb)

        # TC: best squad player's expected (extra 1x captain value)
        squad_expected = [
            _project_gw(squad_fits[e["id"]], team_gw_fdr.get(e["team"], {}).get(gw, 3.0))
            for e in squad_elements
        ]
        tc = max(squad_expected) if squad_expected else 0.0
        tc_uplifts.append(tc)

        # FH: top 11 from all players minus current 11
        all_gw_expected = [
            (el["id"], _project_gw(all_mus[el["id"]], team_gw_fdr.get(el["team"], {}).get(gw, 3.0)))
            for el in all_elements
        ]
        all_gw_expected.sort(key=lambda x: x[1], reverse=True)
        top_11 = sum(v for _, v in all_gw_expected[:11])
        current_11 = sum(
            _project_gw(squad_fits[e["id"]], team_gw_fdr.get(e["team"], {}).get(gw, 3.0))
            for e in playing_elements
        )
        fh_gains.append(top_11 - current_11)

    # Compute ranks (1 = best GW for this chip)
    def rank_desc(values: list[float]) -> list[int]:
        indexed = sorted(enumerate(values), key=lambda x: x[1], reverse=True)
        ranks = [0] * len(values)
        for rank, (idx, _) in enumerate(indexed, 1):
            ranks[idx] = rank
        return ranks

    bb_ranks = rank_desc(bb_scores)
    tc_ranks = rank_desc(tc_uplifts)
    fh_ranks = rank_desc(fh_gains)

    gw_breakdown = [
        ChipGW(
            gw=gameweeks[j],
            bb_score=round(bb_scores[j], 1),
            tc_uplift=round(tc_uplifts[j], 1),
            fh_gain=round(fh_gains[j], 1),
            bb_rank=bb_ranks[j],
            tc_rank=tc_ranks[j],
            fh_rank=fh_ranks[j],
        )
        for j in range(n_gws)
    ]

    best_bb_idx = bb_scores.index(max(bb_scores))
    best_tc_idx = tc_uplifts.index(max(tc_uplifts))
    best_fh_idx = fh_gains.index(max(fh_gains))

    return ChipAdvice(
        best_bb_gw=gameweeks[best_bb_idx],
        best_bb_score=round(bb_scores[best_bb_idx], 1),
        best_tc_gw=gameweeks[best_tc_idx],
        best_tc_uplift=round(tc_uplifts[best_tc_idx], 1),
        best_fh_gw=gameweeks[best_fh_idx],
        best_fh_gain=round(fh_gains[best_fh_idx], 1),
        gw_breakdown=gw_breakdown,
    )
