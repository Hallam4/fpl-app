from typing import Any
from scipy import stats
import fpl_client
from models import (
    PlayerInfo,
    TransferRecommendation,
    CaptainCandidate,
    ChipGW,
    ChipAdvice,
)
from simulator import get_cached_player_simulations, get_cached_player_fits, compute_hit_analysis

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


async def build_transfer_recommendations(
    team_id: int, current_gw: int, bootstrap: dict
) -> list[TransferRecommendation]:
    squad_elements, picks, bank, players_by_id = await get_squad_players(
        team_id, current_gw, bootstrap
    )
    teams_by_id = {t["id"]: t for t in bootstrap["teams"]}
    squad_ids = {e["id"] for e in squad_elements}

    # Get simulation projections for all players
    sim_data = await get_cached_player_simulations(current_gw, bootstrap, squad_ids)
    sims_by_id = {p.id: p for p in sim_data.players}

    recommendations: list[TransferRecommendation] = []

    for element in squad_elements:
        sim = sims_by_id.get(element["id"])
        if not sim:
            continue

        sell_3gw = sum(sim.gw_expected[:3])
        pos = element["element_type"]
        sell_price = element["now_cost"] / 10

        # Find best replacement by 3-GW projected points
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

            cand_sim = sims_by_id.get(candidate["id"])
            if not cand_sim:
                continue
            cand_3gw = sum(cand_sim.gw_expected[:3])

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
            f"{sell_info.name} {sell_3gw:.1f} pts over 3 GWs (Monte Carlo)"
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

    # Add hit analysis for each recommendation
    for rec in recommendations:
        hit = await compute_hit_analysis(
            rec.sell_player.id, rec.buy_player.id, current_gw, bootstrap
        )
        if hit:
            rec.hit_break_even_1gw = hit["hit_break_even_1gw"]
            rec.hit_break_even_3gw = hit["hit_break_even_3gw"]
            rec.expected_net_1gw = hit["expected_net_1gw"]
            rec.expected_net_3gw = hit["expected_net_3gw"]

    return recommendations


async def build_captain_recommendations(
    team_id: int, current_gw: int, bootstrap: dict
) -> list[CaptainCandidate]:
    squad_elements, picks, bank, players_by_id = await get_squad_players(
        team_id, current_gw, bootstrap
    )
    teams_by_id = {t["id"]: t for t in bootstrap["teams"]}
    squad_ids = {e["id"] for e in squad_elements}

    # Get simulation projections
    sim_data = await get_cached_player_simulations(current_gw, bootstrap, squad_ids)
    sims_by_id = {p.id: p for p in sim_data.players}
    fits = get_cached_player_fits(current_gw)

    # Next GW fixtures for opponent display
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

        sim = sims_by_id.get(element["id"])
        if not sim:
            continue

        expected_pts = sim.gw_expected[0] if sim.gw_expected else 0.0

        # P90 from cached fit params
        fit = fits.get(element["id"])
        if fit:
            mu_base, sigma, df = fit
            fdr = team_fdr.get(element["team"], 3.0)
            fdr_scale = (6 - fdr) / 3.0
            mu_scaled = max(0.0, mu_base * fdr_scale)
            p90 = max(0.0, mu_scaled + sigma * stats.t.ppf(0.9, df))
        else:
            p90 = expected_pts * 1.3

        opponent_teams = [
            teams_by_id.get(
                f["team_h"] if f["team_a"] == element["team"] else f["team_a"], {}
            ).get("short_name", "?")
            for f in next_fixtures
            if f["team_h"] == element["team"] or f["team_a"] == element["team"]
        ]
        opponent = opponent_teams[0] if opponent_teams else "?"
        fdr_val = team_fdr.get(element["team"], 3.0)

        reasoning = (
            f"Expected: {expected_pts:.1f} pts | "
            f"P90 upside: {p90:.1f} pts | "
            f"vs {opponent} (FDR {fdr_val:.0f})"
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
    squad_ids = {e["id"] for e in squad_elements}

    picks_by_element = {p["element"]: p for p in picks}
    bench_ids = [e["id"] for e in squad_elements if picks_by_element[e["id"]]["multiplier"] == 0]
    playing_ids = [e["id"] for e in squad_elements if picks_by_element[e["id"]]["multiplier"] > 0]

    sim_data = await get_cached_player_simulations(current_gw, bootstrap, squad_ids)
    sims_by_id = {p.id: p for p in sim_data.players}

    n_gws = len(sim_data.gameweeks)
    bb_scores = []
    tc_uplifts = []
    fh_gains = []

    for j in range(n_gws):
        # BB: sum of bench players' expected for this GW
        bb = sum(sims_by_id[pid].gw_expected[j] for pid in bench_ids if pid in sims_by_id)
        bb_scores.append(bb)

        # TC: best squad player's expected (the extra 1x captain value)
        squad_expected = [
            sims_by_id[pid].gw_expected[j] for pid in (playing_ids + bench_ids) if pid in sims_by_id
        ]
        tc = max(squad_expected) if squad_expected else 0.0
        tc_uplifts.append(tc)

        # FH: top 11 from ALL players minus current 11 expected
        all_expected = [(p.id, p.gw_expected[j]) for p in sim_data.players]
        all_expected.sort(key=lambda x: x[1], reverse=True)
        top_11 = sum(v for _, v in all_expected[:11])
        current_11 = sum(sims_by_id[pid].gw_expected[j] for pid in playing_ids if pid in sims_by_id)
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
            gw=sim_data.gameweeks[j],
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
        best_bb_gw=sim_data.gameweeks[best_bb_idx],
        best_bb_score=round(bb_scores[best_bb_idx], 1),
        best_tc_gw=sim_data.gameweeks[best_tc_idx],
        best_tc_uplift=round(tc_uplifts[best_tc_idx], 1),
        best_fh_gw=sim_data.gameweeks[best_fh_idx],
        best_fh_gain=round(fh_gains[best_fh_idx], 1),
        gw_breakdown=gw_breakdown,
    )
