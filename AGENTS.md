# goodNstay QA Automation Testing — Rules, Memory, Skills & Auto Jira + Sheet Standards

> **Mục đích:** File luật gốc (`AGENTS.md`) điều phối AI Agent chạy kiểm thử tự động (Web UI/Responsive, Staging API, OWASP Security, Payment Auto-Bid, Dashboard Regression), đồng thời **tự động xuất báo cáo chuẩn 7-field / 14-field, đẩy lên Jira Board `#135` (Project `OP`) và đồng bộ 20 cột vào Google Drive Excel (`gns_Bug_Report_Tracking.xlsx` — sheet `BUG_TRACKER` & `API_BUGS`)**.

---

## 1. Test Account Credentials & Auto-Authentication (Local `.env.stag`)
- **URL**: `https://goodnstay.com/en-US` (also `/vi-VN`, `/ko-KR`, `/vi-VN/home`, `/en-US/home`, `/ko-KR/home`; **Staging**: `https://web.stag.goodnstay.com/en-US/home` + API `https://services.stag.goodnstay.com`)
- **Credentials Source (Secret-Safe)**: Read `GNS_STAG_EMAIL` and `GNS_STAG_PASSWORD` from local gitignored `.env.stag` (`cp .env.stag.example .env.stag && chmod 600 .env.stag`) — **never hardcode or commit real passwords** into Git.
- **Account Display Alias (Sanitized)**: `TEST_QA_TRAVELER`

### Auto-Authentication Instructions
When asked to test or inspect `web.stag.goodnstay.com` via Chrome DevTools / Playwright browser tools:
1. Navigate to the target URL (`https://web.stag.goodnstay.com/en-US/home` for Staging, or the requested locale).
2. If not already signed in, automatically authenticate using `GNS_STAG_EMAIL` and `GNS_STAG_PASSWORD` from local `.env.stag` and click **LOGIN & FIND YOUR STAY** without printing the password to logs or reports.
3. On public surfaces (such as Global Home), verify **both** **Guest Session** (`data-gns-home-session="guest"`) and **Signed-In Session** (`data-gns-home-session="signed-in"`) whenever auth state alters navigation, drawers, notifications, or CTAs.

---

## 2. QA Bug Discovery & Evidence Standards
- **Confluence Spec Authority (via `atlassian` MCP -> `https://mcp.atlassian.com/v2/mcp`)**:
  - `166952975` — Accommodation Route Contract
  - `165937257` — Payment & Localization Contract (currency / FX / locale rules)
  - `171376745` — Design & Responsive Standards
  - `524593` — API Standard
  - `144015744` — OpenAPI Governance, Error Contract & Docs Portal
  - `184944019` — QA Guide: How to Write API Test Cases (VI v3.0 / EN v1.0)
  - Cross-check Confluence contracts and owning Jira handoff tickets (e.g., `OP-1626`, `OP-1593`) before setting `classification` (`Confirmed Bug` vs `Needs Verification — (need to brainstorming with team or observe)`).
- **Anti-Duplicate Pre-Check**: Always cross-check candidate bugs against `templates/existing_bugs_exclude.md` and live Jira Board `#135` (`GET /rest/agile/1.0/board/135/issue`) before filing.
- **Multi-Viewport Matrix**: Inspect Desktop (`1440x900`), Laptop (`1280x800`), Tablet (`768x1024`), and Mobile (`390x844` iPhone 14/15, `375x667` iPhone SE, `360x800`). Always measure real `getBoundingClientRect()` coordinates and computed CSS rules to prove overflow, clipping, or specificity bugs.
- **Mandatory 7-Field QA Report ("One Issue – One Report")**:
  1. `title` (`<= 255` chars): `[Area - Component] <Actual Problem> + <Context>`
  2. `environment`: `<Env> · <Device/Viewport> · <Browser> · <Locale>`
  3. `steps_to_reproduce`: Numbered atomic steps
  4. `actual_result`: Objective observed metrics only (px offsets, HTTP status, DOM state) — no speculation
  5. `expected_result`: Grounded in Confluence specs or same-page component parity
  6. `evidence`: Must contain `url`, `datetime` (`ICT`), `console` (F12 Console), `network` (F12 Network), `notes` (JS bundle / CSS root cause), and real `.png` screenshots
  7. `classification` + `severity` (`S0`–`S4`) + `priority_label` (`P0`–`P3`) + `reproducibility`

