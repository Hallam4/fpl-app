import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fplApi, TransferRecommendation } from "../api/fpl";

const POSITION_COLOR: Record<string, string> = {
  GKP: "bg-yellow-700 text-yellow-100",
  DEF: "bg-green-700 text-green-100",
  MID: "bg-blue-700 text-blue-100",
  FWD: "bg-red-700 text-red-100",
};

const STATUS_LABEL: Record<string, { label: string; color: string }> = {
  a: { label: "Fit", color: "text-green-400" },
  d: { label: "Doubtful", color: "text-yellow-400" },
  i: { label: "Injured", color: "text-red-400" },
  s: { label: "Suspended", color: "text-red-400" },
  u: { label: "Unavailable", color: "text-gray-400" },
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

function StatCompare({
  label,
  sell,
  buy,
  higherIsBetter = true,
}: {
  label: string;
  sell: number;
  buy: number;
  higherIsBetter?: boolean;
}) {
  const buyWins = higherIsBetter ? buy > sell : buy < sell;
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-center text-sm">
      <span className={`text-right ${buyWins ? "text-gray-400" : "text-white font-semibold"}`}>
        {sell.toFixed(1)}
      </span>
      <span className="text-xs text-gray-500 text-center w-16">{label}</span>
      <span className={buyWins ? "text-white font-semibold" : "text-gray-400"}>
        {buy.toFixed(1)}
      </span>
    </div>
  );
}

function TransferRow({ rec }: { rec: TransferRecommendation }) {
  const [expanded, setExpanded] = useState(false);

  const sellStatus = STATUS_LABEL[rec.sell_player.status] ?? { label: rec.sell_player.status, color: "text-gray-400" };
  const buyStatus = STATUS_LABEL[rec.buy_player.status] ?? { label: rec.buy_player.status, color: "text-gray-400" };

  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden">
      {/* Main row */}
      <div className="p-4 space-y-2">
        <div className="flex items-center gap-3">
          <span
            className={`text-xs font-bold px-2 py-0.5 rounded flex-shrink-0 ${
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

        {/* Expand toggle */}
        <button
          onClick={() => setExpanded((v) => !v)}
          className="w-full text-left text-xs text-gray-400 hover:text-white flex items-center gap-1 transition-colors pt-1"
        >
          <span>{expanded ? "▲" : "▼"}</span>
          <span>{expanded ? "Hide reasoning" : "Show reasoning"}</span>
        </button>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-gray-700 p-4 space-y-4">
          {/* Reasoning */}
          <p className="text-sm text-gray-300 italic">{rec.reasoning}</p>

          {/* Stat comparison */}
          <div className="space-y-1">
            <div className="grid grid-cols-[1fr_auto_1fr] gap-2 text-xs text-gray-500 mb-2">
              <span className="text-right text-red-300 font-medium">{rec.sell_player.name}</span>
              <span className="w-16" />
              <span className="text-green-300 font-medium">{rec.buy_player.name}</span>
            </div>
            <StatCompare label="Form" sell={rec.sell_player.form} buy={rec.buy_player.form} />
            <StatCompare label="ICT" sell={rec.sell_player.ict_index} buy={rec.buy_player.ict_index} />
            <StatCompare label="Total pts" sell={rec.sell_player.total_points} buy={rec.buy_player.total_points} />
            <StatCompare label="Cost £m" sell={rec.sell_player.now_cost} buy={rec.buy_player.now_cost} higherIsBetter={false} />
          </div>

          {/* Status */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-gray-700 rounded p-2">
              <p className="text-gray-400 mb-0.5">Availability</p>
              <p className={sellStatus.color}>{sellStatus.label}</p>
            </div>
            <div className="bg-gray-700 rounded p-2">
              <p className="text-gray-400 mb-0.5">Availability</p>
              <p className={buyStatus.color}>{buyStatus.label}</p>
            </div>
          </div>

          {/* Scores */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-gray-700 rounded p-2 text-center">
              <p className="text-gray-400">3-GW Projected</p>
              <p className="text-red-300 font-bold text-base">{rec.sell_score.toFixed(1)}</p>
            </div>
            <div className="bg-gray-700 rounded p-2 text-center">
              <p className="text-gray-400">3-GW Projected</p>
              <p className="text-green-300 font-bold text-base">{rec.buy_score.toFixed(1)}</p>
            </div>
          </div>

          {/* Hit Analysis */}
          {rec.hit_break_even_1gw != null && (
            <div className="space-y-2">
              <p className="text-xs text-gray-400 font-medium">Should I take a -4 hit?</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                <div className="bg-gray-700 rounded p-2 text-center">
                  <p className="text-gray-400">1-GW Break-Even</p>
                  <p className={`font-bold text-base ${rec.hit_break_even_1gw! > 0.5 ? "text-green-400" : "text-red-400"}`}>
                    {(rec.hit_break_even_1gw! * 100).toFixed(0)}%
                  </p>
                </div>
                <div className="bg-gray-700 rounded p-2 text-center">
                  <p className="text-gray-400">3-GW Break-Even</p>
                  <p className={`font-bold text-base ${rec.hit_break_even_3gw! > 0.5 ? "text-green-400" : "text-red-400"}`}>
                    {(rec.hit_break_even_3gw! * 100).toFixed(0)}%
                  </p>
                </div>
                <div className="bg-gray-700 rounded p-2 text-center">
                  <p className="text-gray-400">1-GW Net pts</p>
                  <p className={`font-bold text-base ${rec.expected_net_1gw! > 0 ? "text-green-400" : "text-red-400"}`}>
                    {rec.expected_net_1gw! > 0 ? "+" : ""}{rec.expected_net_1gw!.toFixed(1)}
                  </p>
                </div>
                <div className="bg-gray-700 rounded p-2 text-center">
                  <p className="text-gray-400">3-GW Net pts</p>
                  <p className={`font-bold text-base ${rec.expected_net_3gw! > 0 ? "text-green-400" : "text-red-400"}`}>
                    {rec.expected_net_3gw! > 0 ? "+" : ""}{rec.expected_net_3gw!.toFixed(1)}
                  </p>
                </div>
              </div>
              <p className="text-[10px] text-gray-600">
                Break-even = probability the buy outscores sell by 4+ pts. Net = expected point difference minus 4.
              </p>
            </div>
          )}
        </div>
      )}
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
        Running simulations for transfer analysis...
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
        Recommendations powered by Monte Carlo simulations. 3-GW projected points
        from Student-t fitted distributions with FDR scaling. Always use your own judgement.
      </p>
    </div>
  );
}
