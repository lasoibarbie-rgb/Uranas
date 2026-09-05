# Uranas Global V3

Business website + client/debt management + M-Pesa STK Push + receipts + monthly invoice generation.

## Render web service
Build:
`pip install -r requirements.txt`

Start:
`gunicorn app:app`

## Render PostgreSQL
Set `DATABASE_URL` to the PostgreSQL Internal Database URL.

## Environment variables
Required for admin:
- `SECRET_KEY`
- `ADMIN_PASSWORD` (or `ADMIN_PASSWORD_HASH`)

M-Pesa production:
- `MPESA_ENV=production`
- `MPESA_CONSUMER_KEY`
- `MPESA_CONSUMER_SECRET`
- `MPESA_PASSKEY`
- `MPESA_TILL=9393003`
- `MPESA_SHORTCODE=9393003`
- `MPESA_TRANSACTION_TYPE=CustomerBuyGoodsOnline`
- `MPESA_CALLBACK_BASE_URL=https://YOUR-RENDER-URL.onrender.com`

Optional:
- `CRON_SECRET`

## Monthly invoices
The app generates invoices for active recurring service/bin items on the 30th of each month.
Set a Render Cron Job to run daily or on the 30th:
`python -c "import app; app.generate_monthly_invoices()"`

The app prevents duplicate invoices for the same client/month.

## Important M-Pesa note
STK Push requires a Daraja application and production credentials/approval from Safaricom. The code is wired for Daraja and uses the configured Till 9393003, but real production credentials must be supplied in Render Environment Variables. The callback URL must be publicly reachable over HTTPS.