---

## 3. Jira Bug Reporting Automation (`Internship Program 2026`)
- **Tooling**: Always activate `.agents/skills/jira-bug-reporter/SKILL.md` and run `.agents/skills/jira-bug-reporter/scripts/jira_bug_reporter.py` (reads local credentials from `.env.jira`). For multi-bug batches, use `scripts/upload_jira_batch.py`.
- **Safety Gate**: Always run preview (`dry-run`, without `--confirm`) and show the user before posting live tickets to the shared **Internship Program 2026** board unless explicitly told to publish immediately — **Pre-Authorized Exception for Staging API Testing**: When executing API tests on Staging (`https://web.stag.goodnstay.com/`), confirmed API defects are pre-authorized to be **auto-published to Jira Board `#135` (`--confirm`) AND immediately synced into worksheet `API_BUGS`** of Google Drive tracker `gns_Bug_Report_Tracking.xlsx` (`1u11CxA99JxABEny9Gtgvi8Ylk0zOj8mo`, `gid=985739379`).
- **Board vs. Project Mapping (Critical)**:
  - **"Internship Program 2026"** is **Scrum Board `#135`** (`https://optibide-org.atlassian.net/jira/software/c/projects/OP/boards/135/backlog`) inside Jira Project **`Optibide` (`key: "OP"`, `id: "10001"`)**, Issue Type `Bug` (`id: "10009"`).
  - **Board Filter Rule (`Filter 10233`)**: Tickets **will NOT appear** on Board `#135` unless `assignee` is set to `Nguyen Bao Minh` (`712020:ca1958e5-9851-4d9d-93d9-e8eae49e4c3d` — or your own board-filter assignee account). Keep `JIRA_AUTO_ASSIGN_SELF=true`.
- **`OP` Structured Custom Tabs (Never Leave Blank)**:
  - Populating `description` alone leaves `OP`'s **Key details** tabs (`Reporting`, `Expectation`, `RCA`) empty on Jira Web & Mobile. Always rely on `jira_bug_reporter.py` (`build_structured_custom_fields`) so all 12 structured fields (`Environment`, `Pre-condition`, `Step-by-step`, `Actual Result`, `Expected Result`, `UI References`, `Signals and Clues`, `Detailed Analysis`, `Priority`, `Impact`, `Platform`, `Original Source Location`) are populated with inline `mediaSingle` screenshots, while `labels` (absent from `OP`'s Create Screen) is skipped automatically.
- **Batch Upload & Anti-Duplicate Protocol**:
  1. Save validated per-bug payloads in `<report_dir>/json_payloads/BUG-XX.json`.
  2. Query `GET /rest/agile/1.0/board/135/issue` by `summary` before creating tickets and flush each created `issue_key` immediately to `<report_dir>/uploaded_jira_tickets.json` so retries never create duplicates.
  3. To repair or backfill fields/screenshots on an existing ticket, run `--update OP-XXXX --confirm` instead of creating a new ticket.
  4. **Verify Before Claiming Success**: Query Board `#135` after upload to verify `on_board == True`, attachment counts match, inline media count matches, and zero custom fields are missing.
- **Google Drive Sheet Sync (`gns_Bug_Report_Tracking.xlsx`, `file_id=1u11CxA99JxABEny9Gtgvi8Ylk0zOj8mo`)**:
  - For **UI / E2E / Functional / Responsive** bugs -> sync into worksheet **`BUG_TRACKER`** via `scripts/sync_bug_tracker_sheet.py`.
  - For **Staging API / OWASP Security** bugs -> sync into worksheet **`API_BUGS`** (`gid=985739379`) via `.agents/skills/api-qa-testing/scripts/sync_api_bugs_sheet.py`.
  - Always download the latest `.xlsx` right before editing via `google-workspace` MCP `get_drive_file_download_url`, keep output inside `~/.workspace-mcp/attachments/` (to satisfy `ALLOWED_FILE_DIRS`), verify via `scripts/verify_xlsx_excel.sh` (ZIP CRC + XML + macOS Microsoft Excel `osascript`), and upload back in-place via `update_drive_file`.

