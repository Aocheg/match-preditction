"""Integration and unit tests for the Fellows vs Mentors volleyball prediction backend."""

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

    def test_progression_flow_validation_lock_and_top3_prizes(self):
        status, initial = self._req("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(initial["match"]["home_team"], "Fellows")
        self.assertEqual(initial["match"]["away_team"], "Mentors")
        self.assertEqual(initial["match"]["prizes"], [20000, 10000, 5000])

        # Invalid progressions must fail with 400
        for bad_prog in [
            ["Fellows"],
            ["Fellows", "Mentors"],
            ["Fellows", "Fellows", "Mentors"],
            ["Fellows", "Unknown"],
        ]:
            bad_code, _ = self._req(
                "POST",
                "/api/predictions",
                {"name": "Tester", "contact": "08010000000", "progression": bad_prog},
            )
            self.assertEqual(bad_code, 400)

        # Submit 6 predictions:
        # 4 exact ["Fellows", "Mentors", "Fellows"], 1 different 2-1 ["Mentors", "Fellows", "Fellows"], 1 2-0 ["Mentors", "Mentors"]
        entries = [
            ("Ada", "08011112222", ["Fellows", "Mentors", "Fellows"]),
            ("Bola", "bola@example.com", ["Mentors", "Fellows", "Fellows"]),
            ("Chidi", "08033334444", ["Fellows", "Mentors", "Fellows"]),
            ("Dapo", "dapo@example.com", ["Mentors", "Mentors"]),
            ("Efe", "08055556666", ["Fellows", "Mentors", "Fellows"]),
            ("Femi", "08066667777", ["Fellows", "Mentors", "Fellows"]),
        ]
        for idx, (name, contact, prog) in enumerate(entries, start=1):
            code, res = self._req(
                "POST",
                "/api/predictions",
                {"name": name, "contact": contact, "progression": prog},
            )
            self.assertEqual(code, 201)
            self.assertEqual(res["prediction"]["order"], idx)
            self.assertNotEqual(res["prediction"]["contact_masked"], contact)

        # Duplicate phone and duplicate email rejected with 409
        code_dup_phone, _ = self._req(
            "POST",
            "/api/predictions",
            {"name": "Ada Clone", "contact": "0801-111-2222", "progression": ["Fellows", "Fellows"]},
        )
        self.assertEqual(code_dup_phone, 409)
        code_dup_email, _ = self._req(
            "POST",
            "/api/predictions",
            {"name": "Bola Clone", "contact": "BOLA@example.com", "progression": ["Fellows", "Fellows"]},
        )
        self.assertEqual(code_dup_email, 409)

        # Public state hides raw contacts
        _, pub_state = self._req("GET", "/api/state")
        self.assertNotIn("contact", pub_state["predictions"][0])

        # Wrong PIN rejected; valid PIN returns token and unmasked contacts
        bad_code, _ = self._req("POST", "/api/admin/login", {"pin": "wrong"})
        self.assertEqual(bad_code, 401)
        ok_code, login_res = self._req("POST", "/api/admin/login", {"pin": "secret99"})
        self.assertEqual(ok_code, 200)
        token = login_res["token"]
        self.assertEqual(login_res["snapshot"]["predictions"][0]["contact"], "08011112222")

        # Locking blocks new entries
        lock_code, _ = self._req(
            "POST", "/api/admin/match", {"status": "locked"}, token=token
        )
        self.assertEqual(lock_code, 200)
        blocked_code, _ = self._req(
            "POST",
            "/api/predictions",
            {"name": "Late", "contact": "08099990000", "progression": ["Fellows", "Mentors", "Fellows"]},
        )
        self.assertEqual(blocked_code, 403)

        # Finishing match awards first 3 exact progression matches: Ada, Chidi, Efe
        # Bola had 2-1 too, but wrong round order (Mentors -> Fellows -> Fellows), so Bola must miss!
        fin_code, fin_res = self._req(
            "POST",
            "/api/admin/match",
            {"status": "finished", "final_progression": ["Fellows", "Mentors", "Fellows"]},
            token=token,
        )
        self.assertEqual(fin_code, 200)
        winners = fin_res["snapshot"]["winners"]
        self.assertEqual(len(winners), 3)
        self.assertEqual(
            [(w["name"], w["rank"], w["prize"]) for w in winners],
            [("Ada", 1, 20000), ("Chidi", 2, 10000), ("Efe", 3, 5000)],
        )
        bola = fin_res["snapshot"]["predictions"][1]
        self.assertEqual(bola["outcome"], "missed")
        femi = fin_res["snapshot"]["predictions"][5]
        self.assertEqual(femi["outcome"], "exact_late")
        self.assertEqual(femi["prize"], 0)

        # Reset clears predictions and reopens
        rst_code, rst_res = self._req("POST", "/api/admin/reset", {}, token=token)
        self.assertEqual(rst_code, 200)
        self.assertEqual(rst_res["snapshot"]["stats"]["total"], 0)
        self.assertEqual(rst_res["snapshot"]["match"]["status"], "open")


if __name__ == "__main__":
    unittest.main()
