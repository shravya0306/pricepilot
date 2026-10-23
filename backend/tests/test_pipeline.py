from app.config import Settings
from app.safety import public_error, safe_http_url
from app.services.gemini_client import _parse_json
from app.services.pipeline import Dependencies, run_job
from app.services.serper import parse_shopping_response, search_shopping
from app.services.scraper import fetch_page_html
from app.state import Job
from app.text_extract import html_to_offer_text


def _settings() -> Settings:
    return Settings(
        gemini_api_key="",
        serper_api_key="",
        scraper_api_key="",
        _env_file=None,
    )


def test_shopping_parser_dedupes_merchants_and_keeps_the_lower_price():
    hits = parse_shopping_response(
        {
            "shopping": [
                {"source": "Amazon.in", "link": "https://amazon.in/a", "price": "₹15,000", "title": "Phone A"},
                {
                    "source": "amazon.in",
                    "link": "https://amazon.in/b",
                    "price": "₹14,000",
                    "title": "Phone A cheaper",
                },
                {"source": "Flipkart", "link": "https://flipkart.com/a", "price": 12000, "title": "Phone B"},
                {"source": "", "link": "https://nope.example", "price": "₹1"},
                {"source": "Croma", "link": "", "price": "₹1"},
            ]
        }
    )
    assert [(hit.merchant, hit.price, hit.url) for hit in hits] == [
        ("Amazon.in", 14000, "https://amazon.in/b"),
        ("Flipkart", 12000, "https://flipkart.com/a"),
    ]
    assert hits[0].title == "Phone A cheaper"


def test_shopping_parser_limits_unique_merchants():
    payload = {
        "shopping": [
            {"source": f"Shop {index}", "link": f"https://shop.example/{index}", "price": f"₹{1000 + index}"}
            for index in range(8)
        ]
    }
    assert len(parse_shopping_response(payload)) == 5


def test_serper_and_scraper_require_keys_without_calling_network():
    try:
        search_shopping("phone", " ")
        raised = False
    except RuntimeError as exc:
        raised = "SERPER_API_KEY" in str(exc)
    assert raised

    try:
        fetch_page_html("https://example.com", "")
        raised = False
    except RuntimeError as exc:
        raised = "SCRAPER_API_KEY" in str(exc)
    assert raised


def test_html_keeps_offer_text_and_structured_data():
    html = """
    <style>body{color:red}</style>
    <script>var tracking = 1;</script>
    <script type="application/ld+json">{"discount":"10% off"}</script>
    <p>Bank offer ₹500 off</p>
    """
    text = html_to_offer_text(html)
    assert "10% off" in text
    assert "₹500 off" in text
    assert "color:red" not in text
    assert "tracking" not in text


def test_gemini_json_parser_ignores_fences_and_fills_missing_lists():
    data = _parse_json(
        """```json
        {"bank_offers": [{"bank": "HDFC", "discount": "10% off"}]}
        ```"""
    )
    assert data["bank_offers"][0]["bank"] == "HDFC"
    assert data["coupons"] == []
    assert data["exchange_offers"] == []
    assert data["cashback_offers"] == []


def test_public_error_redacts_secrets():
    message = public_error(
        RuntimeError("http://api.scraperapi.com/?api_key=SECRETVALUE&url=https://shop.example")
    )
    assert "SECRETVALUE" not in message
    assert "api_key=***" in message
    assert safe_http_url("javascript:alert(1)") is None
    assert safe_http_url("https://shop.example/p") == "https://shop.example/p"


