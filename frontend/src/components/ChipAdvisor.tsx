import { useQuery } from "@tanstack/react-query";
import { fplApi, ChipGW } from "../api/fpl";

function rankColor(rank: number, total: number): string {
  if (rank <= 2) return "text-green-400";
  if (rank >= total - 1) return "text-red-400";
  return "text-gray-400";
}

function rankBg(rank: number, total: number): string {
  if (rank === 1) return "bg-green-900/30";
  if (rank === 2) return "bg-green-900/15";
  if (rank >= total - 1) return "bg-red-900/15";
  return "";
}

export default function ChipAdvisor({ teamId }: { teamId: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["chips", teamId],
    queryFn: () => fplApi.getChips(teamId),
  });

  if (isLoading)
    return (
      <div className="flex justify-center py-8 text-gray-400">
        Analysing chip strategy...
      </div>
    );
  if (error)
    return (
      <div className="text-red-400 py-4 text-center">
        Error: {(error as Error).message}
      </div>
    );
  if (!data) return null;

  const { advice } = data;
  const total = advice.gw_breakdown.length;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Chip Strategy Advisor</h2>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-gray-800 rounded-xl p-4 border border-blue-800/40">
          <p className="text-xs text-gray-400 mb-1">Best Bench Boost</p>
          <p className="text-2xl font-bold text-blue-400">GW {advice.best_bb_gw}</p>
          <p className="text-sm text-gray-400">+{advice.best_bb_score.toFixed(1)} bench pts</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-amber-800/40">
          <p className="text-xs text-gray-400 mb-1">Best Triple Captain</p>
          <p className="text-2xl font-bold text-amber-400">GW {advice.best_tc_gw}</p>
          <p className="text-sm text-gray-400">+{advice.best_tc_uplift.toFixed(1)} extra pts</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-emerald-800/40">
          <p className="text-xs text-gray-400 mb-1">Best Free Hit</p>
          <p className="text-2xl font-bold text-emerald-400">GW {advice.best_fh_gw}</p>
          <p className="text-sm text-gray-400">+{advice.best_fh_gain.toFixed(1)} vs current XI</p>
        </div>
      </div>

      {/* Breakdown table */}
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-gray-400 text-xs">
              <th className="text-left py-2 px-3 font-normal">GW</th>
              <th className="text-right py-2 px-3 font-normal">BB pts</th>
              <th className="text-right py-2 px-3 font-normal">TC pts</th>
              <th className="text-right py-2 px-3 font-normal">FH gain</th>
            </tr>
          </thead>
          <tbody>
            {advice.gw_breakdown.map((gw: ChipGW) => (
              <tr key={gw.gw} className="border-t border-gray-800">
                <td className="py-1.5 px-3 text-gray-300 font-medium">GW {gw.gw}</td>
                <td className={`py-1.5 px-3 text-right font-medium ${rankColor(gw.bb_rank, total)} ${rankBg(gw.bb_rank, total)}`}>
                  {gw.bb_score.toFixed(1)}
                  {gw.bb_rank === 1 && <span className="ml-1 text-[10px]">best</span>}
                </td>
                <td className={`py-1.5 px-3 text-right font-medium ${rankColor(gw.tc_rank, total)} ${rankBg(gw.tc_rank, total)}`}>
                  {gw.tc_uplift.toFixed(1)}
                  {gw.tc_rank === 1 && <span className="ml-1 text-[10px]">best</span>}
                </td>
                <td className={`py-1.5 px-3 text-right font-medium ${rankColor(gw.fh_rank, total)} ${rankBg(gw.fh_rank, total)}`}>
                  {gw.fh_gain.toFixed(1)}
                  {gw.fh_rank === 1 && <span className="ml-1 text-[10px]">best</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-500">
        BB = sum of bench expected pts. TC = best player's extra captain value.
        FH = best possible XI minus your current XI. Based on Monte Carlo simulations.
      </p>
    </div>
  );
}
