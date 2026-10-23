# PricePilot rebuilt

PricePilot compares live Indian shopping listings for one product, reads the two lowest reachable product pages, and separates guaranteed discounts from conditional benefits and post-purchase cashback.

This folder is a new implementation. It does not replace `pricepilot_improvized`.

## Stack

- Frontend: React, TypeScript, Vite
- Backend: Python, FastAPI
- Search: Serper Shopping (`https://google.serper.dev/shopping`, India, English)
- Product pages: ScraperAPI with JavaScript rendering, premium proxies, and `country_code=in`
- Offer reading and the written recommendation: Google Gemini

API keys are read only by the backend from environment variables.

## Project layout

```text
pricepilot-rebuilt/
├── backend/
│   ├── app/
│   │   ├── main.py              # HTTP API
│   │   ├── pricing.py           # Discount, cap, eligibility, and stacking rules
│   │   ├── text_extract.py      # Offer text and JSON-LD from product HTML
│   │   └── services/
│   │       ├── serper.py
│   │       ├── scraper.py
│   │       ├── gemini_client.py
│   │       └── pipeline.py      # Search job
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    ├── package.json
    └── .env.example
```

## Configure

1. Create `backend/.env` from `backend/.env.example`.
2. Set `GEMINI_API_KEY`, `SERPER_API_KEY`, and `SCRAPER_API_KEY`.
3. Leave `frontend/.env` empty during local development. The Vite dev server proxies `/api` to `http://127.0.0.1:8001`.

Do not put API keys in frontend code or in `VITE_` variables.

`GEMINI_MODEL` defaults to `models/gemini-2.5-flash-lite`, the model used by the original app.

## Install and run

Use two terminals. Python 3.11 or newer is required. The commands below are for Windows PowerShell.

Backend:

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env and add the three API keys.
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

The API health check is `http://127.0.0.1:8001/api/health`.

On this machine, Uvicorn’s default `127.0.0.1:8000` bind failed with Windows `WinError 10013` while another process already held that port. `127.0.0.1:8001` is permitted and is the port the frontend proxy uses.

## What a search does

1. `POST /api/search` with `{ "product": "..." }` starts a job and returns `{ "job_id": "..." }`.
2. The backend asks Serper Shopping for up to five distinct merchants.
3. It keeps listings with a readable price and an `http` or `https` link, cheapest first.
4. It downloads product HTML through ScraperAPI until two pages succeed or the candidates run out.
5. Gemini extracts bank offers, coupons, exchange offers, and cashback from that page text. The page is treated as untrusted data.
6. The backend recalculates every discount. Gemini does not decide the final price.
7. `GET /api/jobs/{job_id}` returns logs, deals, and, when two deals exist, a recommendation.
8. `POST /api/jobs/{job_id}/stop` asks the job to stop before the next merchant or before the recommendation.

Checkout price subtracts only the best guaranteed instant discount. These are not folded into that price:

- Bank offers and other conditional benefits, unless both the coupon and the bank offer are explicitly combinable. A combined price is then shown separately.
- Exchange offers, including "up to" amounts, because they need a qualifying device.
- Cashback, which is estimated from the checkout price and labeled as post-purchase.

Unclear offers, discounts that do not produce a positive price below the listed price, and offers below a stated minimum purchase are skipped and mentioned in the log.

The dashboard keeps the original search, start, stop, live logs, two-deal comparison, purchase confirmation, and recommendation panel.

## Test

From `backend`, with the virtual environment active:

```powershell
python -m pytest
```

From `frontend`:

```powershell
npm run build
```

The automated tests do not call Serper, ScraperAPI, or Gemini. A passing test run does not prove that live credentials or merchant pages work. Run a search in the browser after the keys are configured to verify the live integrations.

## API responses

Successful search creation returns HTTP 202. Job status is `running`, `completed`, `stopped`, or `failed`. Invalid product text returns HTTP 422. An unknown job returns HTTP 404. More than three running searches returns HTTP 429.

Errors use FastAPI's `detail` field. Provider failures are reported as short messages. Query strings that would contain an API key are not returned to the browser.