---

## 4. Technical, Security & Self-Improvement Guardrails
- **Secret Hygiene**: Never print, echo, or commit `JIRA_API_TOKEN` (`.env.jira`, `chmod 600`) or `Authorization` headers (`~/.gemini/config/mcp_config.json`, `chmod 600`).
- **Python & Network Resilience**:
  - `optibide-org.atlassian.net` occasionally resets TLS handshakes (`[Errno 54] Connection reset by peer`) — always use bounded retries with backoff.
  - On Python 3.14+, always close `urllib.error.HTTPError` objects (`finally: exc.close()`) and verify changes with `python3 -W error -m unittest discover -s .agents/skills/jira-bug-reporter/tests`.
  - For Streamable HTTP SSE endpoints (`https://mcp.atlassian.com/v2/mcp`), read responses with `readline()`, never `.read()`.
- **Excel OpenXML (`.xlsx`) Editing Integrity (Never Use `xml.etree.ElementTree`)**:
  - Never serialize `.xlsx` worksheets or `.rels` files with Python's stdlib `xml.etree.ElementTree` — it drops unused `xmlns:x14ac` / `xmlns:xr2` / `xmlns:xr3` declarations referenced by `mc:Ignorable="x14ac xr xr2 xr3"` and adds `ns0:` prefixes to `.rels` (`<ns0:Relationships>`), causing Microsoft Excel to reject the workbook on open.
  - Always use `lxml.etree` (`standalone=True`, preserving every `nsmap` prefix in `mc:Ignorable` and default unprefixed `xmlns` on `.rels`), recompute exact `sst/@count` and `sst/@uniqueCount`, and verify the saved `.xlsx` opens cleanly in macOS `Microsoft Excel` via `osascript` before reporting completion.
- **Continuous Self-Improvement Loop**:
  - Whenever user feedback exposes a gap (e.g., an unpopulated Jira tab, an environment mismatch, or a workflow friction point), fix the automation + unit tests first, then distil the root lesson into `AGENTS.md` (workspace-wide) or `.agents/skills/<name>/SKILL.md` (tool-specific) so the agent permanently upgrades its behavior across future sessions.

---

## 5. Partner Auction Dashboard v2 (`dashboard/dashboard`) — Mandatory Post-Change Testing & Test-Case Policy
Whenever creating a new feature, modifying existing logic/UI/master-data, or fixing bugs inside `dashboard/dashboard`, ALWAYS activate `.agents/skills/dashboard-qa-testing/SKILL.md` and follow `guides/dashboard_AGENTS.md`:
1. **Every Change Must Include New / Updated Automated Tests**:
   - Pricing / formatters / helpers -> `tests/unit/pricing-and-formatters.test.ts`
   - Master-data JSON / seed schema & FKs -> synchronize `master-data/seed/*.json` + `master-data/*.json` and update `tests/unit/master-data-contract.test.ts`
   - KPIs, periods (`today`/`7d`/`30d`), branches, funnel, schedule, or Benchmark series -> `tests/unit/analytics-engine.test.ts`
   - REST API / persistence / fallback -> `tests/e2e/api-master-data.spec.ts`
   - Buttons, switches, filters, `<1/N>` pagination, modals, workflows, or RBAC (`Quản lý` vs `Lễ tân`) -> `tests/e2e/buttons-and-modals.spec.ts` & `tests/e2e/workflows-and-rbac.spec.ts`
   - Layout / responsive changes -> verify all 7 viewports (`1440×900`, `1280×800`, `1024×768`, `768×1024`, `390×844`, `375×667`, `360×800`) in `tests/e2e/responsive-matrix.spec.ts` (`scrollWidth <= innerWidth`, zero console/page errors)
   - Document added/updated test IDs in `tests/TEST_CASES.md`.
2. **Mandatory Verification Gate Before Completion**:
   - Run `npm test` AND `npm run build` (`tsc -b && vite build`).
   - Do NOT finish or report completion until **100% of unit + E2E + responsive tests and production build pass with 0 errors**, and never kill an already-running Vite dev server on `localhost:5182`.

---

