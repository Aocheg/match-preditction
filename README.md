# Legendary FC vs Learn2Earn FC — Match Prediction Site

A full-stack match score prediction web application built with Python's standard library (`ThreadingHTTPServer` + `sqlite3`) and vanilla HTML/CSS/JavaScript.

## Rules & Prizes
- **Match:** Legendary FC vs Learn2Earn FC
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
- `HOST` (default `127.0.0.1`, set to `0.0.0.0` to share on your local network)
- `ADMIN_PIN` (default `2026` — change this before hosting publicly!)

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
