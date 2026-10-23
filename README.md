# PricePilot

**AI-powered price comparison for Indian shopping --- compare listings
and estimate the effective price after coupons, bank offers, exchange
deals, and cashback.**

-   **Live demo:** https://pricepilot-lime-theta.vercel.app
-   **GitHub repository:** https://github.com/shravya0306/pricepilot
-   **Backend API:** https://pricepilot-uu1b.onrender.com
-   **Author:** [Shravya H Somayaji](https://www.linkedin.com/in/shravya-somayaji-38b051357/) ·
    [GitHub](https://github.com/shravya0306)

> Note: Render's free instance may spin down after inactivity, so the
> first request after a quiet period can take longer.

```{=html}
<!-- Optional: add a screenshot at docs/screenshot.png after capturing a completed search. -->
```
```{=html}
<!-- ![PricePilot screenshot](docs/screenshot.png) -->
```
## The problem

A listed price is rarely the final price you pay. Product pages may
advertise coupons, bank offers, exchange deals, and cashback, making it
difficult to distinguish guaranteed discounts from benefits with
conditions. PricePilot compares product listings and separates checkout
discounts from conditional or post-purchase benefits.

## What it does

-   Searches for product listings across Indian merchants using Google
    Shopping results.
-   Attempts to read the product pages of the two lowest-priced eligible
    listings.
-   Extracts bank offers, coupons, exchange offers, and cashback from
    product-page text.
-   Calculates checkout price and displays conditional benefits
    separately.
-   Generates a short recommendation comparing the deals.
-   Supports stopping a search and viewing live progress logs.

## Key design decision: AI reads; code calculates

Language models can interpret messy offer text, but arithmetic and
eligibility rules should be deterministic. PricePilot separates these
responsibilities:

1.  **Gemini extracts offer details** from product-page text.
2.  **Python recalculates discounts** using the rules in `pricing.py`,
    including caps, minimum-purchase requirements, eligibility, and
    stacking. The model does not determine the final price.
3.  **Scraped page content is treated as untrusted input** to reduce the
    risk of prompt injection.

Unclear offers, offers that do not meet minimum purchase requirements,
and discounts that cannot be validated are skipped rather than guessed.

### How prices are classified

  -----------------------------------------------------------------------
  Benefit                 Included in checkout    Notes
                          price?                  
  ----------------------- ----------------------- -----------------------
  Guaranteed instant      Yes, according to the   Applied only when the
  discount                implemented rules       offer is validated

  Bank offers and other   No                      Shown separately;
  conditional benefits                            combined pricing is
                                                  shown only when
                                                  compatibility is
                                                  established

  Exchange offers         No                      Require an eligible
                                                  device; "up to" amounts
                                                  are conditional

  Cashback                No                      Shown separately as a
                                                  post-purchase benefit
  -----------------------------------------------------------------------

## How a search works

``` mermaid
flowchart LR
    A[React UI: enter product] --> B[FastAPI: create search job]
    B --> C[Serper Shopping: find listings]
    C --> D[ScraperAPI: fetch product pages]
    D --> E[Gemini: extract offers]
    E --> F[pricing.py: recalculate discounts]
    F --> G[Gemini: write recommendation]
    G --> H[UI polls job status and shows results]
```

## Tech stack

  Layer                    Technology
  ------------------------ --------------------------------------
  Frontend                 React, TypeScript, Vite
  Backend                  Python, FastAPI
  Product search           Serper Shopping API
  Product-page retrieval   ScraperAPI
  AI                       Google Gemini
  Testing                  pytest and frontend production build

## Engineering details

-   **Asynchronous jobs:** `POST /api/search` returns a job ID; the UI
    polls `GET /api/jobs/{job_id}`; `POST /api/jobs/{job_id}/stop`
    requests a stop.
-   **Rate limiting:** the backend limits concurrent searches and can
    return HTTP 429 when the limit is reached.
-   **Secrets stay server-side:** API keys belong in backend environment
    variables and local `.env` files, never in frontend code or GitHub.
-   **Error handling:** invalid input and missing jobs return
    appropriate API errors; provider failures are reported to the UI.

## Project structure

``` text
pricepilot/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── pricing.py
│   │   ├── text_extract.py
│   │   └── services/
│   │       ├── serper.py
│   │       ├── scraper.py
│   │       ├── gemini_client.py
│   │       └── pipeline.py
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    ├── package.json
    └── .env.example
```

## Getting started

### Requirements

-   Python 3.11 or newer
-   Node.js and npm
-   API keys for Gemini, Serper, and ScraperAPI

### 1. Backend

From the repository root:

``` powershell
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux instead:
# source .venv/bin/activate

pip install -r requirements.txt
Copy-Item .env.example .env
```

Add your actual API keys to `backend/.env` using the variable names
documented in `backend/.env.example`. Do not commit this file.

Start the local API:

``` powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Health check: http://127.0.0.1:8001/api/health

### 2. Frontend

In a second terminal, from the repository root:

``` powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. In development, Vite proxies `/api` to the
backend on port `8001`; leave `VITE_API_BASE` empty locally unless you
intentionally configure a different API origin.

### 3. Tests and build

Run from the repository root:

``` powershell
cd backend
python -m pytest
cd ..\frontend
npm run build
```

Automated tests do not necessarily verify live third-party API access.
Run a real product search to confirm that the configured provider keys
and integrations work.

## Deployment

-   **Frontend:** deployed on Vercel from the `frontend` directory.
-   **Backend:** deployed as a Render Web Service from the `backend`
    directory.
-   **Frontend API setting:** set `VITE_API_BASE` in Vercel Production
    to `https://pricepilot-uu1b.onrender.com`.
-   **CORS:** the backend must allow the deployed frontend origin
    `https://pricepilot-lime-theta.vercel.app`.

To publish changes, commit and push to the `main` branch. Render and
Vercel are configured to auto-deploy from GitHub; check that each
deployment succeeds, then test the live website.

``` powershell
git add .
git commit -m "Describe your change"
git push
```

## Limitations and future work

-   Results depend on third-party APIs and merchant page layouts; some
    pages may not be accessible and will be skipped.
-   AI offer extraction may misread unusual wording. Ambiguous offers
    are skipped rather than guessed.
-   Prices change frequently; verify the final price and offer
    conditions on the merchant's website before purchasing.
-   Potential next steps: price history, price-drop alerts, caching to
    reduce API calls, and broader merchant coverage.

## Note

This is an educational project. Use scraping responsibly and respect
applicable merchant terms of service.
