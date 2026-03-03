import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fplApi, PlayerSimRow, PlayerSimulationsResponse } from "../api/fpl";
import TeamForecast from "./TeamForecast";
import BrierScore from "./BrierScore";

type Position = "ALL" | "GKP" | "DEF" | "MID" | "FWD";
type SortKey = "total" | "name" | "cost";

const POSITIONS: Position[] = ["ALL", "GKP", "DEF", "MID", "FWD"];

function cellStyle(pts: number): React.CSSProperties {
  if (pts <= 0) return { backgroundColor: "#374151" };
  const t = Math.min(pts, 8) / 8;
  const hue = t * 120;
  return { backgroundColor: `hsl(${hue}, 65%, ${35 + t * 10}%)` };
}

function LegendBar() {
  const stops = [0, 1, 2, 3, 4, 5, 6, 7, 8];
  return (
    <div className="flex items-center gap-2 text-xs text-gray-400">
      <span>0 pts</span>
      <div className="flex h-4 rounded overflow-hidden">
        {stops.map((v) => (
          <div key={v} className="w-6" style={cellStyle(v)} />
        ))}
      </div>
      <span>8+ pts</span>
      <div className="flex items-center gap-1 ml-3">
        <div className="w-6 h-4 rounded" style={{ backgroundColor: "#374151" }} />
        <span>Blank</span>
      </div>
    </div>
  );
}

function renderRow(
  p: PlayerSimRow,
  highlight: boolean,
  gameweeks: number[],
) {
  return (
    <tr
      key={p.id}
      className={`border-t border-gray-800 ${
        highlight ? "bg-purple-900/20" : ""
      }`}
    >
      <td className="sticky left-0 z-[5] py-1 pr-2 text-gray-300 text-xs truncate max-w-[8rem] bg-gray-950">
        <span className="font-medium">{p.name}</span>
        <span className="text-gray-500 ml-1 text-[10px]">{p.position}</span>
      </td>
      <td className="py-1 px-2 text-gray-400 text-xs">{p.team}</td>
      <td className="py-1 px-2 text-gray-400 text-xs text-right">
        {p.now_cost.toFixed(1)}
      </td>
      <td className="py-1 px-2 text-white text-xs text-right font-bold">
        {p.total_expected.toFixed(1)}
      </td>
      {gameweeks.map((gw, j) => (
        <td key={gw} className="py-0.5 px-0.5">
          <div
            className="w-14 h-8 flex items-center justify-center rounded text-xs font-medium text-white/90"
            style={cellStyle(p.gw_expected[j])}
          >
            {p.gw_expected[j] <= 0 ? "—" : p.gw_expected[j].toFixed(1)}
          </div>
        </td>
      ))}
    </tr>
  );
}

