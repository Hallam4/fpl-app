import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import TeamView from "./components/TeamView";
import TransferRecommender from "./components/TransferRecommender";
import FixtureDifficulty from "./components/FixtureDifficulty";
import SimulationChart from "./components/SimulationChart";
import CaptainPicker from "./components/CaptainPicker";
import { fplApi } from "./api/fpl";

type Tab = "squad" | "transfers" | "fixtures" | "simulate" | "captain";

const TABS: { id: Tab; label: string }[] = [
  { id: "squad", label: "Squad" },
  { id: "transfers", label: "Transfers" },
  { id: "fixtures", label: "Fixtures" },
  { id: "simulate", label: "Simulate" },
  { id: "captain", label: "Captain" },
];

function TeamIdForm({ onSubmit }: { onSubmit: (id: number) => void }) {
  const [input, setInput] = useState("");

  const handleSubmit = () => {
    const id = parseInt(input.trim(), 10);
    if (!isNaN(id) && id > 0) onSubmit(id);
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8">
      <div className="max-w-md w-full space-y-6">
        <div className="text-center">
          <h1 className="text-4xl font-extrabold text-purple-400">FPL Advisor</h1>
          <p className="text-gray-400 mt-2">
            Enter your Fantasy Premier League team ID to get started.
          </p>
        </div>
        <div className="bg-gray-800 rounded-xl p-6 space-y-4">
          <label className="block text-sm text-gray-300">
            Your FPL Team ID
            <p className="text-xs text-gray-500 mt-0.5">
              Find it in the FPL website URL:{" "}
              <span className="text-gray-300">/entry/</span>
              <strong>1234567</strong>/
            </p>
          </label>
          <input
            type="number"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. 1234567"
            className="w-full bg-gray-700 text-white rounded-lg px-4 py-3 text-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
          />
          <button
            onClick={handleSubmit}
            disabled={!input.trim()}
            className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white font-bold py-3 rounded-lg transition-colors"
          >
            Analyse My Team
          </button>
        </div>
      </div>
    </div>
  );
}

function FixturesTab({ teamId }: { teamId: number }) {
  // Fetch squad to get player team short names for the fixture heatmap highlight
  const { data: teamData } = useQuery({
    queryKey: ["team", teamId],
    queryFn: () => fplApi.getTeam(teamId),
  });

  // Fetch fixtures to resolve short names → team IDs
  const { data: fixturesData } = useQuery({
    queryKey: ["fixtures"],
    queryFn: () => fplApi.getFixtures(),
  });

  let squadTeamIds: Set<number> | undefined;
  if (teamData && fixturesData) {
    const squadShortNames = new Set(teamData.squad.map((p) => p.team));
    squadTeamIds = new Set(
      fixturesData.teams
        .filter((t) => squadShortNames.has(t.team_short_name))
        .map((t) => t.team_id)
    );
  }

  return <FixtureDifficulty squadTeamIds={squadTeamIds} />;
}

function MainApp({ teamId, onReset }: { teamId: number; onReset: () => void }) {
  const [activeTab, setActiveTab] = useState<Tab>("squad");

  const { data: teamData } = useQuery({
    queryKey: ["team", teamId],
    queryFn: () => fplApi.getTeam(teamId),
  });

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-gray-900 border-b border-gray-800 px-4 py-3 flex items-center gap-4">
        <h1 className="text-xl font-extrabold text-purple-400">FPL Advisor</h1>
        {teamData && (
          <span className="text-sm text-gray-400">
            {teamData.team_name} &middot; GW{teamData.current_gw}
          </span>
        )}
        <button
          onClick={onReset}
          className="ml-auto text-sm text-gray-400 hover:text-white transition-colors"
        >
          Change Team
        </button>
      </header>

      <nav className="bg-gray-900 border-b border-gray-800 px-4 flex gap-1 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors border-b-2 ${
              activeTab === tab.id
                ? "border-purple-500 text-purple-400"
                : "border-transparent text-gray-400 hover:text-white"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="flex-1 p-4 md:p-6 max-w-6xl mx-auto w-full">
        {activeTab === "squad" && <TeamView teamId={teamId} />}
        {activeTab === "transfers" && <TransferRecommender teamId={teamId} />}
        {activeTab === "fixtures" && <FixturesTab teamId={teamId} />}
        {activeTab === "simulate" && <SimulationChart teamId={teamId} />}
        {activeTab === "captain" && <CaptainPicker teamId={teamId} />}
      </main>
    </div>
  );
}

export default function App() {
  const [teamId, setTeamId] = useState<number | null>(null);

  if (!teamId) {
    return <TeamIdForm onSubmit={setTeamId} />;
  }

  return <MainApp teamId={teamId} onReset={() => setTeamId(null)} />;
}
