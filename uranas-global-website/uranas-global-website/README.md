# Uranas Global Investment Limited — Website

A responsive, static website for Uranas Global Investment Limited.

## Files

- `index.html` — website structure/content
- `style.css` — design and responsive styling
- `script.js` — mobile menu + current year
- `assets/` — Uranas logo and supplied promotional images

## Run locally

No Python, Flask, Node.js or database is required.

### Option 1 — simplest
Double-click `index.html` and open it in your browser.

### Option 2 — local server
If you have Python installed:

```bash
python -m http.server 8000
```

Then open:

`http://localhost:8000`

## GitHub Pages

1. Create a new GitHub repository.
2. Upload **all files and the assets folder**.
3. Go to **Settings → Pages**.
4. Under Build and deployment choose **Deploy from a branch**.
5. Select `main` and `/ (root)`.
6. Save.
7. GitHub will give you a public website link.

## Render

Create a **Static Site** on Render and connect this GitHub repository.

- Build Command: leave blank
- Publish Directory: `.`
- No environment variables are needed.

## Important

This version is intentionally static, so it avoids Flask/Jinja template errors. It can be hosted directly on GitHub Pages and on Render.

Before launch, replace the Facebook URL in `index.html` with the exact Uranas Global Services Facebook page URL if you have it.
