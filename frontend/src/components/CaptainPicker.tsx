import { useQuery } from "@tanstack/react-query";
import { fplApi, CaptainCandidate } from "../api/fpl";

const MEDALS = ["🥇", "🥈", "🥉"];

function CaptainCard({
  candidate,
  rank,
}: {
  candidate: CaptainCandidate;
  rank: number;
}) {
  const { player, reasoning } = candidate;

  return (
    <div className="bg-gray-800 rounded-xl p-5 flex flex-col gap-3 relative overflow-hidden">
      <div className="absolute top-3 right-3 text-2xl">{MEDALS[rank]}</div>

      <div className="flex items-center gap-4">
        <div className="relative">
          <img
            src={player.photo}
            alt={player.name}
            className="w-16 h-20 object-cover rounded-lg"
            onError={(e) => {
              (e.target as HTMLImageElement).src =
                "https://resources.premierleague.com/premierleague/photos/players/110x140/Photo-Missing.png";
            }}
          />
        </div>
        <div>
          <h3 className="font-bold text-lg">{player.name}</h3>
          <p className="text-sm text-gray-400">
            {player.team} &middot; {player.position}
          </p>
          <p className="text-sm text-gray-400">£{player.now_cost.toFixed(1)}m</p>
        </div>
      </div>

      <div className="flex gap-3">
        <div className="flex-1 bg-gray-700 rounded-lg p-2 text-center">
          <p className="text-xs text-gray-400">Expected</p>
          <p className="text-xl font-bold text-purple-400">
            {candidate.expected_pts.toFixed(1)}
          </p>
        </div>
        <div className="flex-1 bg-gray-700 rounded-lg p-2 text-center">
          <p className="text-xs text-gray-400">P90 Upside</p>
          <p className="text-xl font-bold text-blue-400">
            {candidate.p90_pts.toFixed(1)}
          </p>
        </div>
        <div className="flex-1 bg-gray-700 rounded-lg p-2 text-center">
          <p className="text-xs text-gray-400">Form</p>
          <p className="text-xl font-bold text-green-400">{player.form}</p>
        </div>
      </div>

      <p className="text-sm text-gray-300 italic">{reasoning}</p>
    </div>
  );
}

export default function CaptainPicker({ teamId }: { teamId: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["captain", teamId],
    queryFn: () => fplApi.getCaptain(teamId),
  });

  if (isLoading)
    return (
      <div className="flex justify-center py-12 text-gray-400">
        Analysing captain options...
      </div>
    );
  if (error)
    return (
      <div className="text-red-400 py-8 text-center">
        Error: {(error as Error).message}
      </div>
    );
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">Captain Picks</h2>
        <span className="text-sm text-gray-400">GW {data.current_gw}</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {data.recommendations.map((candidate, i) => (
          <CaptainCard key={candidate.player.id} candidate={candidate} rank={i} />
        ))}
      </div>

      <p className="text-xs text-gray-500">
        Ranked by Monte Carlo expected points. P90 shows 90th-percentile upside
        from Student-t fitted distributions.
      </p>
    </div>
  );
}
