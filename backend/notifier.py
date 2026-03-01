"""
Live FPL event notifier.

Polls /api/event/{gw}/live/ every 60 seconds during the active gameweek.
Sends a WhatsApp message via Twilio when a squad player scores, assists,
keeps a clean sheet, or earns bonus points.

Required environment variables:
  TWILIO_ACCOUNT_SID   — from Twilio console
  TWILIO_AUTH_TOKEN    — from Twilio console
  TWILIO_FROM          — your Twilio WhatsApp number e.g. +14155238886
  NOTIFY_TO            — your personal WhatsApp number e.g. +447700900000
  NOTIFY_TEAM_ID       — FPL team ID to watch (defaults to 392566)
"""

import asyncio
import logging
import os
import httpx
import fpl_client

logger = logging.getLogger(__name__)

POLL_INTERVAL = 60  # seconds
TEAM_ID = int(os.environ.get("NOTIFY_TEAM_ID", "392566"))

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.environ.get("TWILIO_FROM", "")  # e.g. +14155238886
NOTIFY_TO = os.environ.get("NOTIFY_TO", "")      # e.g. +447700900000

# Track last-known stats per player to detect changes
_prev_stats: dict[int, dict] = {}


async def _send_whatsapp(message: str) -> None:
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, NOTIFY_TO]):
        logger.info("Twilio not configured — notification (would send): %s", message)
        return
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                data={
                    "From": f"whatsapp:{TWILIO_FROM}",
                    "To": f"whatsapp:{NOTIFY_TO}",
                    "Body": message,
                },
                timeout=10,
            )
            if resp.status_code not in (200, 201):
                logger.error("Twilio error %s: %s", resp.status_code, resp.text)
            else:
                logger.info("Notification sent: %s", message)
    except Exception as e:
        logger.error("Failed to send notification: %s", e)


def _current_gw(bootstrap: dict) -> int:
    for event in bootstrap.get("events", []):
        if event.get("is_current"):
            return event["id"]
    for event in bootstrap.get("events", []):
        if event.get("is_next"):
            return event["id"]
    return 1


def _diff_messages(player_name: str, prev: dict, curr: dict) -> list[str]:
    messages = []

    goals = curr.get("goals_scored", 0) - prev.get("goals_scored", 0)
    assists = curr.get("assists", 0) - prev.get("assists", 0)
    clean = curr.get("clean_sheets", 0) - prev.get("clean_sheets", 0)
    bonus = curr.get("bonus", 0) - prev.get("bonus", 0)
    pts = curr.get("total_points", 0) - prev.get("total_points", 0)

    if goals > 0:
        messages.append(f"⚽ {player_name} scored {'a goal' if goals == 1 else f'{goals} goals'}! +{pts} pts")
    elif assists > 0:
        messages.append(f"🅰️ {player_name} got {'an assist' if assists == 1 else f'{assists} assists'}! +{pts} pts")
    elif clean > 0:
        messages.append(f"🧤 {player_name} kept a clean sheet! +{pts} pts")
    elif bonus > 0:
        messages.append(f"⭐ {player_name} earned {bonus} bonus point{'s' if bonus > 1 else ''}!")

    return messages


async def _poll_once() -> None:
    global _prev_stats
    try:
        bootstrap = await fpl_client.get_bootstrap()
        gw = _current_gw(bootstrap)

        # Fetch squad
        picks_data = await fpl_client.get_entry_picks(TEAM_ID, gw)
        squad_ids = {p["element"] for p in picks_data["picks"] if p["multiplier"] > 0}
        players_by_id = {e["id"]: e for e in bootstrap["elements"]}

        # Fetch live GW data
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://fantasy.premierleague.com/api/event/{gw}/live/",
                timeout=15,
            )
            resp.raise_for_status()
            live_data = resp.json()

        live_by_id = {e["id"]: e["stats"] for e in live_data.get("elements", [])}

        notifications = []
        for player_id in squad_ids:
            curr = live_by_id.get(player_id)
            if curr is None:
                continue

            prev = _prev_stats.get(player_id, {
                "goals_scored": 0, "assists": 0,
                "clean_sheets": 0, "bonus": 0, "total_points": 0,
            })

            player_name = players_by_id.get(player_id, {}).get("web_name", f"Player {player_id}")
            msgs = _diff_messages(player_name, prev, curr)
            notifications.extend(msgs)
            _prev_stats[player_id] = curr

        for msg in notifications:
            await _send_whatsapp(msg)

    except Exception as e:
        logger.warning("Poll error: %s", e)


async def run_polling_loop() -> None:
    logger.info("FPL live notifier started (team %s, polling every %ds)", TEAM_ID, POLL_INTERVAL)
    while True:
        await _poll_once()
        await asyncio.sleep(POLL_INTERVAL)
