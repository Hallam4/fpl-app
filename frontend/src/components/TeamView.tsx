import { useQuery } from "@tanstack/react-query";
import { fplApi, SquadPlayer } from "../api/fpl";

const STATUS_BADGE: Record<string, string> = {
  a: "bg-green-700 text-green-100",
  d: "bg-yellow-700 text-yellow-100",
  i: "bg-red-700 text-red-100",
  s: "bg-gray-600 text-gray-100",
  u: "bg-gray-600 text-gray-100",
};

const STATUS_LABEL: Record<string, string> = {
  a: "Available",
  d: "Doubtful",
  i: "Injured",
  s: "Suspended",
  u: "Unavailable",
};

function PlayerCard({ player }: { player: SquadPlayer }) {
  return (
    <div className="bg-gray-800 rounded-lg p-3 flex items-center gap-3 relative">
      {player.is_captain && (
        <span className="absolute top-1 right-1 bg-purple-600 text-white text-xs font-bold px-1.5 py-0.5 rounded">
          C
        </span>
      )}
      {player.is_vice_captain && !player.is_captain && (
        <span className="absolute top-1 right-1 bg-blue-600 text-white text-xs font-bold px-1.5 py-0.5 rounded">
          V
        </span>
      )}
      <img
        src={player.photo}
        alt={player.name}
        className="w-12 h-16 object-cover rounded"
        onError={(e) => {
          (e.target as HTMLImageElement).src =
            "https://resources.premierleague.com/premierleague/photos/players/110x140/Photo-Missing.png";
        }}
      />
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm truncate">{player.name}</p>
        <p className="text-xs text-gray-400">
          {player.team} &middot; {player.position}
        </p>
        <p className="text-xs text-gray-400">£{player.now_cost.toFixed(1)}m</p>
        <div className="flex gap-1 mt-1">
          <span className="text-xs bg-gray-700 px-1.5 py-0.5 rounded">
            Form: {player.form}
          </span>
          <span
            className={`text-xs px-1.5 py-0.5 rounded ${
              STATUS_BADGE[player.status] ?? STATUS_BADGE["u"]
            }`}
          >
            {STATUS_LABEL[player.status] ?? player.status}
          </span>
        </div>
      </div>
      <div className="text-right">
        <p className="text-lg font-bold text-purple-400">{player.total_points}</p>
        <p className="text-xs text-gray-500">pts</p>
      </div>
    </div>
  );
}

export default function TeamView({ teamId }: { teamId: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["team", teamId],
    queryFn: () => fplApi.getTeam(teamId),
  });

  if (isLoading)
    return (
      <div className="flex justify-center py-12 text-gray-400">
        Loading squad...
      </div>
    );
  if (error)
    return (
      <div className="text-red-400 py-8 text-center">
        Error: {(error as Error).message}
      </div>
    );
  if (!data) return null;

  const byPos = (pos: string) => data.squad.filter((p) => p.position === pos);
  const gkp = byPos("GKP");
  const def = byPos("DEF");
  const mid = byPos("MID");
  const fwd = byPos("FWD");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-4 items-center">
        <div>
          <h2 className="text-xl font-bold">{data.team_name}</h2>
          <p className="text-sm text-gray-400">GW {data.current_gw}</p>
        </div>
        <div className="ml-auto flex gap-4 text-sm">
          <div className="bg-gray-800 rounded px-3 py-2">
            <p className="text-gray-400">Bank</p>
            <p className="font-bold text-green-400">£{data.bank.toFixed(1)}m</p>
          </div>
          {data.overall_rank && (
            <div className="bg-gray-800 rounded px-3 py-2">
              <p className="text-gray-400">Overall Rank</p>
              <p className="font-bold">{data.overall_rank.toLocaleString()}</p>
            </div>
          )}
        </div>
      </div>

      {[
        { label: "Goalkeepers", players: gkp },
        { label: "Defenders", players: def },
        { label: "Midfielders", players: mid },
        { label: "Forwards", players: fwd },
      ].map(({ label, players }) => (
        <div key={label}>
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-2">
            {label}
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {players.map((p) => (
              <PlayerCard key={p.id} player={p} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
