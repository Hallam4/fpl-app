import time
from typing import Any, Optional
import httpx

BASE_URL = "https://fantasy.premierleague.com/api"

_cache: dict[str, tuple[Any, float]] = {}
CACHE_TTL = 900  # 15 minutes


def _cached(key: str) -> Optional[Any]:
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None


def _store(key: str, data: Any) -> None:
    _cache[key] = (data, time.time())


async def get_bootstrap() -> dict:
    key = "bootstrap"
    if cached := _cached(key):
        return cached
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/bootstrap-static/", timeout=30)
        r.raise_for_status()
        data = r.json()
    _store(key, data)
    return data


async def get_fixtures(gw: int) -> list:
    key = f"fixtures_{gw}"
    if cached := _cached(key):
        return cached
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/fixtures/?event={gw}", timeout=30)
        r.raise_for_status()
        data = r.json()
    _store(key, data)
    return data


async def get_element_summary(player_id: int) -> dict:
    key = f"element_{player_id}"
    if cached := _cached(key):
        return cached
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/element-summary/{player_id}/", timeout=30)
        r.raise_for_status()
        data = r.json()
    _store(key, data)
    return data


async def get_entry_picks(team_id: int, gw: int) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/entry/{team_id}/event/{gw}/picks/", timeout=30)
        r.raise_for_status()
        return r.json()


async def get_entry(team_id: int) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/entry/{team_id}/", timeout=30)
        r.raise_for_status()
        return r.json()
