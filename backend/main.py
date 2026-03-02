import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Form, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import fpl_client
import recommender
import simulator
import brier as brier_mod
import whatsapp
import notifier


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(notifier.run_polling_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
from models import (
    TeamResponse,
    SquadPlayer,
    TransfersResponse,
    FixturesResponse,
    TeamFixtures,
    FixtureEntry,
    SimulationResult,
    LiveResponse,
    LivePlayerStats,
    CaptainResponse,
    PlayerSimulationsResponse,
    BrierScoreResponse,
)

app = FastAPI(title="FPL Advisor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def _current_gw(bootstrap: dict) -> int:
    events = bootstrap.get("events", [])
    for event in events:
        if event.get("is_current"):
            return event["id"]
    # Fall back to next event if none is current
    for event in events:
        if event.get("is_next"):
            return event["id"]
    return 1


@app.get("/api/team/{team_id}", response_model=TeamResponse)
async def get_team(team_id: int):
    try:
        bootstrap = await fpl_client.get_bootstrap()
        entry = await fpl_client.get_entry(team_id)
        current_gw = _current_gw(bootstrap)
        picks_data = await fpl_client.get_entry_picks(team_id, current_gw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    players_by_id = {e["id"]: e for e in bootstrap["elements"]}
    teams_by_id = {t["id"]: t for t in bootstrap["teams"]}
    picks = picks_data["picks"]
    bank = picks_data["entry_history"]["bank"] / 10

    squad: list[SquadPlayer] = []
    for pick in picks:
        element = players_by_id[pick["element"]]
        team = teams_by_id.get(element["team"], {})
        squad.append(
            SquadPlayer(
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
                is_captain=pick.get("is_captain", False),
                is_vice_captain=pick.get("is_vice_captain", False),
                multiplier=pick.get("multiplier", 1),
            )
        )

    team_name = entry.get("name", f"Team {team_id}")
    overall_rank = entry.get("summary_overall_rank")

    return TeamResponse(
        team_id=team_id,
        team_name=team_name,
        overall_rank=overall_rank,
        bank=bank,
        squad=squad,
        current_gw=current_gw,
    )


@app.get("/api/fixtures", response_model=FixturesResponse)
async def get_fixtures():
    try:
        bootstrap = await fpl_client.get_bootstrap()
        current_gw = _current_gw(bootstrap)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    teams_by_id = {t["id"]: t for t in bootstrap["teams"]}
    next_gws = list(range(current_gw, current_gw + 6))

    # Fetch all fixtures for next 6 GWs
    team_fixture_map: dict[int, list[FixtureEntry]] = {t["id"]: [] for t in bootstrap["teams"]}

    for gw in next_gws:
        try:
            fixtures = await fpl_client.get_fixtures(gw)
        except Exception:
            continue
        for f in fixtures:
            h, a = f["team_h"], f["team_a"]
            h_name = teams_by_id.get(a, {}).get("short_name", "?")
            a_name = teams_by_id.get(h, {}).get("short_name", "?")
            team_fixture_map[h].append(
                FixtureEntry(gw=gw, opponent=h_name, is_home=True, fdr=f["team_h_difficulty"])
            )
            team_fixture_map[a].append(
                FixtureEntry(gw=gw, opponent=a_name, is_home=False, fdr=f["team_a_difficulty"])
            )

    teams_fixtures = [
        TeamFixtures(
            team_id=tid,
            team_name=teams_by_id[tid]["name"],
            team_short_name=teams_by_id[tid]["short_name"],
            fixtures=sorted(team_fixture_map[tid], key=lambda x: x.gw),
        )
        for tid in team_fixture_map
    ]

    return FixturesResponse(
        current_gw=current_gw,
        next_gws=next_gws,
        teams=teams_fixtures,
    )


@app.get("/api/transfers/{team_id}", response_model=TransfersResponse)
async def get_transfers(team_id: int):
    try:
        bootstrap = await fpl_client.get_bootstrap()
        current_gw = _current_gw(bootstrap)
        recs = await recommender.build_transfer_recommendations(team_id, current_gw, bootstrap)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return TransfersResponse(
        team_id=team_id,
        current_gw=current_gw,
        recommendations=recs,
    )


@app.get("/api/simulate/{team_id}", response_model=SimulationResult)
async def simulate_team(team_id: int):
    try:
        bootstrap = await fpl_client.get_bootstrap()
        current_gw = _current_gw(bootstrap)
        result = await simulator.run_simulation(team_id, current_gw, bootstrap)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@app.get("/api/captain/{team_id}", response_model=CaptainResponse)
async def get_captain(team_id: int):
    try:
        bootstrap = await fpl_client.get_bootstrap()
        current_gw = _current_gw(bootstrap)
        recs = await recommender.build_captain_recommendations(team_id, current_gw, bootstrap)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CaptainResponse(
        team_id=team_id,
        current_gw=current_gw,
        recommendations=recs,
    )


@app.get("/api/player-simulations", response_model=PlayerSimulationsResponse)
async def player_simulations(team_id: int | None = Query(default=None)):
    try:
        bootstrap = await fpl_client.get_bootstrap()
        current_gw = _current_gw(bootstrap)

        squad_player_ids: set[int] | None = None
        if team_id:
            picks_data = await fpl_client.get_entry_picks(team_id, current_gw)
            squad_player_ids = {p["element"] for p in picks_data["picks"]}

        result = await simulator.run_player_simulations(
            current_gw, bootstrap, squad_player_ids
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@app.get("/api/live/{team_id}", response_model=LiveResponse)
async def get_live(team_id: int):
    try:
        bootstrap = await fpl_client.get_bootstrap()
        current_gw = _current_gw(bootstrap)
        picks_data = await fpl_client.get_entry_picks(team_id, current_gw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    players_by_id = {e["id"]: e for e in bootstrap["elements"]}
    teams_by_id = {t["id"]: t for t in bootstrap["teams"]}
    picks = picks_data["picks"]

    try:
        async with __import__("httpx").AsyncClient() as client:
            r = await client.get(
                f"https://fantasy.premierleague.com/api/event/{current_gw}/live/",
                timeout=15,
            )
            r.raise_for_status()
            live_data = r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"FPL live API error: {e}")

    live_by_id = {e["id"]: e["stats"] for e in live_data.get("elements", [])}

    players: list[LivePlayerStats] = []
    gw_total = 0

    for pick in picks:
        pid = pick["element"]
        element = players_by_id[pid]
        stats = live_by_id.get(pid, {})
        multiplier = pick.get("multiplier", 1)
        gw_pts = stats.get("total_points", 0)
        effective = gw_pts * multiplier

        if multiplier > 0:
            gw_total += effective

        players.append(LivePlayerStats(
            id=pid,
            name=element["web_name"],
            team=teams_by_id.get(element["team"], {}).get("short_name", "?"),
            position=POSITION_MAP.get(element["element_type"], "?"),
            is_captain=pick.get("is_captain", False),
            is_vice_captain=pick.get("is_vice_captain", False),
            multiplier=multiplier,
            minutes=stats.get("minutes", 0),
            gw_points=gw_pts,
            effective_points=effective,
            goals_scored=stats.get("goals_scored", 0),
            assists=stats.get("assists", 0),
            clean_sheets=stats.get("clean_sheets", 0),
            bonus=stats.get("bonus", 0),
            yellow_cards=stats.get("yellow_cards", 0),
            red_cards=stats.get("red_cards", 0),
            saves=stats.get("saves", 0),
        ))

    players.sort(key=lambda p: p.effective_points, reverse=True)

    return LiveResponse(
        team_id=team_id,
        current_gw=current_gw,
        gw_total=gw_total,
        players=players,
    )


@app.get("/api/brier/{team_id}", response_model=BrierScoreResponse)
async def get_brier(team_id: int):
    try:
        bootstrap = await fpl_client.get_bootstrap()
        current_gw = _current_gw(bootstrap)
        result = await brier_mod.compute_brier_scores(team_id, current_gw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return BrierScoreResponse(team_id=team_id, **result)


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(Body: str = Form(...)):
    twiml = await whatsapp.handle_message(Body)
    return Response(content=twiml, media_type="application/xml")


@app.get("/health")
async def health():
    return {"status": "ok"}
