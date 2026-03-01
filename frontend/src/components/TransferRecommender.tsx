import { useQuery } from "@tanstack/react-query";
import { fplApi, TransferRecommendation } from "../api/fpl";

const POSITION_COLOR: Record<string, string> = {
  GKP: "bg-yellow-700 text-yellow-100",
  DEF: "bg-green-700 text-green-100",
  MID: "bg-blue-700 text-blue-100",
  FWD: "bg-red-700 text-red-100",
};

function GainBadge({ gain }: { gain: number }) {
  const color =
    gain > 3 ? "text-green-400" : gain > 0 ? "text-yellow-400" : "text-red-400";
  return (
    <span className={`font-bold ${color}`}>
      {gain > 0 ? "+" : ""}
      {gain.toFixed(1)} pts
    </span>
  );
}

function TransferRow({ rec }: { rec: TransferRecommendation }) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-3">
      <div className="flex items-center gap-3">
        <span
          className={`text-xs font-bold px-2 py-0.5 rounded ${
            POSITION_COLOR[rec.sell_player.position] ?? "bg-gray-600"
          }`}
        >
          {rec.sell_player.position}
        </span>
        <div className="flex-1 grid grid-cols-[1fr_auto_1fr] items-center gap-2">
          <div className="text-right">
            <p className="font-semibold text-red-300">{rec.sell_player.name}</p>
            <p className="text-xs text-gray-400">
              {rec.sell_player.team} &middot; £{rec.sell_player.now_cost.toFixed(1)}m
            </p>
          </div>
          <span className="text-gray-500 text-sm">→</span>
          <div>
            <p className="font-semibold text-green-300">{rec.buy_player.name}</p>
            <p className="text-xs text-gray-400">
              {rec.buy_player.team} &middot; £{rec.buy_player.now_cost.toFixed(1)}m
            </p>
          </div>
        </div>
        <GainBadge gain={rec.points_gain_estimate} />
      </div>
      <p className="text-xs text-gray-400 italic">{rec.reasoning}</p>
    </div>
  );
}

export default function TransferRecommender({ teamId }: { teamId: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["transfers", teamId],
    queryFn: () => fplApi.getTransfers(teamId),
  });

  if (isLoading)
    return (
      <div className="flex justify-center py-12 text-gray-400">
        Calculating transfer recommendations...
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
        <h2 className="text-lg font-bold">Transfer Recommendations</h2>
        <span className="text-sm text-gray-400">GW {data.current_gw}</span>
      </div>

      {data.recommendations.length === 0 ? (
        <p className="text-gray-400 py-8 text-center">
          No transfer recommendations available.
        </p>
      ) : (
        <div className="space-y-3">
          {data.recommendations.map((rec, i) => (
            <div key={i} className="flex gap-3 items-start">
              <span className="text-gray-500 font-bold text-sm w-5 pt-4 flex-shrink-0">
                {i + 1}
              </span>
              <div className="flex-1">
                <TransferRow rec={rec} />
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-gray-500 mt-4">
        Recommendations are based on form, fixture difficulty, and ICT index. Always
        use your own judgement.
      </p>
    </div>
  );
}
