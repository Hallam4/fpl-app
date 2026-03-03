import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { fplApi } from "../api/fpl";
import { StatCard } from "./TeamForecast";

interface Props {
  playerId: number;
  playerName: string;
  gwExpected: number[];
  gameweeks: number[];
}

export default function PlayerDetailPanel({
  playerId,
  playerName,
  gwExpected,
  gameweeks,
}: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["player-detail", playerId],
    queryFn: () => fplApi.getPlayerDetail(playerId),
    staleTime: 5 * 60 * 1000,
  });

  const projectionData = gameweeks.map((gw, i) => ({
    gw: `GW${gw}`,
    pts: gwExpected[i],
  }));

  return (
    <tr className="border-t border-gray-700 bg-gray-900/60">
      <td colSpan={4 + gameweeks.length} className="p-4">
        <div className="space-y-4">
          <p className="text-sm font-semibold text-gray-300">
            {playerName} — Detail
          </p>

          {isLoading && (
            <div className="text-xs text-gray-400">Loading simulation...</div>
          )}
          {error && (
            <div className="text-xs text-red-400">
              Error: {(error as Error).message}
            </div>
          )}

          {data && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                <StatCard label="Mean" value={data.mean} color="text-blue-400" />
                <StatCard label="Median" value={data.median} color="text-purple-400" />
                <StatCard label="P25" value={data.p25} color="text-green-400" />
                <StatCard label="P75" value={data.p75} color="text-amber-400" />
                <StatCard label="P90" value={data.p90} color="text-red-400" />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Next-GW Histogram */}
                <div className="bg-gray-800 rounded-xl p-4">
                  <p className="text-xs text-gray-400 mb-2">
                    GW{data.gameweek} Points Distribution
                    <span className="ml-2 text-gray-500">
                      n={data.n_simulations.toLocaleString()}
                    </span>
                  </p>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart
                      data={data.histogram_bins.map((bin, i) => ({
                        pts: bin.toFixed(1),
                        count: data.histogram_counts[i],
                      }))}
                      margin={{ top: 5, right: 10, bottom: 20, left: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis
                        dataKey="pts"
                        tick={{ fill: "#9CA3AF", fontSize: 10 }}
                        label={{
                          value: "Points",
                          position: "insideBottom",
                          offset: -10,
                          fill: "#9CA3AF",
                          fontSize: 11,
                        }}
                      />
                      <YAxis tick={{ fill: "#9CA3AF", fontSize: 10 }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#1F2937",
                          border: "none",
                          borderRadius: "8px",
                        }}
                        labelStyle={{ color: "#E5E7EB" }}
                        formatter={(value: number) => [
                          value.toLocaleString(),
                          "Simulations",
                        ]}
                      />
                      <Bar dataKey="count" fill="#7C3AED" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* 10-GW Projection */}
                <div className="bg-gray-800 rounded-xl p-4">
                  <p className="text-xs text-gray-400 mb-2">
                    {gameweeks.length}-GW Projected Points
                  </p>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart
                      data={projectionData}
                      margin={{ top: 5, right: 10, bottom: 20, left: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis
                        dataKey="gw"
                        tick={{ fill: "#9CA3AF", fontSize: 10 }}
                      />
                      <YAxis tick={{ fill: "#9CA3AF", fontSize: 10 }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#1F2937",
                          border: "none",
                          borderRadius: "8px",
                        }}
                        labelStyle={{ color: "#E5E7EB" }}
                        formatter={(value: number) => [
                          (value as number).toFixed(1),
                          "Expected pts",
                        ]}
                      />
                      <Bar dataKey="pts" fill="#8B5CF6" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </>
          )}
        </div>
      </td>
    </tr>
  );
}
