from typing import Any
import fpl_client
from models import PlayerInfo, TransferRecommendation, CaptainCandidate

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

    # Fetch fixtures for next 3 GWs and build player→fixture map
    all_fixtures: list[dict] = []
    for gw in range(current_gw, current_gw + 3):
        try:
            gw_fixtures = await fpl_client.get_fixtures(gw)
            all_fixtures.extend(gw_fixtures)
        except Exception:
            pass

    # Build team_id → list of upcoming fixtures (with difficulty)
    team_fixtures: dict[int, list[dict]] = {}
    for f in all_fixtures:
        h, a = f["team_h"], f["team_a"]
        team_fixtures.setdefault(h, []).append(
            {"difficulty": f["team_h_difficulty"], "finished": f.get("finished", False)}
        )
        team_fixtures.setdefault(a, []).append(
            {"difficulty": f["team_a_difficulty"], "finished": f.get("finished", False)}
        )

    squad_ids = {e["id"] for e in squad_elements}
    squad_value = sum(e["now_cost"] for e in squad_elements) / 10
    budget = squad_value + bank

    recommendations: list[TransferRecommendation] = []

    for element in squad_elements:
        player_fixtures = team_fixtures.get(element["team"], [])
        avg_fdr = _avg_fdr(player_fixtures, 3)
        form = float(element.get("form") or 0)
        injury_flag = 1.0 if element.get("status") not in ("a", "d") else 0.0

        sell_score = (
            (5 - avg_fdr) * 0.3
            + (1 - form / 10) * 0.4
            + injury_flag * 0.3
        )

        pos = element["element_type"]
        sell_price = element["now_cost"] / 10

        # Find best replacement
        best_buy = None
        best_buy_score = -1.0

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

            cand_fixtures = team_fixtures.get(candidate["team"], [])
            cand_fdr = _avg_fdr(cand_fixtures, 3)
            cand_form = float(candidate.get("form") or 0)
            cand_ict = float(candidate.get("ict_index") or 0)

            buy_score = (
                cand_form * 0.3
                + cand_ict / 100 * 0.3
                + (1 / max(candidate["now_cost"], 1)) * 100 * 0.2
                + (1 - cand_fdr / 5) * 0.2
            )

            if buy_score > best_buy_score:
                best_buy_score = buy_score
                best_buy = candidate

        if best_buy is None:
            continue

        points_gain = round((best_buy_score - sell_score) * 5, 1)
        sell_info = _player_info(element, teams_by_id)
        buy_info = _player_info(best_buy, teams_by_id)

        reason_parts = []
        if injury_flag:
            reason_parts.append(f"{sell_info.name} is injured/doubtful")
        if form < 2.5:
            reason_parts.append(f"{sell_info.name} is out of form ({form})")
        if avg_fdr >= 3.5:
            reason_parts.append(f"tough fixtures ahead (avg FDR {avg_fdr:.1f})")
        reason_parts.append(
            f"{buy_info.name} has good form ({float(best_buy.get('form') or 0):.1f}) "
            f"and easier fixtures"
        )
        reasoning = "; ".join(reason_parts) if reason_parts else "Better fixture run and form"

        recommendations.append(
            TransferRecommendation(
                sell_player=sell_info,
                buy_player=buy_info,
                sell_score=round(sell_score, 3),
                buy_score=round(best_buy_score, 3),
                points_gain_estimate=points_gain,
                reasoning=reasoning,
            )
        )

    recommendations.sort(key=lambda r: r.points_gain_estimate, reverse=True)
    return recommendations[:5]


async def build_captain_recommendations(
    team_id: int, current_gw: int, bootstrap: dict
) -> list[CaptainCandidate]:
    squad_elements, picks, bank, players_by_id = await get_squad_players(
        team_id, current_gw, bootstrap
    )
    teams_by_id = {t["id"]: t for t in bootstrap["teams"]}

    # Next GW fixtures only for captain scoring
    try:
        next_fixtures = await fpl_client.get_fixtures(current_gw)
    except Exception:
        next_fixtures = []

    team_fixtures_gw: dict[int, list[dict]] = {}
    for f in next_fixtures:
        h, a = f["team_h"], f["team_a"]
        team_fixtures_gw.setdefault(h, []).append(
            {"difficulty": f["team_h_difficulty"], "finished": f.get("finished", False)}
        )
        team_fixtures_gw.setdefault(a, []).append(
            {"difficulty": f["team_a_difficulty"], "finished": f.get("finished", False)}
        )

    candidates: list[CaptainCandidate] = []

    for element in squad_elements:
        if element["element_type"] == 1:  # skip GKs for captain
            continue

        player_fixtures = team_fixtures_gw.get(element["team"], [])
        avg_fdr = _avg_fdr(player_fixtures, 1)
        form = float(element.get("form") or 0)
        ict = float(element.get("ict_index") or 0)

        captain_score = (
            form * 0.35
            + ict / 100 * 0.35
            + (1 - avg_fdr / 5) * 0.3
        )

        pos_name = POSITION_MAP.get(element["element_type"], "?")
        opponent_teams = [
            teams_by_id.get(f["team_h"] if f["team_a"] == element["team"] else f["team_a"], {}).get("short_name", "?")
            for f in next_fixtures
            if f["team_h"] == element["team"] or f["team_a"] == element["team"]
        ]
        opponent = opponent_teams[0] if opponent_teams else "?"

        reason_parts = [
            f"Form: {form:.1f}/10",
            f"ICT: {ict:.1f}",
            f"vs {opponent} (FDR {avg_fdr:.0f})",
        ]
        reasoning = " | ".join(reason_parts)

        candidates.append(
            CaptainCandidate(
                player=_player_info(element, teams_by_id),
                captain_score=round(captain_score, 3),
                reasoning=reasoning,
            )
        )

    candidates.sort(key=lambda c: c.captain_score, reverse=True)
    return candidates[:3]
