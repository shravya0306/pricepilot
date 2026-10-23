import re
from urllib.parse import urlsplit


def safe_http_url(url: str) -> str | None:
    candidate = (url or "").strip()
    if not candidate:
        return None
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate


def public_error(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    text = re.sub(r"(api[_-]?key=)[^&\s]+", r"\1***", text, flags=re.IGNORECASE)
    text = re.sub(
        r"((?:X-API-KEY|authorization)['\"]?\s*[:=]\s*)\S+",
        r"\1***",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"AIza[\w-]{10,}", "***", text)
    if len(text) > 300:
        text = text[:300] + "..."
    return text
