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
  hit_break_even_1gw: number | null;
  hit_break_even_3gw: number | null;
  expected_net_1gw: number | null;
  expected_net_3gw: number | null;
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

export interface SimulationMeta {
  n_simulations: number;
  distribution: string;
  techniques: string[];
  variance_reduction_factor: number;
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
  meta: SimulationMeta;
}

export interface CaptainCandidate {
  player: PlayerInfo;
  captain_score: number;
  expected_pts: number;
  p90_pts: number;
  reasoning: string;
}

export interface CaptainResponse {
  team_id: number;
  current_gw: number;
  recommendations: CaptainCandidate[];
}

export interface LivePlayerStats {
  id: number;
  name: string;
  team: string;
  position: string;
  is_captain: boolean;
  is_vice_captain: boolean;
  multiplier: number;
  minutes: number;
  gw_points: number;
  effective_points: number;
  goals_scored: number;
  assists: number;
  clean_sheets: number;
  bonus: number;
  yellow_cards: number;
  red_cards: number;
  saves: number;
}

export interface LiveResponse {
  team_id: number;
  current_gw: number;
  gw_total: number;
  players: LivePlayerStats[];
}

export interface CalibrationBucket {
  bin_start: number;
  bin_end: number;
  predicted_avg: number;
  actual_rate: number;
  count: number;
}

export interface BrierGWDetail {
  gw: number;
  brier_score: number;
  mse: number;
  n_players: number;
}

export interface BrierScoreResponse {
  team_id: number;
  brier_score: number | null;
  mse: number | null;
  calibration: CalibrationBucket[];
  gw_details: BrierGWDetail[];
}

export interface PlayerSimRow {
  id: number;
  name: string;
  team: string;
  team_id: number;
  position: string;
  now_cost: number;
  form: number;
  gw_expected: number[];
  total_expected: number;
  in_squad: boolean;
}

export interface PlayerSimulationsResponse {
  current_gw: number;
  gameweeks: number[];
  players: PlayerSimRow[];
}

export interface PlayerDetailSimulation {
  player_id: number;
  name: string;
  team: string;
  position: string;
  gameweek: number;
  mean: number;
  median: number;
  p25: number;
  p75: number;
  p90: number;
  histogram_bins: number[];
  histogram_counts: number[];
  n_simulations: number;
}

export interface ChipGW {
  gw: number;
  bb_score: number;
  tc_uplift: number;
  fh_gain: number;
  bb_rank: number;
  tc_rank: number;
  fh_rank: number;
}

export interface ChipAdvice {
  best_bb_gw: number;
  best_bb_score: number;
  best_tc_gw: number;
  best_tc_uplift: number;
  best_fh_gw: number;
  best_fh_gain: number;
  gw_breakdown: ChipGW[];
}

export interface ChipResponse {
  team_id: number;
  current_gw: number;
  advice: ChipAdvice;
}

// In production VITE_API_URL is the backend hostname (set by Render blueprint).
// In dev the Vite proxy forwards /api → localhost:8000.
const BASE = import.meta.env.VITE_API_URL
  ? `https://${import.meta.env.VITE_API_URL}/api`
  : "/api";

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
  getLive: (teamId: number) =>
    fetchJson<LiveResponse>(`${BASE}/live/${teamId}`),
  getPlayerSimulations: (teamId?: number) =>
    fetchJson<PlayerSimulationsResponse>(
      `${BASE}/player-simulations${teamId ? `?team_id=${teamId}` : ""}`
    ),
  getBrier: (teamId: number) =>
    fetchJson<BrierScoreResponse>(`${BASE}/brier/${teamId}`),
  getPlayerDetail: (playerId: number) =>
    fetchJson<PlayerDetailSimulation>(`${BASE}/player-detail/${playerId}`),
  getChips: (teamId: number) =>
    fetchJson<ChipResponse>(`${BASE}/chips/${teamId}`),
};
