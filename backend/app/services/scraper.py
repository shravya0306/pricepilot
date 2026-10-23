import httpx


def fetch_page_html(url: str, api_key: str) -> str:
    if not api_key.strip():
        raise RuntimeError("SCRAPER_API_KEY is not configured")
    try:
        response = httpx.get(
            "http://api.scraperapi.com/",
            params={
                "api_key": api_key,
                "url": url,
                "render": "true",
                "premium": "true",
                "country_code": "in",
            },
            timeout=70,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"ScraperAPI returned HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("ScraperAPI request failed") from exc
    return response.text
