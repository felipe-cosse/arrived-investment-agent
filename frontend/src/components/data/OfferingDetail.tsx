/** Full offering drill-down: source-backed facts, return history, and metro data. */

import type { ReactElement } from "react";
import type { OfferingDetails } from "../../api/client";
import { shortDate } from "../../lib/format";
import OfferingCard from "./OfferingCard";
import OfferingFacts from "./OfferingFacts";
import RegionInfoPanel from "./RegionInfoPanel";
import ReturnsChart from "./ReturnsChart";

interface OfferingDetailProps {
  details: OfferingDetails;
  onBack?: () => void;
}

export default function OfferingDetail({ details, onBack }: OfferingDetailProps): ReactElement {
  return (
    <div className="flex flex-col gap-lg">
      {onBack !== undefined ? (
        <div>
          <button
            type="button"
            onClick={onBack}
            className="rounded-md px-sm py-sm text-label font-medium text-accent hover:bg-accent/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            ← All offerings
          </button>
        </div>
      ) : null}
      <div className="grid items-start gap-lg lg:grid-cols-2">
        <OfferingCard offering={details.offering} />
        <ReturnsChart returns={details.history} title="Last 12 months" />
      </div>
      <OfferingFacts offering={details.offering} />
      <RegionInfoPanel offeringId={details.offering.id} />
      <p className="text-label text-secondary">
        Offering data as of {shortDate(details.offering.as_of)} · source: Arrived public catalogue.
      </p>
    </div>
  );
}
