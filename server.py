#!/usr/bin/env python3
"""Match Prediction web server for Legendary FC vs Learn2Earn FC.

Zero-dependency Python 3 server using ThreadingHTTPServer and SQLite.
"""

from datetime import datetime, timezone
import hmac
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import secrets
import sqlite3
import threading
from urllib.parse import urlparse


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "predictions.db")

HOME_TEAM = "Legendary FC"
AWAY_TEAM = "Learn2Earn FC"
PRIZES = [20000, 10000, 5000]
VALID_STATUSES = {"open", "locked", "finished"}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def utc_now_iso():
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_contact(raw):
    """Validate and normalize a phone number or email address for deduplication."""
    cleaned = raw.strip()
    if "@" in cleaned:
        if not EMAIL_RE.match(cleaned) or len(cleaned) > 120:
            raise ValueError("Enter a valid email address or phone number.")
        return cleaned, "email:" + cleaned.lower()

    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 7 or len(digits) > 15:
        raise ValueError("Enter a valid phone number (7–15 digits) or email address.")
    return cleaned, "phone:" + digits


def mask_contact(raw):
    """Mask email or phone number for public display."""
    cleaned = raw.strip()
    if "@" in cleaned:
        local, domain = cleaned.split("@", 1)
        head = local[:2] if len(local) > 2 else local[:1]
        return f"{head}***@{domain}"
    if len(cleaned) <= 4:
        return "****"
    return cleaned[:3] + "****" + cleaned[-3:]


def parse_score(val, label):
    """Validate a predicted or final match score as an integer between 0 and 50."""
    if isinstance(val, bool):
        raise ValueError(f"{label} must be a whole number.")
    try:
        num = int(val)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.")
    if num < 0 or num > 50:
        raise ValueError(f"{label} must be between 0 and 50.")
    return num


