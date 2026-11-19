# MediBill — Amruta Medicals And General Stores

This is the consolidated MediBill development package. It puts the current browser prototype, backend starter, database configuration, Docker setup, and setup instructions in one folder.

## What's included

- `frontend/`: current browser-based billing and inventory prototype (local browser storage).
- `backend/`: FastAPI starter API with persistent medicine records, batches, and sales endpoints.
- `docker-compose.yml`: PostgreSQL + API development environment.
- `.env.example`: sample configuration only; replace secrets before any deployment.

## Run the current billing prototype on macOS

1. Open this extracted folder in VS Code.
2. Open Terminal → New Terminal.
3. Run:

   ```bash
   cd frontend
   python3 -m http.server 8000
   ```
4. Open http://localhost:8000 in your browser.

The prototype currently saves its records in that browser's local storage. It is not yet wired to the API, so data will not synchronize between devices.

## Run the backend with Docker

1. Install Docker Desktop for Mac and start it.
2. In a terminal at the project root, copy `.env.example` to `.env` and change `JWT_SECRET` to a long random secret.
3. Run:

   ```bash
   docker compose up --build
   ```
4. Open http://localhost:8001/docs to inspect the API.

For local backend development without Docker:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Set `DATABASE_URL` to a local PostgreSQL URL or use the default SQLite development database.

## API starter endpoints

- `GET /health`
- `GET /store` — authenticated pharmacy profile
- `GET /inventory/summary` — authenticated stock summary (demo and verified records separated)
- `POST /auth/token` — administrator login (form-encoded username/password)
- `GET /medicines` — authenticated medicine list
- `POST /medicines` — authenticated medicine creation
- `POST /sales` — authenticated sale creation with stock deduction in a database transaction
- `GET /sales` — authenticated sale history

The initial administrator is created from `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables on first startup. Change the example credentials immediately.

## Pharmacy profile defaults

- Name: Amruta Medicals And General Stores
- Phone: 9901544875
- Email: intentionally blank
- Address: blank until supplied
- Drug licence: blank; to be entered by the store
- Currency: INR
- GST: not enabled; confirm tax treatment with a qualified accountant before issuing commercial invoices.

## Important status and limitations

This is a development package, **not a production-ready pharmacy system**. The frontend remains a local prototype and is not yet connected to the backend. Backend endpoints are an initial integration foundation and have not been security-audited or validated for commercial use. No Android app, signed Windows/macOS installer, thermal-printer integration, barcode-scanner integration, cloud deployment, automated backup service, or regulatory validation is included yet. Sample medicine data is demonstration-only. Do not use it for dispensing or live sales. Verify all medicine names, batches, expiry dates, stock, pricing, and applicable legal/tax requirements before operational use.


## Current package version

- Package: MediBill Complete Development Package v0.2.0
- Pharmacy profile: Amruta Medicals And General Stores; phone 9901544875; email/address/drug licence left blank where not supplied.
- Currency: INR; GST registration flag defaults to false. Do not charge or represent GST incorrectly; confirm invoice treatment with an accountant.
- The current HTML frontend still uses browser localStorage. It does not yet call the FastAPI endpoints.


## Latest update: UPI QR payments and interactive dashboard (v0.3.0)

- Billing supports a dynamic UPI payment QR for the exact bill amount.
- Configure the store's real UPI ID in **Settings → UPI ID**. No UPI ID is prefilled.
- Select **UPI** in Billing to display the QR and UPI app link.
- Before saving a UPI bill, the cashier must tick the payment-received verification checkbox. This is a manual safeguard only; it does not verify bank settlement automatically. Always confirm receipt in the merchant UPI app/bank account.
- QR image generation currently uses the online QR Server endpoint and therefore requires internet access. The UPI payment URI is sent to that QR service to render the code.
- Dashboard now supports 7-day, 30-day, 90-day and custom date ranges, with sales, bill counts, payment mode totals, top-selling items and stock alerts refreshed for the selected period.

**Important:** this remains a local development prototype using browser local storage. It is not connected to the FastAPI/PostgreSQL backend, does not automatically reconcile UPI transactions, and is not approved for production pharmacy billing. Demo medicine/stock data must be replaced with verified records.
