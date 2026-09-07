# Uranas Global V4.1 — Existing System Upgrade

Built directly on the uploaded Uranas Global V3.1 source.

## New V4.1 features
- **Clients → Import Clients** button is visible in the existing Clients page.
- Import client information from CSV, XLS or XLSX.
- Required: Name. Optional: Phone, Email, Location, Service, Notes.
- Matching client names are updated rather than duplicated.
- Client data is only accessible behind the admin login.
- **Website Photos** admin page for Bin and BNB image uploads.
- Published Bin and BNB images appear on the public home page.
- Admin can remove public images.
- Existing dashboard, debts, invoices, M-Pesa payment page, historical import and styling are retained.
- Service/payment WhatsApp notifications use the client's stored phone number, not a poster/business number.

## Deploy
Use this as the code in the same GitHub repository connected to your current Render service. Do not create a new repository unless you specifically want a separate site.

For uploaded photos to survive Render deploys/restarts, configure a Render persistent disk and set `UPLOAD_DIR` to a folder on that disk, e.g. `/opt/render/project/src/uploads`.

The app automatically adds the new `location` field to an existing Client table and creates the WebsiteMedia table.

Never put passwords/API keys in GitHub. Keep them in Render environment variables.
