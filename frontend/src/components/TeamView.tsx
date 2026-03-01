import { useQuery } from "@tanstack/react-query";
import { fplApi, SquadPlayer, LivePlayerStats } from "../api/fpl";

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

function EventIcons({ stats }: { stats: LivePlayerStats }) {
  const icons: string[] = [];
  for (let i = 0; i < stats.goals_scored; i++) icons.push("⚽");
  for (let i = 0; i < stats.assists; i++) icons.push("🅰️");
  if (stats.clean_sheets > 0) icons.push("🧤");
  if (stats.bonus > 0) icons.push(`⭐×${stats.bonus}`);
  if (stats.yellow_cards > 0) icons.push("🟨");
  if (stats.red_cards > 0) icons.push("🟥");
  if (!icons.length) return null;
  return <span className="text-xs">{icons.join(" ")}</span>;
}

function PlayerCard({
  player,
  liveStats,
}: {
  player: SquadPlayer;
  liveStats?: LivePlayerStats;
}) {
  const played = liveStats && liveStats.minutes > 0;
  const notYetPlayed = liveStats && liveStats.minutes === 0;

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
        <div className="flex gap-1 mt-1 flex-wrap">
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
        {liveStats && (
          <div className="mt-1 flex items-center gap-1.5 flex-wrap">
            <span className={`text-xs px-1.5 py-0.5 rounded ${played ? "bg-green-900 text-green-300" : "bg-gray-700 text-gray-400"}`}>
              {liveStats.minutes}'
            </span>
            <EventIcons stats={liveStats} />
          </div>
        )}
      </div>
      <div className="text-right space-y-1">
        {liveStats !== undefined && (
          <div className="text-center">
            <p className={`text-lg font-bold ${played ? "text-green-400" : notYetPlayed ? "text-gray-500" : "text-purple-400"}`}>
              {liveStats.effective_points}
            </p>
            <p className="text-xs text-gray-500">GW pts</p>
          </div>
        )}
        <div className="text-center">
          <p className="text-sm font-semibold text-gray-400">{player.total_points}</p>
          <p className="text-xs text-gray-600">season</p>
        </div>
      </div>
    </div>
  );
}

export default function TeamView({ teamId }: { teamId: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["team", teamId],
    queryFn: () => fplApi.getTeam(teamId),
  });

  const { data: liveData } = useQuery({
    queryKey: ["live", teamId],
    queryFn: () => fplApi.getLive(teamId),
    refetchInterval: 60_000, // refresh every 60s during live GW
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

  const liveById = liveData
    ? Object.fromEntries(liveData.players.map((p) => [p.id, p]))
    : {};

  const byPos = (pos: string) => data.squad.filter((p) => p.position === pos);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-4 items-center">
        <div>
          <h2 className="text-xl font-bold">{data.team_name}</h2>
          <p className="text-sm text-gray-400">GW {data.current_gw}</p>
        </div>
        <div className="ml-auto flex gap-3 text-sm flex-wrap">
          {liveData && (
            <div className="bg-green-900 rounded px-3 py-2 text-center">
              <p className="text-green-400 text-xs">GW{liveData.current_gw} Points</p>
              <p className="font-bold text-green-300 text-xl">{liveData.gw_total}</p>
            </div>
          )}
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
        { label: "Goalkeepers", players: byPos("GKP") },
        { label: "Defenders", players: byPos("DEF") },
        { label: "Midfielders", players: byPos("MID") },
        { label: "Forwards", players: byPos("FWD") },
      ].map(({ label, players }) => (
        <div key={label}>
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-2">
            {label}
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {players.map((p) => (
              <PlayerCard
                key={p.id}
                player={p}
                liveStats={liveById[p.id]}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