## 6. API QA Testing, Staging Boundary & `API_BUGS` Tracker Sync (`.agents/skills/api-qa-testing`)
Whenever asked to write, review, validate, execute, or export API test cases, Postman collections, request payload fixtures, or cross-service contract matrices (e.g., `OP-1593` Accommodation Registration V2 across `ota-partner-acquisition-web → API Gateway → Partner Service → Media / Location → Admin`), ALWAYS activate `.agents/skills/api-qa-testing/SKILL.md`:
1. **Staging-Only Target Boundary (`https://web.stag.goodnstay.com/`)**: Execute live API testing **ONLY on Staging** via `https://web.stag.goodnstay.com/` (and its Staging backend `https://services.stag.goodnstay.com` / `*.stag.goodnstay.com`). **NEVER** send API test traffic to Production (`https://goodnstay.com` or `https://services.goodnstay.com` — blocked by `FORBIDDEN_PRODUCTION_URL`).
2. **No Guessing (`BLOCKED — API contract missing`)**: Never invent endpoint URLs, field names, HTTP statuses, or `errorCode`s, and never use `https://api.example.test/...` as a STAGING URL. Use `POST {{baseUrl}}{{registrationPath}}`, `<CHECK_OPENAPI>`, `<CHECK_ERROR_REGISTRY>`, and explicitly flag missing contracts and their owners.
3. **Mandatory 14-Field Schema + Section 5.2 JSON Record**: Every API test case must include all 14 fields from the goodNstay QA Guide (`Test Case ID`, `Title`, `Requirement`, `Priority / Test layer`, `Environment`, `Preconditions`, `Method + URL`, `Headers / Auth / Parameters`, `Payload / Test data`, `Steps`, `Expected response`, `Expected data result`, `Actual result`, `Status and evidence`) plus the Section 5.2 JSON execution record.
4. **Complete Valid Fixture + Single-Variable Mutation**: Derive negative/boundary payloads from a complete valid fixture (`valid-registration-v2.json`) by mutating **one variable only** (e.g., removing `primaryContact.phoneCountry` while keeping `primaryContact.phone` in valid E.164 `+84900000000`).
5. **Persistence Readback & Error Parity (`OP-1591` / `OP-1592`)**: Verify `GET` / Admin Reviewer readback on 2xx success, verify zero records created on 4xx error, and assert Partner domain errors never degrade to generic `DOWNSTREAM_CLIENT_ERROR` at API Gateway.
6. **Mandatory Pre-Test & Post-Test Self-Audit Gate (Zero QA Guide Violations)**:
   - **BEFORE testing**: Always re-read `guides/QA Guide — How to Write API Test Cases.md` and run `python3 .agents/skills/api-qa-testing/scripts/api_test_helper.py lessons`. Never treat frontend JS chunks (`_next/static/chunks/*.js`) as a Backend OpenAPI Error Registry; if Backend OpenAPI or Commit SHA is unpublished, keep `<CHECK_OPENAPI>`, `<CHECK_ERROR_REGISTRY>`, `<CHECK_DEPLOYED_SHA>`, mark passing checks `NOT VERIFIED` (never `PASS`), and mark contract-ambiguous checks `BLOCKED` (`Needs Verification` on Jira / `NEEDS REVIEW` on `API_BUGS`).
   - **DURING & AFTER testing (before Jira/Drive upload)**: Enforce **1 Test Case = 1 Endpoint = 1 Single-Variable Mutation = 1 Clear Result** (with dedicated `endpointBaseFixtures` per endpoint and no body on `GET` in Postman), scrub all DOM text nodes + user avatars via `TreeWalker` and **visually inspect every `.png` via `read_file`** to confirm 0% PII/name/avatar/phone/hash leak (deleting old Jira attachments via `DELETE /rest/api/3/attachment/{id}` before replacing), and run `python3 .agents/skills/api-qa-testing/scripts/api_test_helper.py validate <suite.json> --strict` (`0 ERROR, 0 WARN`) + unit tests (`python3 -W error -m unittest discover -s .agents/skills/api-qa-testing/tests`).
