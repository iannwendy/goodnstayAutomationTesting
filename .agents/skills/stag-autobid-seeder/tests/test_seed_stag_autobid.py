import datetime
import http.server
import json
import os
import pathlib
import sys
import threading
import unittest
from urllib.parse import parse_qs, urlparse

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import seed_stag_autobid as ssa  # noqa: E402


class FakeStagHandler(http.server.BaseHTTPRequestHandler):
    state = None

    def log_message(self, format, *args):
        return

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return None
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, status: int, payload: dict):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _require_bearer(self) -> bool:
        expected = f"Bearer {self.state['expected_jwt']}"
        if self.headers.get("Authorization") != expected:
            self._send_json(401, {"success": False, "errorCode": "UNAUTHORIZED"})
            return False
        return True

    def do_POST(self):
        parsed = urlparse(self.path)
        body = self._read_json()
        self.state["requests"].append(("POST", parsed.path, body))

        if parsed.path == "/api/traveler/login":
            if (
                isinstance(body, dict)
                and body.get("username") == self.state["expected_email"]
                and body.get("password") == self.state["expected_password"]
            ):
                self._send_json(
                    200,
                    {
                        "success": True,
                        "message": "OK",
                        "data": {
                            "jwt": self.state["expected_jwt"],
                            "refreshToken": "fake-refresh-token",
                            "user": {
                                "id": 77,
                                "email": self.state["expected_email"],
                                "phone": "900000000",
                                "gender": "male",
                                "dob": "2005-01-01",
                                "fullName": "QA Traveler",
                                "country": "VN",
                                "isTestAccount": True,
                            },
                        },
                    },
                )
            else:
                self._send_json(401, {"success": False, "message": "Invalid credentials"})
            return

        if parsed.path == "/api/traveler/request-bids":
            if not self._require_bearer():
                return
            data = (body or {}).get("data") or {}
            if data.get("stayingCountry") == "KR" and data.get("stayingCity") != "KR-11":
                self._send_json(
                    400,
                    {
                        "success": False,
                        "errorCode": "INVALID_CITY_CODE",
                        "message": "City does not match state",
                    },
                )
                return
            rid = self.state["next_request_id"]
            self.state["next_request_id"] += 1
            self.state["created_requests"].append((rid, data))
            self._send_json(
                200,
                {
                    "success": True,
                    "data": {
                        "requestId": rid,
                        "code": f"CRQ-V-TEST{rid}",
                        "hotelIds": [],
                    },
                },
            )
            return

        self._send_json(404, {"success": False, "message": "Not found"})

    def do_GET(self):
        parsed = urlparse(self.path)
        self.state["requests"].append(("GET", parsed.path, parse_qs(parsed.query)))
        if parsed.path == "/api/traveler/request-bids":
            if not self._require_bearer():
                return
            self.state["poll_count"] += 1
            deals = list(self.state["existing_open_deals"])
            for rid, data in self.state["created_requests"]:
                # Simulate async BullMQ worker populating bid on 2nd poll
                bids = []
                if self.state["poll_count"] >= self.state["emit_bid_on_poll"]:
                    bids = [
                        {
                            "id": 9000 + rid,
                            "hotelName": "Stay Hotel H11",
                            "bidStatus": "waiting",
                            "totalPrice": 169.4,
                            "currency": "KRW",
                            "expiredAt": "2099-01-01T00:00:00.000Z",
                        }
                    ]
                deals.append(
                    {
                        "id": rid,
                        "code": f"CRQ-V-TEST{rid}",
                        "checkInDate": data.get("checkInDate"),
                        "checkOutDate": data.get("checkOutDate"),
                        "isNoMatchedHotel": False,
                        "hotelBids": bids,
                    }
                )
            self._send_json(200, {"success": True, "data": deals})
            return

        self._send_json(404, {"success": False, "message": "Not found"})

    def do_PUT(self):
        parsed = urlparse(self.path)
        body = self._read_json()
        self.state["requests"].append(("PUT", parsed.path, body))
        if parsed.path.startswith("/api/customer-requests/"):
            if not self._require_bearer():
                return
            rid = int(parsed.path.rsplit("/", 1)[-1])
            self.state["cancelled_ids"].append(rid)
            self._send_json(200, {"success": True, "data": {"id": rid, "status": "cancelled"}})
            return

        self._send_json(404, {"success": False, "message": "Not found"})


