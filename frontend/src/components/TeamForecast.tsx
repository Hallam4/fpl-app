import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { SimulationResult } from "../api/fpl";

export function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="bg-gray-800 rounded-lg p-3 text-center">
      <p className="text-xs text-gray-400">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value.toFixed(1)}</p>
    </div>
  );
}

export default function TeamForecast({ data }: { data: SimulationResult }) {
  const chartData = data.histogram_bins.map((bin, i) => ({
    pts: bin.toFixed(0),
    count: data.histogram_counts[i],
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">GW Team Forecast</h2>
        <span className="text-xs text-gray-500">
          n={data.meta.n_simulations.toLocaleString()}
        </span>
      </div>

      {/* Simulation techniques badge bar */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-gray-500">Engine:</span>
        <span className="text-xs bg-indigo-900/60 text-indigo-300 px-2 py-0.5 rounded">
          {data.meta.distribution}
        </span>
        {data.meta.techniques.map((t) => (
          <span
            key={t}
            className="text-xs bg-gray-800 text-gray-300 px-2 py-0.5 rounded"
          >
            {t}
          </span>
        ))}
        {data.meta.variance_reduction_factor > 1 && (
          <span className="text-xs bg-emerald-900/60 text-emerald-300 px-2 py-0.5 rounded">
            {data.meta.variance_reduction_factor}x variance reduction
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <StatCard label="Mean" value={data.mean} color="text-blue-400" />
        <StatCard label="Median (P50)" value={data.median} color="text-purple-400" />
        <StatCard label="P25" value={data.p25} color="text-green-400" />
        <StatCard label="P75" value={data.p75} color="text-amber-400" />
        <StatCard label="P90" value={data.p90} color="text-red-400" />
      </div>

      <div className="bg-gray-800 rounded-xl p-4">
        <p className="text-sm text-gray-400 mb-3">Points Distribution</p>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={chartData} margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="pts"
              tick={{ fill: "#9CA3AF", fontSize: 11 }}
              label={{ value: "Points", position: "insideBottom", offset: -10, fill: "#9CA3AF", fontSize: 12 }}
            />
            <YAxis
              tick={{ fill: "#9CA3AF", fontSize: 11 }}
              label={{ value: "Simulations", angle: -90, position: "insideLeft", fill: "#9CA3AF", fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{ backgroundColor: "#1F2937", border: "none", borderRadius: "8px" }}
              labelStyle={{ color: "#E5E7EB" }}
              formatter={(value: number) => [value.toLocaleString(), "Simulations"]}
            />
            <Bar dataKey="count" fill="#7C3AED" radius={[3, 3, 0, 0]} />
            <ReferenceLine
              x={data.median.toFixed(0)}
              stroke="#A78BFA"
              strokeDasharray="4 4"
              label={{ value: "P50", fill: "#A78BFA", fontSize: 11, position: "top" }}
            />
            <ReferenceLine
              x={data.p25.toFixed(0)}
              stroke="#34D399"
              strokeDasharray="4 4"
              label={{ value: "P25", fill: "#34D399", fontSize: 11, position: "top" }}
            />
            <ReferenceLine
              x={data.p75.toFixed(0)}
              stroke="#FBBF24"
              strokeDasharray="4 4"
              label={{ value: "P75", fill: "#FBBF24", fontSize: 11, position: "top" }}
            />
            <ReferenceLine
              x={data.p90.toFixed(0)}
              stroke="#F87171"
              strokeDasharray="4 4"
              label={{ value: "P90", fill: "#F87171", fontSize: 11, position: "top" }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
