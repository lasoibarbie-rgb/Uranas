# URANAS GLOBAL V4 — Admin + Import

Fresh standalone Flask system.

## Included
- Client dashboard
- CSV/XLSX/XLS client import
- Automatic column matching
- Duplicate-safe client + county updates
- Client phone stored per client
- Bin image uploads
- BNB image uploads
- Image captions
- Service-notification preparation using the CLIENT'S stored phone number
- CSV export
- M-Pesa Till 9393003 displayed in dashboard
- Render-ready Gunicorn setup

## Render
Build: `pip install -r requirements.txt`
Start: `gunicorn app:app`

## Important
The notification screen deliberately does not pretend to send an SMS/WhatsApp message. It records/prepares the notification for the selected client's stored number. Actual automatic delivery needs a messaging provider/API.

SQLite is used for a zero-cost starter. For permanent production data on Render, use a persistent PostgreSQL database or a persistent disk.
