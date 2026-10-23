import re
from dataclasses import dataclass
from enum import Enum

from app.schemas import OfferGroups, OfferKind, PricedOffer, PriceSummary


class DiscountMode(str, Enum):
    FIXED = "fixed"
    PERCENT = "percent"
    PERCENT_CAPPED = "percent_capped"
    UPTO_FIXED = "upto_fixed"


@dataclass(frozen=True)
class DiscountSpec:
    mode: DiscountMode
    percent: float | None = None
    amount: float | None = None
    cap: float | None = None


_PERCENT_CAPPED = re.compile(
    r"(\d+(?:\.\d+)?)\s*%"
    r"(?:\s*(?:off|instant(?:\s+discount)?|discount|cashback))?"
    r"\s*(?:up\s*to|upto)\s*"
    r"(?:₹|rs\.?|inr)?\s*"
    r"(\d[\d,]*(?:\.\d+)?)",
    re.IGNORECASE,
)
_UPTO_FIXED = re.compile(
    r"(?:up\s*to|upto)\s*(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?)",
    re.IGNORECASE,
)
_CURRENCY = re.compile(
    r"(?:₹|rs\.?|inr)\s*(\d[\d,]*(?:\.\d+)?)",
    re.IGNORECASE,
)
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)
_MIN_PURCHASE = re.compile(
    r"(?:min(?:imum)?(?:\s+\w+){0,3}\s+(?:of|above|over|worth)"
    r"|on\s+orders?\s+(?:of|above|over)"
    r"|orders?\s+above"
    r"|spend(?:ing)?\s+(?:of|above|over)?)\s*"
    r"(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?)",
    re.IGNORECASE,
)
_CONDITIONAL_HINTS = (
    "credit card",
    "debit card",
    "bank",
    "selected",
    "first order",
    "new user",
    "app only",
    "prepaid",
    "wallet",
)
_STACK_HINTS = ("stack", "extra ", "additional", "on top")