class SeedStagAutobidTests(unittest.TestCase):
    def setUp(self):
        self.state = {
            "expected_email": "qa-tester@example.test",
            "expected_password": "TestPassword123!",
            "expected_jwt": "eyJ.fake.secret.jwt.token",
            "requests": [],
            "created_requests": [],
            "existing_open_deals": [],
            "cancelled_ids": [],
            "next_request_id": 2001,
            "poll_count": 0,
            "emit_bid_on_poll": 2,
        }
        FakeStagHandler.state = self.state
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeStagHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _make_config(self) -> ssa.StagConfig:
        return ssa.StagConfig(
            api_base_url=self.base_url,
            web_origin="https://web.stag.goodnstay.com",
            email=self.state["expected_email"],
            password=self.state["expected_password"],
            locale="en-US",
        )

    def test_build_payload_enforces_kr11_mirror_and_suite_room_filter(self):
        today = datetime.date(2026, 11, 13)
        payload = ssa.build_autobid_request_payload(
            user={
                "fullName": "QA Traveler",
                "email": "qa-tester@example.test",
                "phone": "900000000",
                "dob": "2005-01-01",
                "gender": "male",
                "country": "VN",
            },
            check_in="2026-11-18",
            check_out="2026-11-20",
            guests=2,
            rooms=1,
            today=today,
        )
        data = payload["data"]
        self.assertEqual(data["stayingCountry"], "KR")
        self.assertEqual(data["stayingProvince"], "KR-11")
        self.assertEqual(data["stayingCity"], "KR-11")
        self.assertEqual(data["stayingDistrict"], "")
        self.assertEqual(data["stayingWard"], "")
        self.assertEqual(data["accommodationType"], "hotel")
        self.assertEqual(data["roomTypes"], ["suite", "anyRoom"])
        self.assertEqual(data["guestCount"], 2)
        self.assertEqual(data["roomCount"], 1)
        self.assertEqual(data["guestComposition"]["adults"], 2)

    def test_build_payload_rejects_autobid_guardrail_violations(self):
        today = datetime.date(2026, 11, 13)
        with self.assertRaises(ssa.ValidationError):
            ssa.build_autobid_request_payload(
                user={}, check_in="2026-11-18", check_out="2026-11-20", guests=9, rooms=1, today=today
            )
        with self.assertRaises(ssa.ValidationError):
            ssa.build_autobid_request_payload(
                user={}, check_in="2026-11-18", check_out="2026-11-20", guests=2, rooms=5, today=today
            )
        with self.assertRaises(ssa.ValidationError):
            ssa.build_autobid_request_payload(
                user={}, check_in="2026-11-20", check_out="2026-11-18", guests=2, rooms=1, today=today
            )
        with self.assertRaises(ssa.ValidationError):
            ssa.build_autobid_request_payload(
                user={}, check_in="2026-11-12", check_out="2026-11-15", guests=2, rooms=1, today=today
            )

    def test_login_and_seed_polls_until_waiting_bid_and_never_leaks_jwt(self):
        client = ssa.StagTravelerClient(self._make_config())
        session = client.login()
        self.assertNotIn(self.state["expected_jwt"], repr(session))
        self.assertNotIn(self.state["expected_password"], repr(self._make_config()))

        result = ssa.seed_or_reuse_autobid(
            client,
            session,
            check_in="2099-01-10",
            check_out="2099-01-12",
            guests=2,
            rooms=1,
            reuse_existing=False,
            poll_interval=0.05,
            poll_timeout=2.0,
        )
        self.assertEqual(result["action"], "created")
        self.assertEqual(result["requestId"], 2001)
        self.assertEqual(len(result["waitingBids"]), 1)
        self.assertEqual(result["waitingBids"][0]["hotelName"], "Stay Hotel H11")
        self.assertGreaterEqual(self.state["poll_count"], 2)
        serialized = json.dumps(result)
        self.assertNotIn(self.state["expected_jwt"], serialized)

    def test_reuse_existing_returns_active_waiting_bid_without_creating_duplicate(self):
        self.state["existing_open_deals"] = [
            {
                "id": 1487,
                "code": "CRQ-V-BDZHPV",
                "checkInDate": "2026-11-18",
                "checkOutDate": "2026-11-20",
                "isNoMatchedHotel": False,
                "hotelBids": [
                    {
                        "id": 5438,
                        "hotelName": "Stay Hotel H11",
                        "bidStatus": "waiting",
                        "totalPrice": 169.4,
                        "currency": "KRW",
                        "expiredAt": "2099-12-31T23:59:59.000Z",
                    }
                ],
            }
        ]
        client = ssa.StagTravelerClient(self._make_config())
        session = client.login()
        result = ssa.seed_or_reuse_autobid(
            client,
            session,
            check_in="2099-01-10",
            check_out="2099-01-12",
            guests=2,
            rooms=1,
            reuse_existing=True,
            poll_interval=0.05,
            poll_timeout=1.0,
        )
        self.assertEqual(result["action"], "reused")
        self.assertEqual(result["requestId"], 1487)
        self.assertEqual(len(self.state["created_requests"]), 0)

    def test_cancel_unmatched_preserves_deals_with_waiting_bids(self):
        self.state["existing_open_deals"] = [
            {
                "id": 1480,
                "code": "CRQ-V-EMPTY1",
                "isNoMatchedHotel": True,
                "hotelBids": [],
            },
            {
                "id": 1487,
                "code": "CRQ-V-ACTIVE",
                "isNoMatchedHotel": False,
                "hotelBids": [
                    {
                        "id": 5438,
                        "hotelName": "Stay Hotel H11",
                        "bidStatus": "waiting",
                        "expiredAt": "2099-12-31T23:59:59.000Z",
                    }
                ],
            },
        ]
        client = ssa.StagTravelerClient(self._make_config())
        session = client.login()
        cancelled = ssa.cancel_unmatched_open_requests(client, session)
        self.assertEqual(cancelled, [1480])
        self.assertEqual(self.state["cancelled_ids"], [1480])

    def test_http_error_closes_response_cleanly_under_python_warnings_as_errors(self):
        bad_cfg = ssa.StagConfig(
            api_base_url=self.base_url,
            web_origin="https://web.stag.goodnstay.com",
            email="wrong@example.test",
            password="wrong",
        )
        client = ssa.StagTravelerClient(bad_cfg)
        with self.assertRaises(ssa.StagApiError) as ctx:
            client.login()
        self.assertIn("401", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
