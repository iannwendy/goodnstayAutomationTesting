#!/usr/bin/env python3
"""Unit tests for goodNstay API QA Testing Helper (api_test_helper.py)."""

from __future__ import annotations

import copy
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import pathlib
import sys
import tempfile
import threading
import unittest

SCRIPT_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import api_test_helper as helper  # noqa: E402


class TestApiTestHelper(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = helper.build_op1593_suite()

    def test_canonical_op1593_suite_passes_strict_validation(self) -> None:
        report = helper.validate_suite_dict(self.suite, pathlib.Path("op1593.json"))
        self.assertEqual(report.error_count, 0, [i.message for i in report.issues])
        self.assertEqual(report.warn_count, 0, [i.message for i in report.issues])
        self.assertEqual(len(self.suite["testCases"]), 10)

    def test_rejects_forbidden_example_url(self) -> None:
        bad = copy.deepcopy(self.suite)
        bad["testCases"][0]["methodAndUrl"] = "POST https://api.example.test/v2/partner-registrations"
        bad["testCases"][0]["resultRecord"]["url"] = "https://api.example.test/v2/partner-registrations"
        report = helper.validate_suite_dict(bad, pathlib.Path("bad.json"))
        codes = {i.code for i in report.issues}
        self.assertIn("FORBIDDEN_EXAMPLE_URL", codes)

    def test_rejects_production_goodnstay_url_and_allows_staging_url(self) -> None:
        bad_prod_web = copy.deepcopy(self.suite)
        bad_prod_web["preconditionsChecklist"]["baseUrl"] = "https://goodnstay.com"
        bad_prod_web["testCases"][0]["methodAndUrl"] = "POST https://goodnstay.com/api/traveler/login"
        bad_prod_web["testCases"][0]["resultRecord"]["url"] = "https://goodnstay.com/api/traveler/login"
        report_web = helper.validate_suite_dict(bad_prod_web, pathlib.Path("bad_prod_web.json"))
        self.assertIn("FORBIDDEN_PRODUCTION_URL", {i.code for i in report_web.issues})

        bad_prod_api = copy.deepcopy(self.suite)
        bad_prod_api["testCases"][0]["resultRecord"]["url"] = "https://services.goodnstay.com/api/traveler/login"
        report_api = helper.validate_suite_dict(bad_prod_api, pathlib.Path("bad_prod_api.json"))
        self.assertIn("FORBIDDEN_PRODUCTION_URL", {i.code for i in report_api.issues})

        good_stag = copy.deepcopy(self.suite)
        good_stag["preconditionsChecklist"]["baseUrl"] = "https://web.stag.goodnstay.com"
        good_stag["preconditionsChecklist"]["openApiDocument"] = "https://services.stag.goodnstay.com/openapi.json"
        good_stag["testCases"][0]["methodAndUrl"] = "POST https://web.stag.goodnstay.com/api/traveler/login"
        good_stag["testCases"][0]["resultRecord"]["url"] = "https://services.stag.goodnstay.com/api/traveler/login"
        report_stag = helper.validate_suite_dict(good_stag, pathlib.Path("good_stag.json"))
        self.assertNotIn("FORBIDDEN_PRODUCTION_URL", {i.code for i in report_stag.issues})

    def test_run_suite_live_blocks_production_goodnstay_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = helper.scaffold_suite_directory(pathlib.Path(tmp))
            for prod_url in ("https://goodnstay.com", "https://www.goodnstay.com", "https://services.goodnstay.com"):
                with self.assertRaisesRegex(ValueError, "Staging"):
                    helper.run_suite_live(suite_path=paths["suite_json"], base_url=prod_url)

    def test_non_regv2_traveler_suite_does_not_emit_v2_fixture_warnings(self) -> None:
        trav = copy.deepcopy(self.suite)
        trav["suiteName"] = "Staging Traveler Web API Suite"
        trav["jiraTicket"] = "OP-1626"
        trav["baseValidFixture"] = {
            "fullName": "QA Tester",
            "phone": "+84900000000",
            "country": "VN",
            "dob": "2000-01-15",
            "gender": "male",
        }
        for tc in trav["testCases"]:
            tc["payloadObject"] = dict(trav["baseValidFixture"])
            tc["headerOnlyMutation"] = True
        report = helper.validate_suite_dict(trav, pathlib.Path("traveler_stag.json"))
        self.assertEqual(report.error_count, 0, [i.message for i in report.issues])
        self.assertEqual(report.warn_count, 0, [i.message for i in report.issues])

    def test_multi_endpoint_base_fixtures_and_postman_get_without_body(self) -> None:
        suite = {
            "suiteName": "Multi-Endpoint Traveler Suite",
            "jiraTicket": "OP-1626",
            "environment": "STAGING",
            "preconditionsChecklist": {
                "requirementJira": "OP-1626",
                "openApiDocument": "[QA fills in — BLOCKED: Strapi OpenAPI not published on STAG]",
                "baseUrl": "https://services.stag.goodnstay.com",
                "methodAndEndpoint": "PUT /api/traveler/update-profile & GET /api/ticket-supports",
                "authAndTokens": "Bearer <REDACTED_QA_TOKEN>",
                "testDataFixtures": "Safe QA fixtures per endpoint",
                "deployedBuildSha": "web=turbopack-2h-u0he6dowwt, api=<CHECK_DEPLOYED_SHA>",
            },
            "baseValidFixture": {"fullName": "QA Tester", "dob": "2000-01-15"},
            "endpointBaseFixtures": {
                "update-profile": {"fullName": "QA Tester", "dob": "2000-01-15", "gender": "male"},
            },
            "testCases": [
                {
                    "testCaseId": "ME-001",
                    "title": "Reject malformed dob string on PUT /api/traveler/update-profile",
                    "testCategory": "Negative",
                    "baseFixtureKey": "update-profile",
                    "urlConfirmedSource": "Observed live in F12 Network & chunk 2k50va9an1vxz.js",
                    "requirement": "GNS-FORM-001",
                    "priorityAndLayer": "P1 / API",
                    "environment": "STAGING · web=turbopack-2h-u0he6dowwt, api=<CHECK_DEPLOYED_SHA>",
                    "preconditions": "Signed-in QA Traveler",
                    "methodAndUrl": "PUT https://services.stag.goodnstay.com/api/traveler/update-profile",
                    "headersAuthParams": "Authorization: Bearer <REDACTED_QA_TOKEN>",
                    "payloadAndTestData": "Single-Variable Delta: dob='not-a-valid-date'",
                    "singleChangeDelta": "Mutate ONLY dob from '2000-01-15' to 'not-a-valid-date'",
                    "steps": [
                        "1. Load valid-update-profile.json.",
                        "2. Mutate ONLY dob to 'not-a-valid-date' and send PUT.",
                        "3. Verify 4xx error and confirm via GET /api/traveler/me readback that dob is unchanged.",
                    ],
                    "expectedResponse": "HTTP <CHECK_OPENAPI> with <CHECK_ERROR_REGISTRY> (never HTTP 500).",
                    "expectedDataResult": "No profile record modified on GET /api/traveler/me readback.",
                    "actualResult": "HTTP 500 Server error.",
                    "statusAndEvidence": "FAIL — screenshots/bug_api03.png",
                    "payloadObject": {"fullName": "QA Tester", "dob": "not-a-valid-date", "gender": "male"},
                    "resultRecord": {
                        "testCaseId": "ME-001",
                        "environment": "STAGING",
                        "method": "PUT",
                        "url": "https://services.stag.goodnstay.com/api/traveler/update-profile",
                        "testDataFile": "invalid-dob.json",
                        "expectedHttpStatus": "<CHECK_OPENAPI>",
                        "expectedErrorCode": "<CHECK_ERROR_REGISTRY>",
                        "actualHttpStatus": "500",
                        "actualErrorCode": "500",
                        "requestId": "req-500",
                        "dataCheck": "GET /api/traveler/me unchanged",
                        "status": "FAIL",
                        "evidenceLink": "screenshots/bug_api03.png",
                    },
                },
                {
                    "testCaseId": "ME-002",
                    "title": "Verify unauthenticated GET /api/ticket-supports access control",
                    "testCategory": "Permission",
                    "urlConfirmedSource": "Observed in chunk 1yil-2d8cpf3l.js",
                    "headerOnlyMutation": True,
                    "requirement": "API Standard (524593)",
                    "priorityAndLayer": "P0 / API Permission",
                    "environment": "STAGING · web=turbopack-2h-u0he6dowwt, api=<CHECK_DEPLOYED_SHA>",
                    "preconditions": "Unauthenticated client",
                    "methodAndUrl": "GET https://services.stag.goodnstay.com/api/ticket-supports?page=1",
                    "headersAuthParams": "Accept: application/json (No Authorization header)",
                    "payloadAndTestData": "None (GET request without body)",
                    "singleChangeDelta": "Omit Authorization header on GET /api/ticket-supports",
                    "steps": [
                        "1. Prepare unauthenticated GET request.",
                        "2. Send GET https://services.stag.goodnstay.com/api/ticket-supports?page=1.",
                        "3. Check HTTP status and verify zero private tickets are exposed.",
                    ],
                    "expectedResponse": "HTTP <CHECK_OPENAPI> (<CHECK_ERROR_REGISTRY>).",
                    "expectedDataResult": "Zero support ticket records exposed to unauthenticated caller.",
                    "actualResult": "HTTP 200 OK returning ticket data[].",
                    "statusAndEvidence": "FAIL — screenshots/bug_api02.png",
                    "payloadObject": {},
                    "resultRecord": {
                        "testCaseId": "ME-002",
                        "environment": "STAGING",
                        "method": "GET",
                        "url": "https://services.stag.goodnstay.com/api/ticket-supports?page=1",
                        "testDataFile": "NO_BODY_GET",
                        "expectedHttpStatus": "<CHECK_OPENAPI>",
                        "expectedErrorCode": "<CHECK_ERROR_REGISTRY>",
                        "actualHttpStatus": "200",
                        "actualErrorCode": "NONE",
                        "requestId": "req-200",
                        "dataCheck": "Publicly returned submitted tickets",
                        "status": "FAIL",
                        "evidenceLink": "screenshots/bug_api02.png",
                    },
                },
            ],
        }
        report = helper.validate_suite_dict(suite, pathlib.Path("me.json"))
        self.assertEqual(report.error_count, 0, [(i.code, i.message) for i in report.issues])
        self.assertEqual(report.warn_count, 0, [(i.code, i.message) for i in report.issues])

        pm = helper.export_postman_collection(suite)
        put_req = pm["item"][0]["request"]
        get_req = pm["item"][1]["request"]
        self.assertIn("body", put_req)
        self.assertEqual(put_req["url"]["host"], ["services", "stag", "goodnstay", "com"])
        self.assertEqual(put_req["url"]["path"], ["api", "traveler", "update-profile"])
        self.assertNotIn("body", get_req)
        self.assertEqual(get_req["url"]["query"], [{"key": "page", "value": "1"}])

    def test_blocks_frontend_chunks_disguised_as_openapi_and_blocks_bcrypt_hash_leak(self) -> None:
        bad = copy.deepcopy(self.suite)
        bad["preconditionsChecklist"]["openApiDocument"] = "https://web.stag.goodnstay.com/_next/static/chunks/abc.js"
        bad["testCases"][1]["resultRecord"]["expectedHttpStatus"] = "400"
        bad["testCases"][1]["resultRecord"]["expectedErrorCode"] = "VALIDATION_ERROR"
        bad["testCases"][1]["actualResult"] = "Exposed hash $2a$10$LPwMmStBWJ8lupVsn1vL7.qEhpKZ65nWiJOr9E2/bfSvMjUtfRoQa"
        report = helper.validate_suite_dict(bad, pathlib.Path("bad_disguised.json"))
        codes = {i.code for i in report.issues}
        self.assertIn("GUESSED_HTTP_STATUS_WITHOUT_OPENAPI", codes)
        self.assertIn("GUESSED_ERROR_CODE_WITHOUT_OPENAPI", codes)
        self.assertIn("PII_OR_SECRET_LEAK", codes)

    def test_rejects_guessed_url_status_and_error_code_when_openapi_missing(self) -> None:
        bad = copy.deepcopy(self.suite)
        bad["testCases"][1]["resultRecord"]["url"] = "/api/v2/accommodations/register"
        bad["testCases"][1]["resultRecord"]["expectedHttpStatus"] = "400"
        bad["testCases"][1]["resultRecord"]["expectedErrorCode"] = "VALIDATION_ERROR"
        report = helper.validate_suite_dict(bad, pathlib.Path("bad.json"))
        codes = {i.code for i in report.issues}
        self.assertIn("GUESSED_URL_WITHOUT_OPENAPI", codes)
        self.assertIn("GUESSED_HTTP_STATUS_WITHOUT_OPENAPI", codes)
        self.assertIn("GUESSED_ERROR_CODE_WITHOUT_OPENAPI", codes)

    def test_rejects_non_standard_statuses_and_unexecuted_pass(self) -> None:
        bad = copy.deepcopy(self.suite)
        bad["testCases"][0]["resultRecord"]["status"] = "NOT RUN"
        bad["testCases"][1]["resultRecord"]["status"] = "PASS"
        report = helper.validate_suite_dict(bad, pathlib.Path("bad.json"))
        codes = {i.code for i in report.issues}
        self.assertIn("INVALID_STATUS", codes)
        self.assertIn("UNEXECUTED_MARKED_PASS_OR_FAIL", codes)
        self.assertIn("PASS_FAIL_WITHOUT_DEPLOYED_SHA", codes)

    def test_rejects_multiple_variables_mutated_in_negative_case(self) -> None:
        bad = copy.deepcopy(self.suite)
        # REGV2-API-002 removes phoneCountry; also mutate propertyName -> 2 diffs
        bad["testCases"][1]["payloadObject"]["propertyName"] = "Another Hotel Name"
        report = helper.validate_suite_dict(bad, pathlib.Path("bad.json"))
        codes = {i.code for i in report.issues}
        self.assertIn("MULTIPLE_VARIABLES_MUTATED", codes)

    def test_rejects_missing_phone_country_without_valid_e164_phone(self) -> None:
        bad = copy.deepcopy(self.suite)
        # Keep only 1 diff from baseValidFixture? No, if phone is also changed that's 2 diffs,
        # so allowMultiFieldMutation=True to isolate the E.164 check
        bad["testCases"][1]["allowMultiFieldMutation"] = True
        bad["testCases"][1]["payloadObject"]["primaryContact"]["phone"] = "0901234567"
        report = helper.validate_suite_dict(bad, pathlib.Path("bad.json"))
        codes = {i.code for i in report.issues}
        self.assertIn("MISSING_PHONE_COUNTRY_MUST_KEEP_E164", codes)

    def test_rejects_pii_and_hardcoded_jwt_leaks(self) -> None:
        bad = copy.deepcopy(self.suite)
        bad["testCases"][0]["payloadObject"]["primaryContact"]["email"] = "baominh.internship@gmail.com"
        bad["testCases"][0]["headersAuthParams"] = (
            "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        report = helper.validate_suite_dict(bad, pathlib.Path("bad.json"))
        codes = {i.code for i in report.issues}
        self.assertIn("SECRET_JWT_LEAK", codes)
        self.assertIn("PII_OR_SECRET_LEAK", codes)

    def test_rejects_missing_14_fields_and_missing_readback_check(self) -> None:
        bad = copy.deepcopy(self.suite)
        bad["testCases"][0]["priorityAndLayer"] = ""
        bad["testCases"][0]["expectedDataResult"] = "Done."
        bad["testCases"][1]["expectedDataResult"] = "Error returned."
        report = helper.validate_suite_dict(bad, pathlib.Path("bad.json"))
        codes = {i.code for i in report.issues}
        self.assertIn("MISSING_14_FIELD", codes)
        self.assertIn("MISSING_POSITIVE_READBACK_CHECK", codes)
        self.assertIn("MISSING_NEGATIVE_ZERO_PERSISTENCE_CHECK", codes)

    def test_scaffold_and_exporters_and_jira_bug_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = pathlib.Path(tmp)
            paths = helper.scaffold_suite_directory(tmp_dir, jira_ticket="OP-1593", prefix="REGV2-API")
            self.assertTrue(paths["suite_json"].is_file())
            self.assertTrue(paths["markdown"].is_file())
            self.assertTrue(paths["postman"].is_file())
            self.assertTrue((paths["fixtures_dir"] / "valid-registration-v2.json").is_file())
            self.assertTrue((paths["fixtures_dir"] / "missing-phone-country.json").is_file())

            # Validate scaffolded JSON via CLI
            rc = helper.main(["validate", str(paths["suite_json"]), "--strict"])
            self.assertEqual(rc, 0)

            # Check Postman Collection v2.1 structure
            pm_data = json.loads(paths["postman"].read_text(encoding="utf-8"))
            self.assertEqual(
                pm_data["info"]["schema"],
                "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            )
            self.assertEqual(len(pm_data["item"]), 10)

            # Check Jira Bug conversion compatibility
            bug_path = tmp_dir / "BUG-REGV2-002.json"
            rc_bug = helper.main([
                "to-jira-bug",
                str(paths["suite_json"]),
                "--case-id",
                "REGV2-API-002",
                "--output",
                str(bug_path),
            ])
            self.assertEqual(rc_bug, 0)
            bug_data = json.loads(bug_path.read_text(encoding="utf-8"))
            for req_key in (
                "title",
                "environment",
                "steps_to_reproduce",
                "actual_result",
                "expected_result",
                "evidence",
                "classification",
            ):
                self.assertIn(req_key, bug_data)

    def test_run_suite_live_end_to_end_automation(self) -> None:
        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_GET(self) -> None:  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-Request-Id", "req-readback-001")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "data": {"id": "pr-101"}}).encode("utf-8"))

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                pc = body.get("primaryContact", {})
                if "phoneCountry" not in pc:
                    # Simulate OP-1591 regression: Gateway returns generic DOWNSTREAM_CLIENT_ERROR -> should trigger FAIL + bug file!
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("X-Request-Id", "req-fail-002")
                    self.end_headers()
                    self.wfile.write(
                        json.dumps({"success": False, "error": {"code": "DOWNSTREAM_CLIENT_ERROR"}}).encode("utf-8")
                    )
                    return
                if body.get("administrativeAreaCode") == "KR-11":
                    self.send_response(422)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("X-Request-Id", "req-pass-003")
                    self.end_headers()
                    self.wfile.write(
                        json.dumps({"success": False, "error": {"code": "LOCATION_CHILD_MISMATCH"}}).encode("utf-8")
                    )
                    return
                self.send_response(201)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-Request-Id", "req-pass-001")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"success": True, "data": {"partnerRequestId": "pr-101"}}).encode("utf-8")
                )

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_dir = pathlib.Path(tmp)
                paths = helper.scaffold_suite_directory(tmp_dir)
                rc = helper.main([
                    "run-suite",
                    str(paths["suite_json"]),
                    "--base-url",
                    f"http://127.0.0.1:{port}",
                    "--registration-path",
                    "/api/v2/partner/registrations",
                    "--admin-readback-path",
                    "/api/v1/admin/partner-requests",
                    "--deployed-sha",
                    "fe=abc1234,gw=def5678,partner=9012345",
                    "--openapi-url",
                    f"http://127.0.0.1:{port}/openapi.json",
                ])
                self.assertEqual(rc, 0)
                updated = json.loads(paths["suite_json"].read_text(encoding="utf-8"))
                by_id = {tc["testCaseId"]: tc["resultRecord"] for tc in updated["testCases"]}
                self.assertEqual(by_id["REGV2-API-001"]["status"], "PASS")
                self.assertEqual(by_id["REGV2-API-002"]["status"], "FAIL")
                self.assertEqual(by_id["REGV2-API-003"]["status"], "PASS")
                self.assertTrue((tmp_dir / "bugs" / "BUG-REGV2-API-002.json").is_file())
        finally:
            server.shutdown()
            server.server_close()

    def test_validates_optional_owasp_mapping_field(self) -> None:
        good = copy.deepcopy(self.suite)
        good["testCases"][7]["owaspMapping"] = (
            "OWASP A01:2025 Broken Access Control (CWE-283) · OWASP API1:2023 BOLA"
        )
        good["testCases"][7]["owaspRemediationUrl"] = (
            "https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html"
        )
        report_ok = helper.validate_suite_dict(good, pathlib.Path("good_owasp.json"))
        self.assertEqual(report_ok.error_count, 0, [i.message for i in report_ok.issues])

        bad = copy.deepcopy(self.suite)
        bad["testCases"][7]["owaspMapping"] = "OWASP A99:2017 Unknown Category"
        report_bad = helper.validate_suite_dict(bad, pathlib.Path("bad_owasp.json"))
        self.assertIn("INVALID_OWASP_MAPPING", {i.code for i in report_bad.issues})

    def test_postman_and_markdown_export_include_owasp_2025_passive_assertions(self) -> None:
        enriched = copy.deepcopy(self.suite)
        enriched["testCases"][7]["owaspMapping"] = (
            "OWASP A01:2025 Broken Access Control (CWE-283) · OWASP API1:2023 BOLA"
        )
        pm_col = helper.export_postman_collection(enriched)
        script_text = "\n".join(pm_col["item"][0]["event"][0]["script"]["exec"])
        self.assertIn("OWASP A04:2025", script_text)
        self.assertIn("resetpasswordtoken", script_text)
        self.assertIn("OWASP A10:2025", script_text)
        self.assertIn("OWASP Mapping:", pm_col["item"][7]["request"]["description"])

        md_text = helper.export_markdown(enriched)
        self.assertIn("OWASP A01:2025 Broken Access Control (CWE-283)", md_text)

    def test_run_suite_live_fails_on_owasp_a04_secret_column_leak_and_a10_500_error(self) -> None:
        class _LeakyHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_GET(self) -> None:  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "data": {"id": "pr-202"}}).encode("utf-8"))

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                pc = body.get("primaryContact", {})
                if "phoneCountry" not in pc:
                    # Simulate OP-1949: unhandled HTTP 500 on malformed/missing input -> OWASP A10:2025
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("X-Request-Id", "req-500-a10")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": {"code": 500, "message": "Server error."}}).encode("utf-8"))
                    return
                # Simulate OP-1947: 201 Created but response leaks resetPasswordToken column -> OWASP A04:2025 FAIL!
                self.send_response(201)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-Request-Id", "req-leak-a04")
                self.end_headers()
                self.wfile.write(
                    json.dumps({
                        "success": True,
                        "data": {
                            "partnerRequestId": "pr-202",
                            "user": {"id": 9, "resetPasswordToken": "redacted-sample-token"},
                        },
                    }).encode("utf-8")
                )

        server = HTTPServer(("127.0.0.1", 0), _LeakyHandler)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_dir = pathlib.Path(tmp)
                paths = helper.scaffold_suite_directory(tmp_dir)
                suite_json = json.loads(paths["suite_json"].read_text(encoding="utf-8"))
                suite_json["testCases"][1]["owaspMapping"] = "OWASP A10:2025 Mishandling of Exceptional Conditions (CWE-755)"
                suite_json["testCases"][1]["owaspRemediationUrl"] = (
                    "https://cheatsheetseries.owasp.org/cheatsheets/Error_Handling_Cheat_Sheet.html"
                )
                paths["suite_json"].write_text(json.dumps(suite_json, indent=2), encoding="utf-8")

                rc = helper.main([
                    "run-suite",
                    str(paths["suite_json"]),
                    "--base-url",
                    f"http://127.0.0.1:{port}",
                    "--registration-path",
                    "/api/v2/partner/registrations",
                    "--admin-readback-path",
                    "/api/v1/admin/partner-requests",
                    "--deployed-sha",
                    "fe=abc1234,gw=def5678,partner=9012345",
                    "--openapi-url",
                    f"http://127.0.0.1:{port}/openapi.json",
                ])
                self.assertEqual(rc, 0)
                updated = json.loads(paths["suite_json"].read_text(encoding="utf-8"))
                by_id = {tc["testCaseId"]: tc for tc in updated["testCases"]}
                # REGV2-API-001 returned 201 + readback 200, yet MUST FAIL due to leaked resetPasswordToken (A04:2025)
                self.assertEqual(by_id["REGV2-API-001"]["resultRecord"]["status"], "FAIL")
                self.assertIn("OWASP A04:2025", by_id["REGV2-API-001"]["actualResult"])

                bug_001 = json.loads((tmp_dir / "bugs" / "BUG-REGV2-API-001.json").read_text(encoding="utf-8"))
                self.assertIn("OWASP A04:2025", bug_001["evidence"]["notes"])

                bug_002 = json.loads((tmp_dir / "bugs" / "BUG-REGV2-API-002.json").read_text(encoding="utf-8"))
                self.assertIn("OWASP A10:2025", bug_002["evidence"]["notes"])
                self.assertIn("Error_Handling_Cheat_Sheet.html", bug_002["evidence"]["notes"])
        finally:
            server.shutdown()
            server.server_close()

    def test_bodyless_post_action_without_fake_postman_body(self) -> None:
        suite = copy.deepcopy(self.suite)
        tc = copy.deepcopy(suite["testCases"][5])
        tc["testCaseId"] = "STAG-ACT-001"
        tc["testCategory"] = "Permission"
        tc["bodylessAction"] = True
        tc["urlConfirmedSource"] = "Observed in chunk 0lu641k7h1gc_.js"
        tc["methodAndUrl"] = "POST https://services.stag.goodnstay.com/api/v1/notifications/mark-all-read"
        tc["payloadObject"] = {}
        tc["resultRecord"]["testCaseId"] = "STAG-ACT-001"
        tc["resultRecord"]["method"] = "POST"
        tc["resultRecord"]["url"] = "https://services.stag.goodnstay.com/api/v1/notifications/mark-all-read"
        tc["resultRecord"]["testDataFile"] = "NO_BODY_POST_ACTION"
        tc["resultRecord"]["expectedErrorCode"] = "<CHECK_ERROR_REGISTRY>"
        tc["expectedDataResult"] = "Zero notification records modified after logout."
        suite["testCases"].append(tc)

        report = helper.validate_suite_dict(suite, pathlib.Path("bodyless_post.json"))
        self.assertEqual(report.error_count, 0, report.issues)
        pm = helper.export_postman_collection(suite)
        post_act = next(i for i in pm["item"] if i["name"].startswith("STAG-ACT-001"))
        self.assertNotIn("body", post_act["request"])

    def test_export_single_case_postman_collection_preserves_origin_and_auth_var(self) -> None:
        suite = copy.deepcopy(self.suite)
        tc = copy.deepcopy(suite["testCases"][1])
        tc["testCaseId"] = "STAG-CORS-001"
        tc["headersAuthParams"] = (
            "Accept: application/json; Origin: https://untrusted-origin.example.test; "
            "Authorization: Bearer <REDACTED_QA_TOKEN>"
        )
        tc["resultRecord"]["testCaseId"] = "STAG-CORS-001"
        suite["testCases"].append(tc)

        single_pm = helper.export_single_case_postman_collection(suite, "STAG-CORS-001")
        self.assertEqual(len(single_pm["item"]), 1)
        hdrs = {h["key"]: h["value"] for h in single_pm["item"][0]["request"]["header"]}
        self.assertEqual(hdrs.get("Origin"), "https://untrusted-origin.example.test")
        self.assertEqual(hdrs.get("Authorization"), "Bearer {{qaToken}}")
        var_keys = {v["key"] for v in single_pm["variable"]}
        self.assertIn("qaToken", var_keys)

    def test_markdown_and_postman_never_bleed_op1593_or_unrequested_headers_or_blocked_4xx(self) -> None:
        suite = {
            "suiteName": "Staging Traveler Suite",
            "jiraTicket": "OP-1626",
            "relatedJiraTickets": ["OP-1959"],
            "environment": "STAGING",
            "preconditionsChecklist": self.suite["preconditionsChecklist"],
            "baseValidFixtureFile": "fixtures/valid-request-bids.json",
            "baseValidFixture": {"data": {"roomCount": 1}},
            "testCases": [
                {
                    "testCaseId": "STAG-CHK-001",
                    "title": "Verify pagination contract when OpenAPI is missing",
                    "testCategory": "Boundary",
                    "headerOnlyMutation": True,
                    "ownerToAsk": "Strapi Backend Owner",
                    "urlConfirmedSource": "Observed in chunk 2k50va9an1vxz.js",
                    "requirement": "<CHECK_OPENAPI> — pagination rule",
                    "priorityAndLayer": "P2 / API Boundary",
                    "environment": "STAGING · Date: 2026-11-19",
                    "preconditions": "Authenticated session.",
                    "methodAndUrl": "POST https://services.stag.goodnstay.com/api/translations/room-description",
                    "headersAuthParams": "Content-Type: application/json; Origin: https://web.stag.goodnstay.com (Omit Authorization header)",
                    "payloadAndTestData": "Fixture: fixtures/valid-request-bids.json",
                    "singleChangeDelta": "Omit ONLY Authorization header",
                    "steps": [
                        "1. Load fixture.",
                        "2. Send POST without Authorization.",
                        "3. Confirm zero DB mutation.",
                    ],
                    "expectedResponse": "<CHECK_OPENAPI> / <CHECK_ERROR_REGISTRY>",
                    "expectedDataResult": "No database record created.",
                    "actualResult": "Observed HTTP 200 OK.",
                    "statusAndEvidence": "BLOCKED — API contract missing.",
                    "payloadObject": {"data": {"roomCount": 1}},
                    "resultRecord": {
                        "testCaseId": "STAG-CHK-001",
                        "environment": "STAGING",
                        "method": "POST",
                        "url": "https://services.stag.goodnstay.com/api/translations/room-description",
                        "testDataFile": "valid-request-bids.json",
                        "expectedHttpStatus": "<CHECK_OPENAPI>",
                        "expectedErrorCode": "<CHECK_ERROR_REGISTRY>",
                        "actualHttpStatus": "200",
                        "actualErrorCode": "NONE",
                        "requestId": "req-chk-001",
                        "dataCheck": "No DB mutation",
                        "status": "BLOCKED",
                        "evidenceLink": "<ADD_AFTER_TEST>",
                    },
                }
            ],
        }
        md = helper.export_markdown(suite)
        self.assertIn("fixtures/valid-request-bids.json", md)
        self.assertNotIn("valid-registration-v2.json", md)
        self.assertIn("`OP-1626`", md)

        pm = helper.export_postman_collection(suite)
        req = pm["item"][0]["request"]
        hdr_keys = {h["key"] for h in req["header"]}
        self.assertNotIn("Idempotency-Key", hdr_keys)
        exec_js = "\n".join(pm["item"][0]["event"][0]["script"]["exec"])
        self.assertNotIn("within(400, 499)", exec_js)


if __name__ == "__main__":
    unittest.main()
