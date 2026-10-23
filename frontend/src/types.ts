export type LogType = "info" | "success" | "warning" | "error";
export type JobStatus = "running" | "completed" | "stopped" | "failed";
export type OfferKind = "bank" | "coupon" | "exchange" | "cashback";
export type OfferTiming = "guaranteed" | "conditional" | "post_purchase";

export interface LogEntry {
  ts: string;
  msg: string;
  type: LogType;
}

export interface PricedOffer {
  id: string;
  kind: OfferKind;
  timing: OfferTiming;
  label: string;
  discount: string;
  eligibility: string | null;
  discount_value: number;
  final_price: number;
  maximum_estimate: boolean;
  stackable: boolean;
}

export interface OfferGroups {
  bank_offers: PricedOffer[];
  coupons: PricedOffer[];
  exchange_offers: PricedOffer[];
  cashback_offers: PricedOffer[];
}

export interface PriceSummary {
  base_price: number;
  checkout_price: number;
  guaranteed_discount: number;
  guaranteed_label: string | null;
  best_conditional_label: string | null;
  best_conditional_price: number | null;
  best_exchange_label: string | null;
  best_exchange_price: number | null;
  cashback_value: number | null;
  cashback_label: string | null;
  estimated_net: number | null;
  stacked_checkout: number | null;
  stacked_label: string | null;
  incompatible_notes: string[];
}

export interface MerchantDeal {
  merchant: string;
  title: string;
  price: number;
  product_url: string;
  offers: OfferGroups;
  summary: PriceSummary;
}

export interface JobState {
  job_id: string;
  status: JobStatus;
  product: string;
  logs: LogEntry[];
  deals: MerchantDeal[];
  insight: string | null;
  error: string | null;
  stop_requested: boolean;
}
