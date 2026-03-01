import { useQuery } from "@tanstack/react-query";
import { fplApi } from "../api/fpl";

const FDR_COLOR: Record<number, string> = {
  1: "bg-green-600 text-green-100",
  2: "bg-green-500 text-green-100",
  3: "bg-amber-500 text-amber-100",
  4: "bg-red-500 text-red-100",
  5: "bg-red-700 text-red-100",
};

const FDR_LEGEND = [
  { fdr: 1, label: "Very Easy" },
  { fdr: 2, label: "Easy" },
  { fdr: 3, label: "Medium" },
  { fdr: 4, label: "Hard" },
  { fdr: 5, label: "Very Hard" },
];

function FdrCell({
  fdr,
  opponent,
  isHome,
}: {
  fdr: number;
  opponent: string;
  isHome: boolean;
}) {
  return (
    <div
      className={`w-16 h-10 flex flex-col items-center justify-center rounded text-xs font-semibold select-none ${
        FDR_COLOR[fdr] ?? "bg-gray-600 text-gray-100"
      }`}
      title={`FDR ${fdr} vs ${opponent} (${isHome ? "Home" : "Away"})`}
    >
      <span className="truncate max-w-full px-1">{opponent}</span>
      <span className="opacity-75">{isHome ? "H" : "A"}</span>
    </div>
  );
}

export default function FixtureDifficulty({
  squadTeamIds,
}: {
  squadTeamIds?: Set<number>;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["fixtures"],
    queryFn: () => fplApi.getFixtures(),
  });

  if (isLoading)
    return (
      <div className="flex justify-center py-12 text-gray-400">
        Loading fixtures...
      </div>
    );
  if (error)
    return (
      <div className="text-red-400 py-8 text-center">
        Error: {(error as Error).message}
      </div>
    );
  if (!data) return null;

  const squadTeams = squadTeamIds
    ? data.teams.filter((t) => squadTeamIds.has(t.team_id))
    : [];
  const allTeams = data.teams;

  function renderTable(
    teams: typeof allTeams,
    maxH?: string
  ) {
    return (
      <div className={`overflow-x-auto ${maxH ?? ""}`}>
        <table className="min-w-full text-sm">
          <thead className="sticky top-0 bg-gray-950 z-10">
            <tr>
              <th className="text-left text-gray-400 font-normal py-2 pr-4 w-36">
                Team
              </th>
              {data!.next_gws.map((gw) => (
                <th
                  key={gw}
                  className="text-center text-gray-400 font-normal py-2 px-1 w-16"
                >
                  GW{gw}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {teams.map((team) => (
              <tr
                key={team.team_id}
                className={`border-t border-gray-800 ${
                  squadTeamIds?.has(team.team_id) ? "bg-gray-800/30" : ""
                }`}
              >
                <td className="py-1 pr-4 text-gray-300 text-xs truncate max-w-[9rem]">
                  {team.team_name}
                </td>
                {data!.next_gws.map((gw) => {
                  const fix = team.fixtures.find((f) => f.gw === gw);
                  return (
                    <td key={gw} className="py-0.5 px-1">
                      {fix ? (
                        <FdrCell
                          fdr={fix.fdr}
                          opponent={fix.opponent}
                          isHome={fix.is_home}
                        />
                      ) : (
                        <div className="w-16 h-10 flex items-center justify-center text-gray-600 text-xs">
                          —
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-bold">Fixture Difficulty — Next 6 GWs</h2>
        <div className="flex flex-wrap gap-1.5">
          {FDR_LEGEND.map(({ fdr, label }) => (
            <span
              key={fdr}
              className={`text-xs px-2 py-0.5 rounded ${FDR_COLOR[fdr]}`}
            >
              {label}
            </span>
          ))}
        </div>
      </div>

      {squadTeams.length > 0 && (
        <section>
          <h3 className="text-sm text-gray-400 font-medium mb-2">
            Your Squad ({squadTeams.length} teams)
          </h3>
          {renderTable(squadTeams)}
        </section>
      )}

      <section>
        {squadTeams.length > 0 && (
          <h3 className="text-sm text-gray-400 font-medium mb-2">All Teams</h3>
        )}
        <div className="max-h-[55vh] overflow-y-auto">
          {renderTable(allTeams)}
        </div>
      </section>
    </div>
  );
}
