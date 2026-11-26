# Fellows vs Mentors — Volleyball Match Prediction Site

A full-stack volleyball match score prediction web application built with Python's standard library (`ThreadingHTTPServer` + `sqlite3`) and vanilla HTML/CSS/JavaScript.

## Rules & Prizes
- **Match:** Fellows vs Mentors (Volleyball)
- **Venue & Time:** Leef Center Volleyball Court • 5:00 PM
- **Prizes (first 3 exact-score predictions, ranked strictly by server arrival order):**
  - **1st:** ₦20,000
  - **2nd:** ₦10,000
  - **3rd:** ₦5,000
- **Duplicate prevention:** One prediction per phone number or email address (normalized before storage). Public views mask contact info; authenticated admins see full contact details for prize payout.

## Run locally
```bash
cd /home/student/match-prediction
python3 server.py
```
Then open `http://127.0.0.1:8000` in your browser.

### Environment options
- `PORT` (default `8000`)
- `HOST` (defaults to `0.0.0.0` when `PORT` is set by a cloud host, otherwise `127.0.0.1`)
- `DB_PATH` (default `./predictions.db`)
- `ADMIN_PIN` (default `2026` — change this before hosting publicly!)

## Host Live (Render — Free Tier)
Because this app saves predictions and timestamps on the server (`server.py` + SQLite), use a Python host rather than GitHub Pages:
1. Push your latest commit to GitHub (`https://github.com/Aocheg/match-preditction`).
2. Sign in to [render.com](https://render.com) with GitHub -> **New +** -> **Web Service** -> select `Aocheg/match-preditction`.
3. Confirm settings:
   - **Runtime:** Python 3
   - **Build Command:** *(leave empty)*
   - **Start Command:** `python3 server.py`
4. Under **Environment Variables**, add `ADMIN_PIN` with your own secret PIN, then click **Deploy Web Service**. Render will give you a public `https://...onrender.com` link to share.

## Admin Controls
Click **Admin Panel** in the header or footer and sign in with the `ADMIN_PIN` to:
- Update the match label (e.g. kickoff date/time)
- **Open** or **Lock** predictions before kickoff
- Enter the **Final Score** and publish the top 3 winners automatically
- View unmasked winner contacts, export CSV, or reset for a new match

## Run automated tests
```bash
cd /home/student/match-prediction
python3 -m unittest test_app.py -v
```
