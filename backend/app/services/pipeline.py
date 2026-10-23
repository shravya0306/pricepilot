import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.config import Settings
from app.pricing import inr, price_offers, summarize
from app.safety import public_error, safe_http_url
from app.schemas import MerchantDeal, OfferGroups
from app.services.gemini_client import extract_offers, generate_insight
from app.services.scraper import fetch_page_html
from app.services.serper import ShoppingHit, search_shopping
from app.state import Job
from app.text_extract import html_to_offer_text

logger = logging.getLogger(__name__)


@dataclass
class Dependencies:
    search: Callable[[str], list[ShoppingHit]]
    fetch: Callable[[str], str]
    extract: Callable[[str, float], dict]
    insight: Callable[[list[dict]], str]


def default_dependencies(settings: Settings) -> Dependencies:
    return Dependencies(
        search=lambda product: search_shopping(product, settings.serper_api_key),
        fetch=lambda url: fetch_page_html(url, settings.scraper_api_key),
        extract=lambda text, price: extract_offers(
            text, price, settings.gemini_api_key, settings.gemini_model
        ),
        insight=lambda deals: generate_insight(
            deals, settings.gemini_api_key, settings.gemini_model
        ),
    )


def fallback_insight(deals: list[MerchantDeal]) -> str:
    if len(deals) < 2:
        return ""
    ranked = sorted(deals, key=lambda deal: (deal.summary.checkout_price, deal.price))
    best, other = ranked[0], ranked[1]
    sentences = [
        f"{best.merchant} has the lower checkout price at {inr(best.summary.checkout_price)}."
    ]
    if best.summary.guaranteed_discount > 0 and best.summary.guaranteed_label:
        sentences.append(
            f"That price includes the guaranteed offer {best.summary.guaranteed_label} "
            f"worth {inr(best.summary.guaranteed_discount)}."
        )
    sentences.append(
        f"{other.merchant} checks out at {inr(other.summary.checkout_price)} before any conditional benefit."
    )
    if best.summary.best_conditional_price is not None or other.summary.best_conditional_price is not None:
        sentences.append(
            "Conditional bank benefits and exchange values are not included in checkout prices because they depend on eligibility."
        )
    if best.summary.cashback_value or other.summary.cashback_value:
        sentences.append(
            "Post-purchase cashback is listed separately and is not subtracted from checkout prices."
        )
    return " ".join(sentences)


def run_job(job: Job, settings: Settings, deps: Dependencies | None = None) -> None:
    dependencies = deps or default_dependencies(settings)
    try:
        _execute(job, dependencies)
    except Exception as exc:
        message = public_error(exc)
        job.log(f"Error: {message}", "error")
        job.set_error(message)
        logger.warning("Search failed: %s", message)
    finally:
        if job.cancelled():
            job.set_status("stopped")
        elif job.snapshot()["deals"]:
            job.set_status("completed")
        else:
            if not job.snapshot()["error"]:
                job.set_error("No results")
            job.set_status("failed")


def _execute(job: Job, deps: Dependencies) -> None:
    if job.cancelled():
        job.log("Stopped by user", "warning")
        return

    job.log("Searching shopping results", "info")
    hits = deps.search(job.product)
    if not hits:
        job.log("No shopping results found", "error")
        job.set_error("No shopping results found")
        return

    valid: list[tuple[ShoppingHit, str]] = []
    for hit in hits:
        if hit.price is None:
            job.log(f"{hit.merchant}: invalid price", "warning")
            continue
        url = safe_http_url(hit.url)
        if url is None:
            job.log(f"{hit.merchant}: invalid product link", "warning")
            continue
        valid.append((hit, url))

    ordered = sorted(valid, key=lambda item: item[0].price or 0)
    chosen: list[tuple[ShoppingHit, str, str]] = []
    for hit, url in ordered:
        if job.cancelled() or len(chosen) >= 2:
            break
        job.log(f"Opening {hit.merchant}", "info")
        try:
            html = deps.fetch(url)
        except Exception as exc:
            message = public_error(exc)
            job.log(f"{hit.merchant} failed: {message}", "warning")
            logger.warning("Page fetch failed for %s: %s", hit.merchant, message)
            continue
        price = hit.price or 0
        job.log(f"{hit.merchant}: {inr(price)}", "success")
        chosen.append((hit, url, html))

    if not chosen:
        if job.cancelled():
            job.log("Stopped by user", "warning")
            return
        job.log("No shopping results found", "error")
        job.set_error("No shopping results found")
        return

    if len(chosen) == 1:
        job.log(f"Top result: {chosen[0][0].merchant}", "success")
    else:
        names = ", ".join(hit.merchant for hit, _url, _html in chosen)
        job.log(f"Top 2: {names}", "success")

    built: list[MerchantDeal] = []
    for hit, url, html in chosen:
        deal = _build_deal(job, deps, hit, url, html)
        built.append(deal)
        job.add_deal(deal.model_dump())

    if job.cancelled():
        job.log("Stopped by user", "warning")
        return
    if len(built) < 2:
        return

    job.log("Preparing recommendation", "info")
    payload = [deal.model_dump() for deal in built]
    try:
        text = deps.insight(payload)
    except Exception as exc:
        message = public_error(exc)
        job.log(f"Insight used calculated comparison: {message}", "warning")
        logger.warning("Insight failed: %s", message)
        text = fallback_insight(built)
    if job.cancelled():
        job.log("Stopped by user", "warning")
        return
    if text.strip():
        job.set_insight(text.strip()[:1200])


def _build_deal(
    job: Job,
    deps: Dependencies,
    hit: ShoppingHit,
    url: str,
    html: str,
) -> MerchantDeal:
    price = hit.price or 0
    job.log(f"Processing {hit.merchant}", "info")
    job.log("Extracting offers from page HTML", "info")
    try:
        raw = deps.extract(html_to_offer_text(html), price)
    except Exception as exc:
        message = public_error(exc)
        job.log(f"Offer extraction failed: {message}", "warning")
        logger.warning("Offer extraction failed for %s: %s", hit.merchant, message)
        raw = {}

    groups, notes = price_offers(raw if isinstance(raw, dict) else {}, price)
    for note in notes:
        job.log(note, "info")
    if _offer_count(groups) == 0:
        job.log("No offers found", "info")
    else:
        job.log("Final offers ready", "success")

    return MerchantDeal(
        merchant=hit.merchant,
        title=hit.title,
        price=price,
        product_url=url,
        offers=groups,
        summary=summarize(price, groups),
    )


def _offer_count(groups: OfferGroups) -> int:
    return (
        len(groups.bank_offers)
        + len(groups.coupons)
        + len(groups.exchange_offers)
        + len(groups.cashback_offers)
    )
