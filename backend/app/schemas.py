from typing import Literal

from pydantic import BaseModel, Field, field_validator


LogType = Literal["info", "success", "warning", "error"]
JobStatus = Literal["running", "completed", "stopped", "failed"]
OfferKind = Literal["bank", "coupon", "exchange", "cashback"]
OfferTiming = Literal["guaranteed", "conditional", "post_purchase"]


class SearchRequest(BaseModel):
    product: str = Field(min_length=2, max_length=200)

    @field_validator("product")
    @classmethod
    def normalize_product(cls, value: str) -> str:
        cleaned = " ".join(value.replace("\x00", " ").split())
        if len(cleaned) < 2:
            raise ValueError("Enter a product name with at least 2 characters")
        return cleaned


class LogEntry(BaseModel):
    ts: str
    msg: str
    type: LogType


class PricedOffer(BaseModel):
    id: str
    kind: OfferKind
    timing: OfferTiming
    label: str
    discount: str
    eligibility: str | None = None
    discount_value: float
    final_price: float
    maximum_estimate: bool = False
    stackable: bool = False


class OfferGroups(BaseModel):
    bank_offers: list[PricedOffer] = Field(default_factory=list)
    coupons: list[PricedOffer] = Field(default_factory=list)
    exchange_offers: list[PricedOffer] = Field(default_factory=list)
    cashback_offers: list[PricedOffer] = Field(default_factory=list)


class PriceSummary(BaseModel):
    base_price: float
    checkout_price: float
    guaranteed_discount: float = 0
    guaranteed_label: str | None = None
    best_conditional_label: str | None = None
    best_conditional_price: float | None = None
    best_exchange_label: str | None = None
    best_exchange_price: float | None = None
    cashback_value: float | None = None
    cashback_label: str | None = None
    estimated_net: float | None = None
    stacked_checkout: float | None = None
    stacked_label: str | None = None
    incompatible_notes: list[str] = Field(default_factory=list)


class MerchantDeal(BaseModel):
    merchant: str
    title: str = ""
    price: float
    product_url: str
    offers: OfferGroups
    summary: PriceSummary


class JobCreated(BaseModel):
    job_id: str


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    product: str
    logs: list[LogEntry]
    deals: list[MerchantDeal]
    insight: str | None = None
    error: str | None = None
    stop_requested: bool = False
