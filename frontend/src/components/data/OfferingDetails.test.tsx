import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Offering, RegionMetric } from "../../types/domain";
import OfferingCard from "./OfferingCard";
import OfferingFacts from "./OfferingFacts";
import { formatRegionValue } from "./RegionInfoPanel";

const OFFERING: Offering = {
  id: "arrived-the-chloe",
  name: "The Chloe",
  market: "Fayetteville, AR",
  property_type: "single_family",
  status: "available",
  share_price_usd: 10,
  min_investment_usd: 100,
  projected_dividend_yield: 0.037,
  projected_appreciation: 0.04,
  funded_pct: 0.88,
  property_value_usd: 320_000,
  leverage_pct: 0,
  source_url: "https://arrived.com/properties/the-chloe",
  thumbnail_url: "https://cdn.arrivedhomes.com/the-chloe.jpg",
  description: "A four-bedroom rental home.",
  purchase_price_usd: 320_000,
  monthly_rent_usd: 1_995,
  annual_rent_usd: 23_940,
  annual_platform_fee_usd: 1_920,
  closing_offering_holding_costs_usd: 21_512,
  property_improvements_reserves_usd: 28_000,
  investor_count: 921,
  bedrooms: 4,
  bathrooms: 3,
  square_feet: 2_021,
  year_built: 2018,
  street_address: "5066 West Claxton Circle",
  postal_code: "72704",
  lease_status: "OCCUPIED",
  lease_end_date: "2028-02-29T00:00:00.000Z",
  hold_period_min_years: 5,
  hold_period_max_years: 7,
  debt_amount_usd: 0,
  debt_interest_pct: 0,
  as_of: "2026-07-12T12:00:00Z",
};

function metric(unit: RegionMetric["unit"], value: number): RegionMetric {
  return {
    metric: "sample",
    label: "Sample",
    value,
    unit,
    observation_month: "2026-01",
    retrieved_at: "2026-02-01T00:00:00Z",
    source: { id: "sample", name: "Source", url: "https://example.com" },
  };
}

describe("offering presentation", () => {
  it("renders compact real-data metrics with separate safe actions", () => {
    const html = renderToStaticMarkup(
      <OfferingCard offering={OFFERING} onSelect={vi.fn()} />,
    );

    expect(html).toContain("Exterior of The Chloe");
    expect(html).toContain("Rent / mo");
    expect(html).toContain("$1,995");
    expect(html).toContain("Purchase price");
    expect(html).toContain("Investors");
    expect(html).toContain("role=\"progressbar\"");
    expect(html).toContain("View details");
    expect(html).toContain("href=\"https://arrived.com/properties/the-chloe\"");
    expect(html).toContain("target=\"_blank\"");
    expect(html).toContain("rel=\"noopener noreferrer\"");
    expect(html).not.toMatch(/<button[^>]*>(?:(?!<\/button>)[\s\S])*<a /);
  });

  it("separates gross rent, annual AUM fee, and one-time costs", () => {
    const html = renderToStaticMarkup(<OfferingFacts offering={OFFERING} />);

    expect(html).toContain("Annual gross rent");
    expect(html).toContain("$23,940");
    expect(html).toContain("Annual AUM fee");
    expect(html).toContain("$1,920");
    expect(html).toContain("Closing &amp; holding costs");
    expect(html).toContain("$21,512");
    expect(html).toContain("5066 West Claxton Circle");
    expect(html).toContain("does not provide a total annual operating-expense figure");
    expect(html).not.toContain("Annual expenses");
  });

  it("formats each public-data unit according to its source contract", () => {
    expect(formatRegionValue(metric("usd_per_month", 1_995))).toBe("$1,995");
    expect(formatRegionValue(metric("percent", 4.2))).toBe("4.2%");
    expect(formatRegionValue(metric("people", 1_240_000))).toBe("1.2M");
  });
});
