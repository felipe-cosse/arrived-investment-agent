/** App shell (§4): header with the staleness badge, the two-pane layout —
 * chat left, tabbed data panel right, stacking below `md` (R30) — and a footer
 * carrying the disclaimer and the Zillow Research attribution (§10). A typed
 * `*_result` chat event switches the data panel to the Agent tab (R18).
 */

import { useEffect, useState } from "react";
import type { ReactElement } from "react";
import ChatPanel from "./components/chat/ChatPanel";
import OfferingExplorer from "./components/data/OfferingExplorer";
import ResultPanel from "./components/data/ResultPanel";
import StalenessBadge from "./components/layout/StalenessBadge";
import TwoPane from "./components/layout/TwoPane";
import PlanBuilder from "./components/plan/PlanBuilder";
import SavedPlans from "./components/plan/SavedPlans";
import { useChatStore } from "./state/chatStore";

type Tab = "agent" | "explore" | "plan" | "saved";

const TABS: ReadonlyArray<{ id: Tab; label: string }> = [
  { id: "agent", label: "Agent results" },
  { id: "explore", label: "Explore offerings" },
  { id: "plan", label: "Plan builder" },
  { id: "saved", label: "Saved plans" },
];

function DataPanel(): ReactElement {
  const panelContent = useChatStore((s) => s.panelContent);
  const [tab, setTab] = useState<Tab>("explore");

  // Each new typed result event brings the agent's output into view (R18).
  useEffect(() => {
    if (panelContent !== null) setTab("agent");
  }, [panelContent]);

  const tabs = TABS.filter((t) => t.id !== "agent" || panelContent !== null);
  return (
    <div className="flex flex-col gap-lg">
      <nav aria-label="Data panel views" className="flex flex-wrap gap-sm">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            aria-current={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`rounded-md px-md py-sm text-label font-medium transition-colors ${
              tab === t.id
                ? "bg-accent text-surface shadow-sm"
                : "bg-surface text-secondary shadow-sm hover:text-primary"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>
      {tab === "agent" && panelContent !== null && <ResultPanel event={panelContent} />}
      {tab === "explore" && <OfferingExplorer />}
      {tab === "plan" && <PlanBuilder />}
      {tab === "saved" && <SavedPlans />}
    </div>
  );
}

export default function App(): ReactElement {
  return (
    <div className="flex min-h-screen flex-col bg-background md:h-screen md:overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-md border-b border-secondary/20 bg-surface px-lg py-md shadow-sm">
        <h1 className="text-h2 font-semibold text-primary">Arrived Investment Agent</h1>
        <StalenessBadge />
      </header>
      <TwoPane chat={<ChatPanel />} data={<DataPanel />} />
      <footer className="border-t border-secondary/20 bg-surface px-lg py-sm text-label text-secondary">
        Hypothetical projections, not investment advice. Offerings are seeded demo data · Data:
        Zillow Research.
      </footer>
    </div>
  );
}
