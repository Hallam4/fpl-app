import { useQuery } from "@tanstack/react-query";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { fplApi } from "../api/fpl";

function grade(score: number): { label: string; color: string } {
  if (score < 0.1) return { label: "Excellent", color: "text-emerald-400" };
  if (score < 0.2) return { label: "Good", color: "text-green-400" };
  if (score < 0.25) return { label: "Fair", color: "text-amber-400" };
  return { label: "Poor", color: "text-red-400" };
}

export default function BrierScore({ teamId }: { teamId: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["brier", teamId],
    queryFn: () => fplApi.getBrier(teamId),
  });

  if (isLoading)
    return (
      <div className="text-gray-500 text-sm py-4">
        Loading calibration data...
      </div>
    );
  if (error) return null; // silently hide if no data
  if (!data || data.brier_score === null) {
    return (
      <div className="bg-gray-800 rounded-xl p-4 mt-6">
        <h3 className="text-sm font-semibold text-gray-400 mb-1">
          Prediction Calibration (Brier Score)
        </h3>
        <p className="text-xs text-gray-500">
          No completed gameweeks with predictions yet. Run simulations each GW
          and calibration data will build up over time.
        </p>
      </div>
    );
  }

  const { label, color } = grade(data.brier_score);

  const calibrationData = data.calibration.map((b) => ({
    predicted: +(b.predicted_avg * 100).toFixed(1),
    actual: +(b.actual_rate * 100).toFixed(1),
    count: b.count,
  }));

  return (
    <div className="space-y-4 mt-6">
      <h3 className="text-sm font-semibold text-gray-400">
        Prediction Calibration
      </h3>

      {/* Score cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <p className="text-xs text-gray-400">Brier Score</p>
          <p className={`text-xl font-bold ${color}`}>
            {data.brier_score.toFixed(4)}
          </p>
          <p className={`text-xs ${color}`}>{label}</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <p className="text-xs text-gray-400">Points MSE</p>
          <p className="text-xl font-bold text-blue-400">
            {data.mse!.toFixed(2)}
          </p>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <p className="text-xs text-gray-400">GWs Tracked</p>
          <p className="text-xl font-bold text-purple-400">
            {data.gw_details.length}
          </p>
        </div>
      </div>

      {/* Calibration chart: predicted probability vs actual frequency */}
      {calibrationData.length > 0 && (
        <div className="bg-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-400 mb-3">
            Calibration Plot — P(4+ pts) predicted vs actual
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 25, left: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="predicted"
                type="number"
                domain={[0, 100]}
                tick={{ fill: "#9CA3AF", fontSize: 11 }}
                label={{
                  value: "Predicted %",
                  position: "insideBottom",
                  offset: -15,
                  fill: "#9CA3AF",
                  fontSize: 12,
                }}
              />
              <YAxis
                dataKey="actual"
                type="number"
                domain={[0, 100]}
                tick={{ fill: "#9CA3AF", fontSize: 11 }}
                label={{
                  value: "Actual %",
                  angle: -90,
                  position: "insideLeft",
                  fill: "#9CA3AF",
                  fontSize: 12,
                }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1F2937",
                  border: "none",
                  borderRadius: "8px",
                }}
                formatter={(v: number, name: string) => [
                  `${v}%`,
                  name === "actual" ? "Actual" : "Predicted",
                ]}
                labelFormatter={() => ""}
              />
              {/* Perfect calibration line */}
              <ReferenceLine
                segment={[
                  { x: 0, y: 0 },
                  { x: 100, y: 100 },
                ]}
                stroke="#6B7280"
                strokeDasharray="4 4"
              />
              <Scatter data={calibrationData} fill="#7C3AED" />
            </ScatterChart>
          </ResponsiveContainer>
          <p className="text-[10px] text-gray-600 text-center mt-1">
            Dashed line = perfect calibration. Dots closer to line = better
            predictions.
          </p>
        </div>
      )}

      {/* Per-GW breakdown */}
      {data.gw_details.length > 0 && (
        <div>
          <p className="text-xs text-gray-400 mb-2">Per-Gameweek Breakdown</p>
          <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
            {data.gw_details.map((gw) => {
              const g = grade(gw.brier_score);
              return (
                <div
                  key={gw.gw}
                  className="flex items-center gap-3 bg-gray-800 rounded px-3 py-1.5"
                >
                  <span className="text-xs text-gray-400 w-10">
                    GW{gw.gw}
                  </span>
                  <span className={`text-xs font-medium w-16 ${g.color}`}>
                    {gw.brier_score.toFixed(4)}
                  </span>
                  <span className="text-xs text-gray-500">
                    MSE {gw.mse.toFixed(1)}
                  </span>
                  <span className="text-xs text-gray-600 ml-auto">
                    {gw.n_players} players
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
