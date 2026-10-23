import re

from bs4 import BeautifulSoup


_KEYWORDS = ("offer", "bank", "coupon", "cashback", "exchange", "discount")


def html_to_offer_text(html: str, limit: int = 24000) -> str:
    soup = BeautifulSoup((html or "")[:1_500_000], "html.parser")
    embedded: list[str] = []
    for script in soup.find_all("script"):
        script_type = (script.get("type") or "").lower()
        content = script.string or script.get_text() or ""
        lowered = content.lower()
        if "ld+json" in script_type or any(keyword in lowered for keyword in _KEYWORDS):
            embedded.append(content[:4000])
        script.decompose()
    for tag in soup(["style", "noscript"]):
        tag.decompose()
    visible = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", f"{visible} {' '.join(embedded)}").strip()
    return _focus(text, limit)


def _focus(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    lowered = text.lower()
    pieces: list[str] = []
    for keyword in _KEYWORDS:
        start = 0
        hits = 0
        while hits < 4:
            index = lowered.find(keyword, start)
            if index < 0:
                break
            pieces.append(text[max(0, index - 350) : min(len(text), index + 500)])
            start = index + len(keyword)
            hits += 1
    if not pieces:
        return text[:limit]
    return " ... ".join(pieces)[:limit]
