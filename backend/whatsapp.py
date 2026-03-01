"""
WhatsApp webhook handler via Twilio.

Supported commands (case-insensitive):
  captain               → top 3 captain picks
  transfers             → top 5 transfer recommendations
  simulate / points     → Monte Carlo simulation summary
  squad / team          → squad overview
  fixtures              → next 6 GW fixture difficulty for your squad
  help                  → list commands

Optionally prefix any command with a team ID:
  392566 captain
  123456 transfers
If no team ID is given, defaults to DEFAULT_TEAM_ID.
"""

import re
import fpl_client
import recommender
import simulator

DEFAULT_TEAM_ID = 392566


def _twiml(message: str) -> str:
    escaped = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{escaped}</Message></Response>'


def _parse(body: str) -> tuple[int, str]:
    """Return (team_id, command) from raw message body."""
    body = body.strip()
    match = re.match(r"^(\d{5,8})\s+(.*)", body)
    if match:
        return int(match.group(1)), match.group(2).lower().strip()
    return DEFAULT_TEAM_ID, body.lower().strip()


async def handle_message(body: str) -> str:
    team_id, cmd = _parse(body)

    try:
        bootstrap = await fpl_client.get_bootstrap()
        current_gw = _current_gw(bootstrap)
    except Exception as e:
        return _twiml(f"Could not reach FPL API: {e}")

    # --- captain ---
    if any(k in cmd for k in ("captain", "captai", "cap")):
        try:
            recs = await recommender.build_captain_recommendations(team_id, current_gw, bootstrap)
        except Exception as e:
            return _twiml(f"Error fetching captain picks: {e}")

        lines = [f"Captain picks for GW{current_gw} (team {team_id}):"]
        medals = ["1️⃣", "2️⃣", "3️⃣"]
        for i, c in enumerate(recs):
            lines.append(f"{medals[i]} {c.player.name} ({c.player.team}) — {c.reasoning}")
        return _twiml("\n".join(lines))

    # --- transfers ---
    if any(k in cmd for k in ("transfer", "sell", "buy")):
        try:
            recs = await recommender.build_transfer_recommendations(team_id, current_gw, bootstrap)
        except Exception as e:
            return _twiml(f"Error fetching transfers: {e}")

        lines = [f"Transfer recommendations for GW{current_gw} (team {team_id}):"]
        for i, r in enumerate(recs[:5], 1):
            gain = f"+{r.points_gain_estimate}" if r.points_gain_estimate > 0 else str(r.points_gain_estimate)
            lines.append(
                f"{i}. Sell {r.sell_player.name} → Buy {r.buy_player.name} "
                f"({r.buy_player.position}, £{r.buy_player.now_cost:.1f}m) {gain}pts"
            )
        return _twiml("\n".join(lines))

    # --- simulate / points ---
    if any(k in cmd for k in ("simulat", "sim", "points", "predict", "score")):
        try:
            result = await simulator.run_simulation(team_id, current_gw, bootstrap)
        except Exception as e:
            return _twiml(f"Error running simulation: {e}")

        lines = [
            f"GW{current_gw} points simulation (team {team_id}, n=10,000):",
            f"Mean:   {result.mean}",
            f"Median: {result.median}",
            f"P25:    {result.p25}",
            f"P75:    {result.p75}",
            f"P90:    {result.p90}",
        ]
        return _twiml("\n".join(lines))

    # --- squad / team ---
    if any(k in cmd for k in ("squad", "team", "players", "my team")):
        players_by_id = {e["id"]: e for e in bootstrap["elements"]}
        teams_by_id = {t["id"]: t for t in bootstrap["teams"]}
        try:
            picks_data = await fpl_client.get_entry_picks(team_id, current_gw)
            entry = await fpl_client.get_entry(team_id)
        except Exception as e:
            return _twiml(f"Error fetching squad: {e}")

        picks = picks_data["picks"]
        bank = picks_data["entry_history"]["bank"] / 10
        team_name = entry.get("name", str(team_id))

        pos_map = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
        lines = [f"{team_name} | GW{current_gw} | Bank £{bank:.1f}m"]
        for pos_id, pos_name in pos_map.items():
            players = [
                players_by_id[p["element"]]
                for p in picks
                if players_by_id[p["element"]]["element_type"] == pos_id
                and p["multiplier"] > 0
            ]
            if players:
                names = ", ".join(
                    p["web_name"] + (" (C)" if any(pk["element"] == p["id"] and pk.get("is_captain") for pk in picks) else "")
                    for p in players
                )
                lines.append(f"{pos_name}: {names}")
        return _twiml("\n".join(lines))

    # --- fixtures ---
    if any(k in cmd for k in ("fixture", "fdr", "schedule")):
        try:
            picks_data = await fpl_client.get_entry_picks(team_id, current_gw)
        except Exception as e:
            return _twiml(f"Error fetching fixtures: {e}")

        players_by_id = {e["id"]: e for e in bootstrap["elements"]}
        teams_by_id = {t["id"]: t for t in bootstrap["teams"]}
        squad_team_ids = {players_by_id[p["element"]]["team"] for p in picks_data["picks"]}

        lines = [f"Fixtures GW{current_gw}–{current_gw+2} for your squad:"]
        for team_id_sq in squad_team_ids:
            team_name = teams_by_id.get(team_id_sq, {}).get("short_name", "?")
            fix_parts = []
            for gw in range(current_gw, current_gw + 3):
                try:
                    fixtures = await fpl_client.get_fixtures(gw)
                except Exception:
                    continue
                for f in fixtures:
                    if f["team_h"] == team_id_sq:
                        opp = teams_by_id.get(f["team_a"], {}).get("short_name", "?")
                        fix_parts.append(f"{opp}(H)FDR{f['team_h_difficulty']}")
                    elif f["team_a"] == team_id_sq:
                        opp = teams_by_id.get(f["team_h"], {}).get("short_name", "?")
                        fix_parts.append(f"{opp}(A)FDR{f['team_a_difficulty']}")
            if fix_parts:
                lines.append(f"{team_name}: {' | '.join(fix_parts)}")

        return _twiml("\n".join(lines))

    # --- help ---
    help_text = (
        "FPL Advisor commands:\n"
        "  captain      — top 3 captain picks\n"
        "  transfers    — top 5 transfer recommendations\n"
        "  simulate     — GW points prediction\n"
        "  squad        — your current squad\n"
        "  fixtures     — next 3 GW fixture difficulty\n\n"
        "Prefix with a team ID to query another team:\n"
        "  123456 captain"
    )
    return _twiml(help_text)


def _current_gw(bootstrap: dict) -> int:
    for event in bootstrap.get("events", []):
        if event.get("is_current"):
            return event["id"]
    for event in bootstrap.get("events", []):
        if event.get("is_next"):
            return event["id"]
    return 1
