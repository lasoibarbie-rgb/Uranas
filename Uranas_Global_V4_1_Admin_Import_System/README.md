# Uranas Global V4.1
Admin-managed Flask website.

Features:
- Admin-only client database
- CSV/XLS/XLSX client import from Admin
- Manual client entry
- Admin uploads bin and BNB images
- Uploaded images appear publicly on the website
- Admin-only bin records
- Render deployment configuration

Client import columns:
Name (required), Phone, Email, Location, Service, Notes.

Deploy:
1. Push this folder to GitHub.
2. Create a Render Web Service from the repo.
3. Build: pip install -r requirements.txt
4. Start: gunicorn app:app
5. Set ADMIN_USERNAME and ADMIN_PASSWORD in Render.
6. Open /login.

The Render disk stores SQLite and uploaded images persistently.
