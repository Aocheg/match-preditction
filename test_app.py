"""Integration and unit tests for the match prediction backend."""

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from server import run_server


class PredictionServerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "test.db")
        self.server = run_server(
            host="127.0.0.1", port=0, db_path=self.db_path, admin_pin="secret99"
        )
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmpdir.cleanup()

    def _req(self, method, path, body=None, token=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["X-Admin-Token"] = token
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read().decode("utf-8"))

    def test_prediction_flow_dedup_lock_and_top3_prizes(self):
        status, initial = self._req("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(initial["match"]["home_team"], "Legendary FC")
        self.assertEqual(initial["match"]["away_team"], "Learn2Earn FC")
        self.assertEqual(initial["match"]["prizes"], [20000, 10000, 5000])

        # Submit 5 predictions: 4 exact (2-1), 1 wrong (0-0)
        entries = [
            ("Ada", "08011112222", 2, 1),
            ("Bola", "bola@example.com", 0, 0),
            ("Chidi", "08033334444", 2, 1),
            ("Dapo", "dapo@example.com", 2, 1),
            ("Efe", "08055556666", 2, 1),
        ]
        for idx, (name, contact, hs, as_) in enumerate(entries, start=1):
            code, res = self._req(
                "POST",
                "/api/predictions",
                {"name": name, "contact": contact, "home_score": hs, "away_score": as_},
            )
            self.assertEqual(code, 201)
            self.assertEqual(res["prediction"]["order"], idx)
            # Public response masks raw contact
            self.assertNotEqual(res["prediction"]["contact_masked"], contact)

        # Duplicate phone (with dashes) and duplicate email (uppercase) must fail with 409
        code_dup_phone, _ = self._req(
            "POST",
            "/api/predictions",
            {"name": "Ada Clone", "contact": "0801-111-2222", "home_score": 1, "away_score": 1},
        )
        self.assertEqual(code_dup_phone, 409)
        code_dup_email, _ = self._req(
            "POST",
            "/api/predictions",
            {"name": "Bola Clone", "contact": "BOLA@example.com", "home_score": 1, "away_score": 1},
        )
        self.assertEqual(code_dup_email, 409)

        # Public state does not expose full unmasked contact
        _, pub_state = self._req("GET", "/api/state")
        self.assertNotIn("contact", pub_state["predictions"][0])

        # Wrong admin PIN rejected
        bad_code, _ = self._req("POST", "/api/admin/login", {"pin": "wrong"})
        self.assertEqual(bad_code, 401)

        # Valid admin login returns token and unmasked contacts
        ok_code, login_res = self._req("POST", "/api/admin/login", {"pin": "secret99"})
        self.assertEqual(ok_code, 200)
        token = login_res["token"]
        self.assertEqual(login_res["snapshot"]["predictions"][0]["contact"], "08011112222")

        # Locking predictions blocks new submissions
        lock_code, _ = self._req(
            "POST", "/api/admin/match", {"status": "locked"}, token=token
        )
        self.assertEqual(lock_code, 200)
        blocked_code, _ = self._req(
            "POST",
            "/api/predictions",
            {"name": "Late", "contact": "08099990000", "home_score": 2, "away_score": 1},
        )
        self.assertEqual(blocked_code, 403)

        # Finishing match with 2-1 awards first 3 exact predictors: Ada, Chidi, Dapo
        fin_code, fin_res = self._req(
            "POST",
            "/api/admin/match",
            {"status": "finished", "final_home_score": 2, "final_away_score": 1},
            token=token,
        )
        self.assertEqual(fin_code, 200)
        winners = fin_res["snapshot"]["winners"]
        self.assertEqual(len(winners), 3)
        self.assertEqual(
            [(w["name"], w["rank"], w["prize"]) for w in winners],
            [("Ada", 1, 20000), ("Chidi", 2, 10000), ("Dapo", 3, 5000)],
        )
        # 4th exact hit (Efe) is marked exact_late with 0 prize
        efe = fin_res["snapshot"]["predictions"][4]
        self.assertEqual(efe["name"], "Efe")
        self.assertEqual(efe["outcome"], "exact_late")
        self.assertEqual(efe["prize"], 0)

        # Reset clears predictions and reopens
        rst_code, rst_res = self._req("POST", "/api/admin/reset", {}, token=token)
        self.assertEqual(rst_code, 200)
        self.assertEqual(rst_res["snapshot"]["stats"]["total"], 0)
        self.assertEqual(rst_res["snapshot"]["match"]["status"], "open")


if __name__ == "__main__":
    unittest.main()