function renderTable(
  players: PlayerSimRow[],
  highlight: boolean,
  gameweeks: number[],
) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="sticky top-0 bg-gray-950 z-10">
          <tr>
            <th className="sticky left-0 z-20 bg-gray-950 text-left text-gray-400 font-normal py-2 pr-2 w-32">
              Player
            </th>
            <th className="text-left text-gray-400 font-normal py-2 px-2 w-12">
              Team
            </th>
            <th className="text-right text-gray-400 font-normal py-2 px-2 w-14">
              Cost
            </th>
            <th className="text-right text-gray-400 font-normal py-2 px-2 w-14">
              Total
            </th>
            {gameweeks.map((gw) => (
              <th
                key={gw}
                className="text-center text-gray-400 font-normal py-2 px-0.5 w-14"
              >
                GW{gw}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {players.map((p) => renderRow(p, highlight, gameweeks))}
        </tbody>
      </table>
    </div>
  );
}

function PlayerFilters({
  posFilter,
  setPosFilter,
  teamFilter,
  setTeamFilter,
  search,
  setSearch,
  sortKey,
  setSortKey,
  teams,
  count,
}: {
  posFilter: Position;
  setPosFilter: (p: Position) => void;
  teamFilter: string;
  setTeamFilter: (t: string) => void;
  search: string;
  setSearch: (s: string) => void;
  sortKey: SortKey;
  setSortKey: (k: SortKey) => void;
  teams: string[];
  count: number;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex gap-1">
        {POSITIONS.map((pos) => (
          <button
            key={pos}
            onClick={() => setPosFilter(pos)}
            className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
              posFilter === pos
                ? "bg-purple-600 text-white"
                : "bg-gray-800 text-gray-400 hover:text-white"
            }`}
          >
            {pos}
          </button>
        ))}
      </div>

      <select
        value={teamFilter}
        onChange={(e) => setTeamFilter(e.target.value)}
        className="bg-gray-800 text-gray-300 text-xs rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-purple-500"
      >
        <option value="ALL">All teams</option>
        {teams.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>

      <input
        type="text"
        placeholder="Search player..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="bg-gray-800 text-gray-300 text-xs rounded px-3 py-1.5 w-40 focus:outline-none focus:ring-1 focus:ring-purple-500"
      />

      <select
        value={sortKey}
        onChange={(e) => setSortKey(e.target.value as SortKey)}
        className="bg-gray-800 text-gray-300 text-xs rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-purple-500"
      >
        <option value="total">Sort: Total pts</option>
        <option value="name">Sort: Name</option>
        <option value="cost">Sort: Cost</option>
      </select>

      <span className="text-xs text-gray-500">{count} players</span>
    </div>
  );
}

function usePlayerFilters(data: PlayerSimulationsResponse | undefined) {
  const [posFilter, setPosFilter] = useState<Position>("ALL");
  const [teamFilter, setTeamFilter] = useState<string>("ALL");
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("total");

  const teams = useMemo(() => {
    if (!data) return [];
    const seen = new Set<string>();
    for (const p of data.players) seen.add(p.team);
    return Array.from(seen).sort();
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    let players = data.players;
    if (posFilter !== "ALL") {
      players = players.filter((p) => p.position === posFilter);
    }
    if (teamFilter !== "ALL") {
      players = players.filter((p) => p.team === teamFilter);
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      players = players.filter((p) => p.name.toLowerCase().includes(q));
    }
    const sorted = [...players];
    if (sortKey === "name") {
      sorted.sort((a, b) => a.name.localeCompare(b.name));
    } else if (sortKey === "cost") {
      sorted.sort((a, b) => b.now_cost - a.now_cost);
    }
    return sorted;
  }, [data, posFilter, teamFilter, search, sortKey]);

  const squadPlayers = useMemo(
    () => filtered.filter((p) => p.in_squad),
    [filtered],
  );
  const otherPlayers = useMemo(
    () => filtered.filter((p) => !p.in_squad),
    [filtered],
  );

  return {
    posFilter,
    setPosFilter,
    teamFilter,
    setTeamFilter,
    search,
    setSearch,
    sortKey,
    setSortKey,
    teams,
    filtered,
    squadPlayers,
    otherPlayers,
  };
}

export default function Projections({ teamId }: { teamId: number }) {
  const simQuery = useQuery({
    queryKey: ["simulate", teamId],
    queryFn: () => fplApi.simulate(teamId),
  });

  const playerSimQuery = useQuery({
    queryKey: ["player-simulations", teamId],
    queryFn: () => fplApi.getPlayerSimulations(teamId),
  });

  const {
    posFilter,
    setPosFilter,
    teamFilter,
    setTeamFilter,
    search,
    setSearch,
    sortKey,
    setSortKey,
    teams,
    filtered,
    squadPlayers,
    otherPlayers,
  } = usePlayerFilters(playerSimQuery.data);

  return (
    <div className="space-y-8">
      {/* ── Section A: GW Team Forecast ── */}
      {simQuery.isLoading && (
        <div className="flex flex-col items-center py-12 text-gray-400 gap-2">
          <div className="text-sm">Running 10,000 Monte Carlo simulations...</div>
          <div className="w-48 h-1 bg-gray-700 rounded overflow-hidden">
            <div className="h-full bg-purple-500 animate-pulse w-3/4" />
          </div>
        </div>
      )}
      {simQuery.error && (
        <div className="text-red-400 py-8 text-center">
          Error: {(simQuery.error as Error).message}
        </div>
      )}
      {simQuery.data && <TeamForecast data={simQuery.data} />}

      {/* ── Section B: Your Squad — Next 10 GWs ── */}
      {playerSimQuery.isLoading && (
        <div className="flex justify-center py-8 text-gray-400">
          Simulating player projections...
        </div>
      )}
      {playerSimQuery.error && (
        <div className="text-red-400 py-4 text-center">
          Error: {(playerSimQuery.error as Error).message}
        </div>
      )}
      {playerSimQuery.data && squadPlayers.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-lg font-bold">
              Your Squad — Next {playerSimQuery.data.gameweeks.length} GWs
            </h2>
            <LegendBar />
          </div>
          {renderTable(squadPlayers, true, playerSimQuery.data.gameweeks)}
        </section>
      )}

      {/* ── Section C: Prediction Calibration ── */}
      <BrierScore teamId={teamId} />

      {/* ── Section D: All Players Explorer ── */}
      {playerSimQuery.data && (
        <section className="space-y-4">
          <h2 className="text-lg font-bold">All Players Explorer</h2>

          <PlayerFilters
            posFilter={posFilter}
            setPosFilter={setPosFilter}
            teamFilter={teamFilter}
            setTeamFilter={setTeamFilter}
            search={search}
            setSearch={setSearch}
            sortKey={sortKey}
            setSortKey={setSortKey}
            teams={teams}
            count={filtered.length}
          />

          <div className="max-h-[60vh] overflow-y-auto">
            {renderTable(
              otherPlayers.length > 0 ? otherPlayers : filtered,
              false,
              playerSimQuery.data.gameweeks,
            )}
          </div>
        </section>
      )}
    </div>
  );
}
