/** Renders the typed `*_result` SSE events as data-panel components (R18):
 * one exhaustive switch over `ResultEvent` with a never-typed default (R29),
 * mapping each §8 tool result onto the explorer/plan components.
 */

import type { ReactElement } from "react";
import { humanize, shortDate } from "../../lib/format";
import type { ResultEvent } from "../../types/events";
import PlanSummary from "../plan/PlanSummary";
import SavedPlans from "../plan/SavedPlans";
import MarketContextCard from "./MarketContextCard";
import OfferingCard from "./OfferingCard";
import OfferingDetail from "./OfferingDetail";
import ReturnsChart from "./ReturnsChart";

/** Compile-time backstop: a new ResultEvent variant fails here first (R29). */
function assertNever(event: never): never {
  throw new Error(`unhandled result event: ${JSON.stringify(event)}`);
}

function body(event: ResultEvent): ReactElement {
  switch (event.type) {
    case "offerings_result":
      return (
        <div className="grid gap-md sm:grid-cols-2 xl:grid-cols-3">
          {event.result.offerings.map((offering) => (
            <OfferingCard key={offering.id} offering={offering} />
          ))}
        </div>
      );
    case "offering_details_result":
      return <OfferingDetail details={event.result} />;
    case "returns_result":
      return (
        <ReturnsChart
          returns={event.result.returns}
          title={`${event.result.offering_id} · last ${event.result.months} months`}
        />
      );
    case "market_context_result":
      return <MarketContextCard market={event.result.market} context={event.result} />;
    case "plan_result":
      return <PlanSummary plan={event.result} />;
    case "plan_saved_result":
      if ("feasible" in event.result) {
        return <PlanSummary plan={event.result} />;
      }
      return (
        <div className="flex flex-col gap-lg">
          <p className="rounded-md bg-success/10 px-md py-sm text-label text-success">
            Saved “{event.result.name ?? event.result.id}” on{" "}
            {shortDate(event.result.created_at)} · data as of {shortDate(event.result.data_as_of)}
          </p>
          <PlanSummary plan={event.result.output} />
        </div>
      );
    case "saved_plans_result":
      return <SavedPlans />;
    default:
      return assertNever(event);
  }
}

export default function ResultPanel({ event }: { event: ResultEvent }): ReactElement {
  return (
    <div className="flex flex-col gap-md">
      <p className="text-label text-secondary">Agent tool · {humanize(event.tool)}</p>
      {body(event)}
    </div>
  );
}