7. **Auto-Upload Jira + Auto-Sync Sheet `API_BUGS` (`1u11CxA99JxABEny9Gtgvi8Ylk0zOj8mo`)**: When live Staging API testing uncovers a confirmed defect:
   - Auto-publish to **Jira Scrum Board `#135`** (`Internship Program 2026`, `OP`) via `jira_bug_reporter.py --confirm` (with anti-duplicate check, all 12 `OP` structured fields, `assignee = Nguyen Bao Minh`, inline `.png` evidence + isolated per-case `<CASE_ID>.postman_collection.json` via `export-postman --case-id <CASE_ID>` + sanitized `<fixture>.json` for body-sending endpoints) and verify `on_board == True`.
   - Immediately download the latest `gns_Bug_Report_Tracking.xlsx` from Google Drive (`get_drive_file_download_url(file_id="1u11CxA99JxABEny9Gtgvi8Ylk0zOj8mo")`), upsert the Vietnamese row(s) into worksheet **`API_BUGS`** (`gid=985739379`, `Table1_4`, 20 columns `A10:T10`: `Environment = STAG`, `QA Stage = NEW`, `Retest Result = NOT RUN`, clickable hyperlinks on `Evidence Link` Col `L` and `Jira Bug` Col `N`) via `python3 .agents/skills/api-qa-testing/scripts/sync_api_bugs_sheet.py`, verify OpenXML/Excel integrity, and upload back in-place via `update_drive_file(file_id="1u11CxA99JxABEny9Gtgvi8Ylk0zOj8mo")`.
8. **OWASP Top 10:2025 & OWASP API Security Top 10:2023 Non-Destructive Integration**:
   - Design Staging security/permission/resilience test cases using the 8 non-destructive single-variable mutations (`SEC-M01`..`SEC-M08`, reference suite `examples/suites/stag_owasp_security_smoke_suite/stag_owasp_security_smoke_test_suite.json`), tagging `"owaspMapping"` (`A01:2025`..`A10:2025`, `X01:2025`..`X03:2025`, `API1:2023`..`API10:2023`) + `"owaspRemediationUrl"` and keeping two-actor BOLA or unconfirmed-contract cases marked `NOT VERIFIED` / `BLOCKED`.
   - Rely on `api_test_helper.py` (`export-postman` & `run-suite`) passive assertions to fail any response leaking raw credential/secret columns (`A04:2025`) or throwing unhandled `5xx` / stack traces (`A10:2025`), and always attach `OWASP Top 10:2025 + CWE + Cheat Sheet remediation` into Jira `OP` RCA fields and `API_BUGS` `Notes / Link`.

---

## 7. Staging Auto-Bid & Payment Test Seeding (`.agents/skills/stag-autobid-seeder`)
Whenever asked to create/seed a room request with a live hotel bid on **Staging** (`web.stag.goodnstay.com` / `services.stag.goodnstay.com`) to test **Payment, FX conversion, checkout, or offer acceptance**, or when blocked by Korea UI `LocationPicker` bug `OP-1787` (`400 INVALID_CITY_CODE` / `INVALID_DISTRICT_CODE`) or `isNoMatchedHotel: true`, ALWAYS activate `.agents/skills/stag-autobid-seeder/SKILL.md` and use `.agents/skills/stag-autobid-seeder/scripts/seed_stag_autobid.py`:
1. **Reuse Before Creating (`--seed`)**: Run `python3 .agents/skills/stag-autobid-seeder/scripts/seed_stag_autobid.py --seed` first so an unexpired (`>= 5` min left) `waiting` offer is reused without spamming Staging; pass `--seed --force-new` only when a brand-new deal is needed.
2. **`Stay Hotel H11` Auto-Bid Invariants**: Direct `POST /api/traveler/request-bids` on Staging requires `stayingCountry: "KR"`, `stayingProvince: "KR-11"`, mirrored `stayingCity: "KR-11"` (`OP-834`), `stayingDistrict: ""`, `accommodationType: "hotel"`, `roomTypes: ["suite", "anyRoom"]`, `guestCount <= 8`, and `roomCount <= 4`. BullMQ emits the `waiting` bid (`169.4 KRW`, 1h expiry) asynchronously in ~2–3.5s.
3. **Hygiene & Verification**: Clean up orphan unmatched/expired open deals via `--cancel-unmatched` (never cancelling active `waiting` offers), never print `data.jwt` or passwords, and verify skill edits with `python3 -W error -m unittest discover -s .agents/skills/stag-autobid-seeder/tests`.
