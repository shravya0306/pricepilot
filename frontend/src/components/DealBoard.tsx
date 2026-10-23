import { useEffect, useState } from "react";
import { formatInr } from "../format";
import type { MerchantDeal, PricedOffer } from "../types";

interface DealBoardProps {
  deals: MerchantDeal[];
  selected: string | null;
  onSelect: (merchant: string) => void;
}

export function DealBoard({ deals, selected, onSelect }: DealBoardProps) {
  const [confirming, setConfirming] = useState(false);
  const [opened, setOpened] = useState(false);
  const selectedDeal = deals.find((deal) => deal.merchant === selected) ?? null;

  useEffect(() => {
    setConfirming(false);
    setOpened(false);
  }, [selected, deals.length]);

  const bestPrice = deals.reduce<number | null>((lowest, deal) => {
    if (lowest === null || deal.summary.checkout_price < lowest) {
      return deal.summary.checkout_price;
    }
    return lowest;
  }, null);

  return (
    <section className="compare">
      <h2>Price Comparison</h2>
      <p className="section-copy">
        The two cheapest valid deals, ranked by final checkout price. Guaranteed discounts
        are included. Bank offers, exchange value, and cashback stay separate until their
        conditions are met.
      </p>
      <div className="compare-table">
        <div className="compare-head">
          <span>Deal</span>
          <span>Pricing</span>
          <span>Action</span>
        </div>
        {deals.length ? (
          deals.map((deal) => {
            const isSelected = deal.merchant === selected;
            const isBest = bestPrice !== null && deal.summary.checkout_price === bestPrice;
            return (
              <article
                key={deal.merchant}
                className={isSelected ? "compare-row selected" : "compare-row"}
              >
                <div className="deal-cell">
                  <label>
                    <input
                      type="radio"
                      name="merchant"
                      checked={isSelected}
                      onChange={() => onSelect(deal.merchant)}
                    />
                    <strong>{deal.merchant}</strong>
                    {isBest ? <span className="best-pill">Best value</span> : null}
                  </label>
                  {deal.title ? <p className="listing-title">{deal.title}</p> : null}
                  <p className="meta">{detailLine(deal)}</p>
                </div>
                <div className="price-cell">
                  <p>
                    <span>Listed</span>
                    <strong>{formatInr(deal.summary.base_price)}</strong>
                  </p>
                  <p>
                    <span>Discount</span>
                    <strong className={deal.summary.guaranteed_discount > 0 ? "savings" : undefined}>
                      {deal.summary.guaranteed_discount > 0
                        ? formatInr(deal.summary.guaranteed_discount)
                        : "None"}
                    </strong>
                  </p>
                  <p>
                    <span>Checkout</span>
                    <strong>{formatInr(deal.summary.checkout_price)}</strong>
                  </p>
                </div>
                <div className="action-cell">
                  {isSelected && selectedDeal && !confirming && !opened ? (
                    <button type="button" onClick={() => setConfirming(true)}>
                      Open Best Deal
                    </button>
                  ) : null}
                </div>
                {isSelected && selectedDeal && confirming && !opened ? (
                  <div className="confirm">
                    <p>Open best deal in browser?</p>
                    <div className="actions">
                      <a
                        className="yes"
                        href={selectedDeal.product_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={() => {
                          setOpened(true);
                          setConfirming(false);
                        }}
                      >
                        Yes, open {selectedDeal.merchant}
                      </a>
                      <button type="button" className="stop" onClick={() => setConfirming(false)}>
                        No, continue exploring
                      </button>
                    </div>
                  </div>
                ) : null}
              </article>
            );
          })
        ) : (
          <p className="empty">Deals will appear here after a search finds prices.</p>
        )}
      </div>
      {deals.map((deal) => (
        <article key={`${deal.merchant}-detail`} className="deal-detail">
          <h3>{deal.merchant}</h3>
          <Summary deal={deal} />
          <OfferList deal={deal} />
        </article>
      ))}
    </section>
  );
}

function detailLine(deal: MerchantDeal): string {
  const count =
    deal.offers.bank_offers.length +
    deal.offers.coupons.length +
    deal.offers.exchange_offers.length +
    deal.offers.cashback_offers.length;
  if (count === 0) {
    return "No offers listed on this page";
  }
  return count === 1 ? "1 offer listed" : `${count} offers listed`;
}

function Summary({ deal }: { deal: MerchantDeal }) {
  const summary = deal.summary;
  return (
    <div className="summary">
      <p>
        <span>Base price</span>
        <strong>{formatInr(summary.base_price)}</strong>
      </p>
      <p>
        <span>Checkout price</span>
        <strong>{formatInr(summary.checkout_price)}</strong>
      </p>
      {summary.guaranteed_label ? (
        <p>
          <span>Guaranteed</span>
          <strong>
            {summary.guaranteed_label} · {formatInr(summary.guaranteed_discount)}
          </strong>
        </p>
      ) : null}
      {summary.best_conditional_price != null ? (
        <p>
          <span>If eligible</span>
          <strong>
            {summary.best_conditional_label}: {formatInr(summary.best_conditional_price)}
          </strong>
        </p>
      ) : null}
      {summary.best_exchange_price != null ? (
        <p>
          <span>Exchange</span>
          <strong>
            {summary.best_exchange_price != null && deal.offers.exchange_offers.some((offer) => offer.maximum_estimate)
              ? `As low as ${formatInr(summary.best_exchange_price)}`
              : formatInr(summary.best_exchange_price)}
          </strong>
        </p>
      ) : null}
      {summary.stacked_checkout != null ? (
        <p>
          <span>Combined, if allowed</span>
          <strong>
            {summary.stacked_label}: {formatInr(summary.stacked_checkout)}
          </strong>
        </p>
      ) : null}
      {summary.estimated_net != null ? (
        <p>
          <span>Est. net after cashback</span>
          <strong>
            {summary.cashback_label}: {formatInr(summary.estimated_net)}
          </strong>
        </p>
      ) : null}
      {summary.incompatible_notes.length ? (
        <ul>
          {summary.incompatible_notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function OfferList({ deal }: { deal: MerchantDeal }) {
  const offers = [
    ...deal.offers.bank_offers,
    ...deal.offers.coupons,
    ...deal.offers.exchange_offers,
    ...deal.offers.cashback_offers,
  ];
  const groups: Array<{ title: string; timing: PricedOffer["timing"] }> = [
    { title: "Guaranteed discounts", timing: "guaranteed" },
    { title: "Conditional benefits", timing: "conditional" },
    { title: "Post-purchase cashback", timing: "post_purchase" },
  ];

  if (!offers.length) {
    return <p className="empty">No offers available</p>;
  }

  return (
    <div className="offer-groups">
      {groups.map((group) => {
        const items = offers.filter((offer) => offer.timing === group.timing);
        if (!items.length) {
          return null;
        }
        return (
          <section key={group.timing}>
            <h4>{group.title}</h4>
            <div className="offer-scroll">
              {items.map((offer) => (
                <article key={offer.id} className="offer">
                  <div className="offer-top">
                    <strong>
                      {kindMark(offer.kind)} {offer.label}
                    </strong>
                    <span className={`badge badge-${offer.timing}`}>{timingLabel(offer.timing)}</span>
                  </div>
                  <p>{offer.discount}</p>
                  {offer.eligibility ? <p className="eligibility">{offer.eligibility}</p> : null}
                  <p className="final">{finalLabel(offer)}</p>
                </article>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function kindMark(kind: PricedOffer["kind"]): string {
  if (kind === "bank") return "Bank";
  if (kind === "coupon") return "Coupon";
  if (kind === "exchange") return "Exchange";
  return "Cashback";
}

function timingLabel(timing: PricedOffer["timing"]): string {
  if (timing === "guaranteed") return "Guaranteed";
  if (timing === "conditional") return "Conditional";
  return "After purchase";
}

function finalLabel(offer: PricedOffer): string {
  const price = formatInr(offer.final_price);
  if (offer.timing === "post_purchase") {
    return `Est. net ${price}`;
  }
  if (offer.maximum_estimate) {
    return `As low as ${price}`;
  }
  if (offer.timing === "conditional") {
    return `If eligible: ${price}`;
  }
  return `Final: ${price}`;
}
