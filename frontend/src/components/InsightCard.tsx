import { formatInr } from "../format";
import type { MerchantDeal } from "../types";

interface InsightCardProps {
  insight: string;
  bestDeal: MerchantDeal | null;
}

export function InsightCard({ insight, bestDeal }: InsightCardProps) {
  return (
    <section className="insight">
      <h2>AI Deal Recommendation</h2>
      {bestDeal ? (
        <p className="best-value">
          <span className="status-dot" aria-hidden="true" />
          Best value: {bestDeal.merchant} at {formatInr(bestDeal.summary.checkout_price)} checkout
        </p>
      ) : null}
      <p>{insight}</p>
    </section>
  );
}
