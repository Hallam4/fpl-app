from pydantic import BaseModel
from typing import Optional


class PlayerInfo(BaseModel):
    id: int
    name: str
    team: str
    position: str
    now_cost: float
    form: float
    ict_index: float
    total_points: int
    status: str
    photo: str


class SquadPlayer(PlayerInfo):
    is_captain: bool
    is_vice_captain: bool
    multiplier: int


class TeamResponse(BaseModel):
    team_id: int
    team_name: str
    overall_rank: Optional[int]
    bank: float
    squad: list[SquadPlayer]
    current_gw: int


class TransferRecommendation(BaseModel):
    sell_player: PlayerInfo
    buy_player: PlayerInfo
    sell_score: float
    buy_score: float
    points_gain_estimate: float
    reasoning: str


class TransfersResponse(BaseModel):
    team_id: int
    current_gw: int
    recommendations: list[TransferRecommendation]


class FixtureEntry(BaseModel):
    gw: int
    opponent: str
    is_home: bool
    fdr: int


class TeamFixtures(BaseModel):
    team_id: int
    team_name: str
    team_short_name: str
    fixtures: list[FixtureEntry]


class FixturesResponse(BaseModel):
    current_gw: int
    next_gws: list[int]
    teams: list[TeamFixtures]


class SimulationResult(BaseModel):
    mean: float
    median: float
    p25: float
    p75: float
    p90: float
    histogram_bins: list[float]
    histogram_counts: list[int]
    player_contributions: list[dict]


class CaptainCandidate(BaseModel):
    player: PlayerInfo
    captain_score: float
    reasoning: str


class CaptainResponse(BaseModel):
    team_id: int
    current_gw: int
    recommendations: list[CaptainCandidate]


class LivePlayerStats(BaseModel):
    id: int
    name: str
    team: str
    position: str
    is_captain: bool
    is_vice_captain: bool
    multiplier: int
    minutes: int
    gw_points: int
    effective_points: int  # doubled for captain
    goals_scored: int
    assists: int
    clean_sheets: int
    bonus: int
    yellow_cards: int
    red_cards: int
    saves: int


class LiveResponse(BaseModel):
    team_id: int
    current_gw: int
    gw_total: int
    players: list[LivePlayerStats]