def parse_amount(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        value = float(str(raw).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if value <= 0 or value > 100_000_000:
        return None
    return value


def parse_listed_price(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    match = re.search(r"\d[\d,]*(?:\.\d+)?", str(value))
    if not match:
        return None
    return parse_amount(match.group())


def parse_min_purchase(text: str) -> float | None:
    match = _MIN_PURCHASE.search(text or "")
    if not match:
        return None
    return parse_amount(match.group(1))


def _unique_amounts(raws: list[str], exclude: float | None) -> list[float] | None:
    values: list[float] = []
    for raw in raws:
        amount = parse_amount(raw)
        if amount is None:
            continue
        if exclude is not None and abs(amount - exclude) < 0.01:
            continue
        if any(abs(amount - existing) < 0.01 for existing in values):
            continue
        values.append(amount)
    return values


def parse_discount_spec(text: str) -> DiscountSpec | None:
    source = text or ""
    minimum = parse_min_purchase(source)

    capped = _PERCENT_CAPPED.findall(source)
    if capped:
        pairs: list[tuple[float, float]] = []
        for percent_raw, cap_raw in capped:
            percent = parse_amount(percent_raw)
            cap = parse_amount(cap_raw)
            if percent is None or cap is None or percent >= 100:
                continue
            if minimum is not None and abs(cap - minimum) < 0.01:
                continue
            pair = (percent, cap)
            if pair not in pairs:
                pairs.append(pair)
        if len(pairs) != 1:
            return None
        percent, cap = pairs[0]
        return DiscountSpec(DiscountMode.PERCENT_CAPPED, percent=percent, cap=cap)

    percents = _unique_amounts(_PERCENT.findall(source), None) or []
    percents = [value for value in percents if value < 100]
    upto = _unique_amounts(_UPTO_FIXED.findall(source), minimum) or []
    currency = _unique_amounts(_CURRENCY.findall(source), minimum) or []

    if upto and not percents:
        if len(upto) != 1:
            return None
        return DiscountSpec(DiscountMode.UPTO_FIXED, amount=upto[0])

    if percents and (currency or upto):
        return None
    if len(percents) > 1 or len(currency) > 1:
        return None
    if len(percents) == 1:
        return DiscountSpec(DiscountMode.PERCENT, percent=percents[0])
    if len(currency) == 1:
        return DiscountSpec(DiscountMode.FIXED, amount=currency[0])
    return None


def discount_amount(spec: DiscountSpec, base_price: float) -> tuple[float, bool]:
    if spec.mode is DiscountMode.FIXED:
        return round(spec.amount or 0, 2), False
    if spec.mode is DiscountMode.PERCENT:
        return round(base_price * (spec.percent or 0) / 100, 2), False
    if spec.mode is DiscountMode.PERCENT_CAPPED:
        raw = base_price * (spec.percent or 0) / 100
        return round(min(raw, spec.cap or 0), 2), False
    return round(spec.amount or 0, 2), True


def evaluate_discount(text: str, base_price: float) -> tuple[str, float, bool] | None:
    spec = parse_discount_spec(text)
    if spec is None:
        return None
    value, maximum = discount_amount(spec, base_price)
    if not _realistic(value, base_price):
        return None
    return spec.mode.value, value, maximum


def _realistic(discount_value: float, base_price: float) -> bool:
    return base_price > 0 and 0 < discount_value < base_price


def _stackable(item: dict, discount: str) -> bool:
    if item.get("stackable") is True:
        return True
    lowered = discount.lower()
    return any(hint in lowered for hint in _STACK_HINTS)


def _timing(kind: OfferKind, discount: str, eligibility: str, maximum_estimate: bool) -> str:
    blob = f"{discount} {eligibility}".lower()
    if kind == "cashback" or "cashback" in blob:
        return "post_purchase"
    if kind in {"bank", "exchange"} or maximum_estimate:
        return "conditional"
    if eligibility.strip():
        return "conditional"
    if any(hint in blob for hint in _CONDITIONAL_HINTS):
        return "conditional"
    return "guaranteed"


def _eligibility(kind: OfferKind, item: dict, timing: str) -> str:
    eligibility = str(item.get("eligibility") or "").strip()
    if eligibility:
        return eligibility
    if kind == "bank":
        bank = str(item.get("bank") or "").strip()
        if bank:
            return f"Requires {bank} payment"
        return "Requires the listed bank payment"
    if kind == "exchange":
        return "Requires exchange of a qualifying device"
    if timing == "post_purchase":
        return "Credited after purchase"
    return ""


def _label(kind: OfferKind, item: dict) -> str:
    if kind == "bank":
        return str(item.get("bank") or "").strip() or "Bank offer"
    if kind == "coupon":
        return str(item.get("code") or "").strip() or "Coupon"
    if kind == "exchange":
        return "Exchange"
    return str(item.get("provider") or "").strip() or "Cashback"


def _as_dicts(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def price_offers(raw: dict, base_price: float) -> tuple[OfferGroups, list[str]]:
    notes: list[str] = []
    groups: dict[str, list[PricedOffer]] = {
        "bank_offers": [],
        "coupons": [],
        "exchange_offers": [],
        "cashback_offers": [],
    }
    buckets: list[tuple[str, OfferKind]] = [
        ("bank_offers", "bank"),
        ("coupons", "coupon"),
        ("exchange_offers", "exchange"),
        ("cashback_offers", "cashback"),
    ]

    for bucket, kind in buckets:
        for index, item in enumerate(_as_dicts(raw.get(bucket))[:8]):
            discount = str(item.get("discount") or "").strip()
            label = _label(kind, item)
            if not discount:
                notes.append(f"Skipped {label}: no discount text")
                continue
            minimum = parse_min_purchase(discount)
            if minimum is not None and base_price + 1e-9 < minimum:
                notes.append(
                    f"Skipped {label}: product price is below the minimum purchase of ₹{minimum:,.0f}"
                )
                continue
            evaluated = evaluate_discount(discount, base_price)
            if evaluated is None:
                notes.append(f"Skipped {label}: discount is unclear or not a realistic price reduction")
                continue
            _mode, discount_value, maximum_estimate = evaluated
            eligibility = _eligibility(kind, item, "guaranteed")
            timing = _timing(kind, discount, eligibility, maximum_estimate)
            if timing == "post_purchase":
                eligibility = _eligibility(kind, item, timing)
            offer = PricedOffer(
                id=f"{kind}-{index}-{len(groups[bucket])}",
                kind=kind,
                timing=timing,  # type: ignore[arg-type]
                label=label,
                discount=discount,
                eligibility=eligibility or None,
                discount_value=discount_value,
                final_price=round(base_price - discount_value, 2),
                maximum_estimate=maximum_estimate,
                stackable=_stackable(item, discount),
            )
            target = "cashback_offers" if timing == "post_purchase" else bucket
            offer = offer.model_copy(update={"id": f"{target}-{len(groups[target])}"})
            groups[target].append(offer)

    for name, offers in groups.items():
        groups[name] = sorted(offers, key=lambda offer: offer.discount_value, reverse=True)

    return OfferGroups(**groups), notes


def _best(offers: list[PricedOffer]) -> PricedOffer | None:
    if not offers:
        return None
    return max(offers, key=lambda offer: offer.discount_value)


def summarize(base_price: float, groups: OfferGroups) -> PriceSummary:
    offers = (
        groups.bank_offers
        + groups.coupons
        + groups.exchange_offers
        + groups.cashback_offers
    )
    guaranteed = [offer for offer in offers if offer.timing == "guaranteed"]
    conditional = [
        offer
        for offer in offers
        if offer.timing == "conditional" and offer.kind != "exchange"
    ]
    exchange = [offer for offer in offers if offer.kind == "exchange"]
    cashback = [offer for offer in offers if offer.timing == "post_purchase"]

    best_guaranteed = _best(guaranteed)
    best_conditional = _best(conditional)
    best_exchange = _best(exchange)
    best_cashback = _best(cashback)

    guaranteed_discount = best_guaranteed.discount_value if best_guaranteed else 0
    checkout = round(base_price - guaranteed_discount, 2)

    stacked_checkout = None
    stacked_label = None
    if (
        best_guaranteed
        and best_conditional
        and best_guaranteed.stackable
        and best_conditional.stackable
    ):
        combined = min(base_price, best_guaranteed.discount_value + best_conditional.discount_value)
        if 0 < combined < base_price:
            stacked_checkout = round(base_price - combined, 2)
            stacked_label = f"{best_guaranteed.label} + {best_conditional.label}"

    estimated_net = None
    if best_cashback is not None:
        estimated_net = round(max(0, checkout - best_cashback.discount_value), 2)

    notes: list[str] = []
    if len(guaranteed) > 1:
        notes.append("Only the best guaranteed coupon is applied. Coupons are not added together.")
    if len([offer for offer in offers if offer.kind == "bank"]) > 1:
        notes.append("Only the largest bank offer is highlighted. Bank offers are alternatives.")
    if best_guaranteed and best_conditional and stacked_checkout is None:
        notes.append(
            "The guaranteed discount and the conditional benefit are shown separately because they cannot be combined."
        )
    if stacked_checkout is not None:
        notes.append("A combined checkout is shown because both offers are marked as combinable.")
    if best_exchange is not None:
        notes.append("Exchange savings require a qualifying device and are excluded from the checkout price.")
    if best_cashback is not None:
        notes.append("Cashback is credited after purchase and is excluded from the checkout price.")
        if len(cashback) > 1:
            notes.append("Only the larger cashback is included in the estimate. Cashback offers are not added together.")

    return PriceSummary(
        base_price=base_price,
        checkout_price=checkout,
        guaranteed_discount=guaranteed_discount,
        guaranteed_label=best_guaranteed.label if best_guaranteed else None,
        best_conditional_label=best_conditional.label if best_conditional else None,
        best_conditional_price=best_conditional.final_price if best_conditional else None,
        best_exchange_label=best_exchange.label if best_exchange else None,
        best_exchange_price=best_exchange.final_price if best_exchange else None,
        cashback_value=best_cashback.discount_value if best_cashback else None,
        cashback_label=best_cashback.label if best_cashback else None,
        estimated_net=estimated_net,
        stacked_checkout=stacked_checkout,
        stacked_label=stacked_label,
        incompatible_notes=notes,
    )


def inr(value: float) -> str:
    if abs(value - round(value)) < 0.001:
        return f"₹{value:,.0f}"
    return f"₹{value:,.2f}"
