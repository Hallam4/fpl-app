export interface PlayerInfo {
  id: number;
  name: string;
  team: string;
  position: string;
  now_cost: number;
  form: number;
  ict_index: number;
  total_points: number;
  status: string;
  photo: string;
}

export interface SquadPlayer extends PlayerInfo {
  is_captain: boolean;
  is_vice_captain: boolean;
  multiplier: number;
}

export interface TeamResponse {
  team_id: number;
  team_name: string;
  overall_rank: number | null;
  bank: number;
  squad: SquadPlayer[];
  current_gw: number;
}

export interface TransferRecommendation {
  sell_player: PlayerInfo;
  buy_player: PlayerInfo;
  sell_score: number;
  buy_score: number;
  points_gain_estimate: number;
  reasoning: string;
}

export interface TransfersResponse {
  team_id: number;
  current_gw: number;
  recommendations: TransferRecommendation[];
}

export interface FixtureEntry {
  gw: number;
  opponent: string;
  is_home: boolean;
  fdr: number;
}

export interface TeamFixtures {
  team_id: number;
  team_name: string;
  team_short_name: string;
  fixtures: FixtureEntry[];
}

export interface FixturesResponse {
  current_gw: number;
  next_gws: number[];
  teams: TeamFixtures[];
}

export interface SimulationResult {
  mean: number;
  median: number;
  p25: number;
  p75: number;
  p90: number;
  histogram_bins: number[];
  histogram_counts: number[];
  player_contributions: {
    id: number;
    name: string;
    position: string;
    team: string;
    expected_pts: number;
    multiplier: number;
  }[];
}

export interface CaptainCandidate {
  player: PlayerInfo;
  captain_score: number;
  reasoning: string;
}

export interface CaptainResponse {
  team_id: number;
  current_gw: number;
  recommendations: CaptainCandidate[];
}

const BASE = "/api";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export const fplApi = {
  getTeam: (teamId: number) =>
    fetchJson<TeamResponse>(`${BASE}/team/${teamId}`),
  getFixtures: () => fetchJson<FixturesResponse>(`${BASE}/fixtures`),
  getTransfers: (teamId: number) =>
    fetchJson<TransfersResponse>(`${BASE}/transfers/${teamId}`),
  simulate: (teamId: number) =>
    fetchJson<SimulationResult>(`${BASE}/simulate/${teamId}`),
  getCaptain: (teamId: number) =>
    fetchJson<CaptainResponse>(`${BASE}/captain/${teamId}`),
};