def test_pipeline_compares_two_lowest_reachable_merchants():
    fetched: list[str] = []

    def search(_product: str):
        from app.services.serper import ShoppingHit

        return [
            ShoppingHit("Unsafe", "javascript:alert(1)", "₹8000", "Bad", 8000),
            ShoppingHit("Missing", "https://missing.example/p", "not-a-price", "Bad", None),
            ShoppingHit("Costly", "https://costly.example/p", "₹12000", "Costly phone", 12000),
            ShoppingHit("Beta", "https://beta.example/p", "₹11000", "Beta phone", 11000),
            ShoppingHit("Alpha", "https://alpha.example/p", "₹10000", "Alpha phone", 10000),
        ]

    def fetch(url: str) -> str:
        fetched.append(url)
        return "<html><p>Bank offer ₹100 off</p></html>"

    def extract(_text: str, price: float) -> dict:
        if price == 10000:
            return {
                "bank_offers": [
                    {"bank": "HDFC", "discount": "10% off", "eligibility": "HDFC credit card"}
                ],
                "coupons": [{"code": "SAVE200", "discount": "₹200 off"}],
                "exchange_offers": [{"discount": "Up to ₹3000 off"}],
                "cashback_offers": [{"provider": "Pay Balance", "discount": "₹300 cashback"}],
            }
        return {"coupons": [{"code": "FIVE", "discount": "5% off"}]}

    job = Job("job-1", "Phone 128GB")
    run_job(
        job,
        _settings(),
        Dependencies(
            search=search,
            fetch=fetch,
            extract=extract,
            insight=lambda _deals: "Alpha checks out lower than Beta before conditional benefits.",
        ),
    )
    snapshot = job.snapshot()

    assert fetched == ["https://alpha.example/p", "https://beta.example/p"]
    assert snapshot["status"] == "completed"
    assert [deal["merchant"] for deal in snapshot["deals"]] == ["Alpha", "Beta"]
    assert snapshot["deals"][0]["summary"]["checkout_price"] == 9800
    assert snapshot["deals"][0]["summary"]["estimated_net"] == 9500
    assert snapshot["deals"][1]["summary"]["checkout_price"] == 10450
    assert "Alpha" in snapshot["insight"]
    assert any(entry["msg"] == "Top 2: Alpha, Beta" for entry in snapshot["logs"])


def test_stop_prevents_the_next_merchant_and_keeps_partial_results():
    fetched: list[str] = []
    job = Job("job-2", "Phone 128GB")

    def search(_product: str):
        from app.services.serper import ShoppingHit

        return [
            ShoppingHit("Alpha", "https://alpha.example/p", "₹10000", "Alpha", 10000),
            ShoppingHit("Beta", "https://beta.example/p", "₹11000", "Beta", 11000),
        ]

    def fetch(url: str) -> str:
        fetched.append(url)
        job.request_cancel()
        return "<p>₹100 off</p>"

    run_job(
        job,
        _settings(),
        Dependencies(
            search=search,
            fetch=fetch,
            extract=lambda _text, _price: {"coupons": [{"code": "SAVE", "discount": "₹100 off"}]},
            insight=lambda _deals: "should not be called",
        ),
    )
    snapshot = job.snapshot()
    assert fetched == ["https://alpha.example/p"]
    assert snapshot["status"] == "stopped"
    assert [deal["merchant"] for deal in snapshot["deals"]] == ["Alpha"]
    assert snapshot["deals"][0]["summary"]["checkout_price"] == 9900
    assert snapshot["insight"] is None
    assert any(entry["msg"] == "Stopped by user" for entry in snapshot["logs"])


def test_insight_failure_falls_back_to_calculated_prices():
    from app.services.serper import ShoppingHit

    def search(_product: str):
        return [
            ShoppingHit("Alpha", "https://alpha.example/p", "₹10000", "Alpha", 10000),
            ShoppingHit("Beta", "https://beta.example/p", "₹11000", "Beta", 11000),
        ]

    job = Job("job-insight", "Phone 128GB")
    run_job(
        job,
        _settings(),
        Dependencies(
            search=search,
            fetch=lambda _url: "<p>₹100 off</p>",
            extract=lambda _text, price: {
                "coupons": [{"code": "SAVE", "discount": "₹100 off" if price == 10000 else "₹50 off"}]
            },
            insight=lambda _deals: (_ for _ in ()).throw(RuntimeError("model down")),
        ),
    )
    snapshot = job.snapshot()
    assert snapshot["status"] == "completed"
    assert snapshot["deals"][0]["summary"]["checkout_price"] == 9900
    assert "Alpha" in snapshot["insight"]
    assert "Beta" in snapshot["insight"]
    assert "model down" not in snapshot["insight"]


def test_scraper_errors_are_redacted_and_do_not_invent_deals():
    job = Job("job-3", "Phone 128GB")

    def search(_product: str):
        from app.services.serper import ShoppingHit

        return [ShoppingHit("Alpha", "https://alpha.example/p", "₹10000", "Alpha", 10000)]

    def fetch(_url: str) -> str:
        raise RuntimeError("http://api.scraperapi.com/?api_key=SECRETVALUE&url=https://alpha.example/p")

    run_job(
        job,
        _settings(),
        Dependencies(search=search, fetch=fetch, extract=lambda *_args: {}, insight=lambda _deals: ""),
    )
    snapshot = job.snapshot()
    rendered = str(snapshot)
    assert snapshot["status"] == "failed"
    assert snapshot["deals"] == []
    assert "SECRETVALUE" not in rendered