class PredictionStore:
    """Thread-safe SQLite persistence and winner-ranking engine."""

    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS match_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    kickoff_label TEXT NOT NULL DEFAULT 'Venue: Mint School Pitch • 5:00 PM',
                    final_home_score INTEGER,
                    final_away_score INTEGER,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    contact TEXT NOT NULL,
                    contact_norm TEXT NOT NULL UNIQUE,
                    home_score INTEGER NOT NULL,
                    away_score INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            row = conn.execute("SELECT id FROM match_state WHERE id = 1").fetchone()
            if not row:
                conn.execute(
                    """
                    INSERT INTO match_state (
                        id, home_team, away_team, status, kickoff_label, updated_at
                    ) VALUES (1, ?, ?, 'open', 'Venue: Mint School Pitch • 5:00 PM', ?)
                    """,
                    (HOME_TEAM, AWAY_TEAM, utc_now_iso()),
                )
            else:
                conn.execute(
                    """
                    UPDATE match_state
                    SET home_team = ?,
                        away_team = ?,
                        kickoff_label = CASE
                            WHEN kickoff_label = 'Matchday Prediction' THEN 'Venue: Mint School Pitch • 5:00 PM'
                            ELSE kickoff_label
                        END
                    WHERE id = 1
                    """,
                    (HOME_TEAM, AWAY_TEAM),
                )

    def get_snapshot(self, include_contacts=False):
        """Return match state, ordered predictions, winners, and crowd statistics."""
        with self._lock, self._connect() as conn:
            match_row = conn.execute("SELECT * FROM match_state WHERE id = 1").fetchone()
            pred_rows = conn.execute(
                "SELECT * FROM predictions ORDER BY id ASC"
            ).fetchall()

        match = {
            "home_team": match_row["home_team"],
            "away_team": match_row["away_team"],
            "status": match_row["status"],
            "kickoff_label": match_row["kickoff_label"],
            "final_home_score": match_row["final_home_score"],
            "final_away_score": match_row["final_away_score"],
            "updated_at": match_row["updated_at"],
            "prizes": PRIZES,
        }

        is_finished = (
            match["status"] == "finished"
            and match["final_home_score"] is not None
            and match["final_away_score"] is not None
        )

        exact_hits = 0
        winners = []
        predictions = []
        home_picks = 0
        draw_picks = 0
        away_picks = 0
        score_counts = {}

        for idx, row in enumerate(pred_rows, start=1):
            hs = row["home_score"]
            as_ = row["away_score"]
            if hs > as_:
                home_picks += 1
            elif hs < as_:
                away_picks += 1
            else:
                draw_picks += 1

            score_key = f"{hs}-{as_}"
            score_counts[score_key] = score_counts.get(score_key, 0) + 1

            rank = None
            prize = 0
            outcome = "pending"
            if is_finished:
                if hs == match["final_home_score"] and as_ == match["final_away_score"]:
                    exact_hits += 1
                    if exact_hits <= len(PRIZES):
                        rank = exact_hits
                        prize = PRIZES[exact_hits - 1]
                        outcome = "winner"
                    else:
                        outcome = "exact_late"
                else:
                    outcome = "missed"

            entry = {
                "id": row["id"],
                "order": idx,
                "name": row["name"],
                "contact_masked": mask_contact(row["contact"]),
                "home_score": hs,
                "away_score": as_,
                "created_at": row["created_at"],
                "outcome": outcome,
                "rank": rank,
                "prize": prize,
            }
            if include_contacts:
                entry["contact"] = row["contact"]
            predictions.append(entry)
            if rank is not None:
                winners.append(entry)

        top_scores = sorted(
            ({"score": k, "count": v} for k, v in score_counts.items()),
            key=lambda x: (-x["count"], x["score"]),
        )[:5]

        return {
            "match": match,
            "stats": {
                "total": len(predictions),
                "home_picks": home_picks,
                "draw_picks": draw_picks,
                "away_picks": away_picks,
                "exact_matches": exact_hits if is_finished else 0,
                "top_scores": top_scores,
            },
            "winners": winners,
            "predictions": predictions,
        }

    def add_prediction(self, name, contact, home_score, away_score):
        """Validate and store a new prediction while predictions are open."""
        clean_name = " ".join(str(name or "").split())
        if len(clean_name) < 2 or len(clean_name) > 60:
            raise ValueError("Name must be between 2 and 60 characters.")
        clean_contact, norm_contact = normalize_contact(str(contact or ""))
        hs = parse_score(home_score, HOME_TEAM + " score")
        as_ = parse_score(away_score, AWAY_TEAM + " score")

        with self._lock, self._connect() as conn:
            match_row = conn.execute(
                "SELECT status FROM match_state WHERE id = 1"
            ).fetchone()
            if match_row["status"] != "open":
                raise PermissionError(
                    "Predictions are currently closed for this match."
                )

            created_at = utc_now_iso()
            try:
                cur = conn.execute(
                    """
                    INSERT INTO predictions (
                        name, contact, contact_norm, home_score, away_score, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (clean_name, clean_contact, norm_contact, hs, as_, created_at),
                )
            except sqlite3.IntegrityError:
                raise FileExistsError(
                    "A prediction with this phone number or email already exists."
                )

            order_num = conn.execute(
                "SELECT COUNT(*) FROM predictions WHERE id <= ?", (cur.lastrowid,)
            ).fetchone()[0]

        return {
            "id": cur.lastrowid,
            "order": order_num,
            "name": clean_name,
            "contact_masked": mask_contact(clean_contact),
            "home_score": hs,
            "away_score": as_,
            "created_at": created_at,
        }

    def update_match(self, status=None, kickoff_label=None, final_home=None, final_away=None):
        """Update match status, label, or final score."""
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM match_state WHERE id = 1").fetchone()
            new_status = status if status is not None else row["status"]
            if new_status not in VALID_STATUSES:
                raise ValueError("Status must be open, locked, or finished.")

            new_label = row["kickoff_label"]
            if kickoff_label is not None:
                cleaned_label = " ".join(str(kickoff_label).split())
                if not cleaned_label or len(cleaned_label) > 80:
                    raise ValueError("Match info must be between 1 and 80 characters.")
                new_label = cleaned_label

            new_fh = row["final_home_score"]
            new_fa = row["final_away_score"]
            if new_status == "finished":
                if final_home is None or final_away is None:
                    raise ValueError("Provide both final scores to finish the match.")
                new_fh = parse_score(final_home, HOME_TEAM + " final score")
                new_fa = parse_score(final_away, AWAY_TEAM + " final score")
            elif status in {"open", "locked"}:
                new_fh = None
                new_fa = None

            conn.execute(
                """
                UPDATE match_state
                SET status = ?, kickoff_label = ?, final_home_score = ?, final_away_score = ?, updated_at = ?
                WHERE id = 1
                """,
                (new_status, new_label, new_fh, new_fa, utc_now_iso()),
            )
        return self.get_snapshot(include_contacts=True)

    def reset_predictions(self):
        """Clear all predictions and reopen the match for a fresh round."""
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM predictions")
            conn.execute("DELETE FROM sqlite_sequence WHERE name = 'predictions'")
            conn.execute(
                """
                UPDATE match_state
                SET status = 'open', final_home_score = NULL, final_away_score = NULL, updated_at = ?
                WHERE id = 1
                """,
                (utc_now_iso(),),
            )
        return self.get_snapshot(include_contacts=True)


class AdminAuth:
    """In-memory token manager for admin actions."""

    def __init__(self, admin_pin):
        self.admin_pin = str(admin_pin)
        self._tokens = set()
        self._lock = threading.Lock()

    def login(self, pin):
        if not hmac.compare_digest(str(pin or ""), self.admin_pin):
            return None
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._tokens.add(token)
        return token

    def is_valid(self, token):
        if not token:
            return False
        with self._lock:
            return token in self._tokens


def make_handler(store, auth):
    """Bind a store and auth manager to a SimpleHTTPRequestHandler subclass."""

    class PredictionHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=STATIC_DIR, **kwargs)

        def log_message(self, format, *args):
            # Keep server logs concise.
            super().log_message(format, *args)

        def _send_json(self, code, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ValueError("Invalid Content-Length header.")
            if length <= 0 or length > 16384:
                raise ValueError("Request body must be valid JSON under 16 KB.")
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ValueError("Malformed JSON payload.")
            if not isinstance(data, dict):
                raise ValueError("JSON body must be an object.")
            return data

        def _require_admin(self):
            token = self.headers.get("X-Admin-Token", "").strip()
            if not auth.is_valid(token):
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "Admin authorization required."})
                return False
            return True

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/api/state":
                is_admin = auth.is_valid(self.headers.get("X-Admin-Token", "").strip())
                self._send_json(HTTPStatus.OK, store.get_snapshot(include_contacts=is_admin))
                return
            if path == "/api/admin/state":
                if not self._require_admin():
                    return
                self._send_json(HTTPStatus.OK, store.get_snapshot(include_contacts=True))
                return
            if path == "/":
                self.path = "/index.html"
            super().do_GET()

        def do_POST(self):
            path = urlparse(self.path).path
            try:
                if path == "/api/predictions":
                    data = self._read_json()
                    created = store.add_prediction(
                        data.get("name"),
                        data.get("contact"),
                        data.get("home_score"),
                        data.get("away_score"),
                    )
                    self._send_json(
                        HTTPStatus.CREATED,
                        {
                            "message": "Prediction recorded!",
                            "prediction": created,
                            "snapshot": store.get_snapshot(include_contacts=False),
                        },
                    )
                    return

                if path == "/api/admin/login":
                    data = self._read_json()
                    token = auth.login(data.get("pin"))
                    if not token:
                        self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "Incorrect admin PIN."})
                        return
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "token": token,
                            "snapshot": store.get_snapshot(include_contacts=True),
                        },
                    )
                    return

                if path == "/api/admin/match":
                    if not self._require_admin():
                        return
                    data = self._read_json()
                    snapshot = store.update_match(
                        status=data.get("status"),
                        kickoff_label=data.get("kickoff_label"),
                        final_home=data.get("final_home_score"),
                        final_away=data.get("final_away_score"),
                    )
                    self._send_json(HTTPStatus.OK, {"snapshot": snapshot})
                    return

                if path == "/api/admin/reset":
                    if not self._require_admin():
                        return
                    snapshot = store.reset_predictions()
                    self._send_json(HTTPStatus.OK, {"snapshot": snapshot})
                    return

                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found."})
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except PermissionError as exc:
                self._send_json(HTTPStatus.FORBIDDEN, {"error": str(exc)})
            except FileExistsError as exc:
                self._send_json(HTTPStatus.CONFLICT, {"error": str(exc)})

    return PredictionHandler


def run_server(host="127.0.0.1", port=8000, db_path=None, admin_pin=None):
    pin = admin_pin or os.environ.get("ADMIN_PIN", "2026")
    resolved_db = db_path or os.environ.get("DB_PATH", DEFAULT_DB_PATH)
    store = PredictionStore(db_path=resolved_db)
    auth = AdminAuth(pin)
    server = ThreadingHTTPServer((host, port), make_handler(store, auth))
    return server


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    default_host = "0.0.0.0" if "PORT" in os.environ else "127.0.0.1"
    host = os.environ.get("HOST", default_host)
    srv = run_server(host=host, port=port)
    print(f"Match Prediction Server running at http://{host}:{port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        srv.server_close()
