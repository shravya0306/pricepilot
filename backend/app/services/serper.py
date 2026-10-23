from dataclasses import dataclass

import httpx

from app.pricing import parse_listed_price


@dataclass(frozen=True)
class ShoppingHit:
    merchant: str
    url: str
    price_text: str
    title: str
    price: float | None


def parse_shopping_response(data: dict, limit: int = 5) -> list[ShoppingHit]:
    ordered: list[str] = []
    by_merchant: dict[str, ShoppingHit] = {}
    for item in data.get("shopping") or []:
        if not isinstance(item, dict):
            continue
        merchant = str(item.get("source") or "").strip()
        url = str(item.get("link") or "").strip()
        if not merchant or not url:
            continue
        key = merchant.casefold()
        hit = ShoppingHit(
            merchant=merchant,
            url=url,
            price_text=str(item.get("price") or ""),
            title=str(item.get("title") or "").strip(),
            price=parse_listed_price(item.get("price")),
        )
        existing = by_merchant.get(key)
        if existing is None:
            if len(ordered) >= limit:
                continue
            ordered.append(key)
            by_merchant[key] = hit
            continue
        if hit.price is not None and (existing.price is None or hit.price < existing.price):
            by_merchant[key] = ShoppingHit(
                merchant=existing.merchant,
                url=hit.url,
                price_text=hit.price_text,
                title=hit.title or existing.title,
                price=hit.price,
            )
    return [by_merchant[key] for key in ordered]


def search_shopping(product: str, api_key: str) -> list[ShoppingHit]:
    if not api_key.strip():
        raise RuntimeError("SERPER_API_KEY is not configured")
    try:
        response = httpx.post(
            "https://google.serper.dev/shopping",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": product, "gl": "in", "hl": "en"},
            timeout=30,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Serper API returned HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Serper API request failed") from exc
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Serper API returned an unexpected response")
    return parse_shopping_response(payload)
