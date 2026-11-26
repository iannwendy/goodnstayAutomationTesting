# Quy Trình Vận Hành Chuẩn (SOP): AI Agent Chạy Test Tự Động → Auto Jira Board `#135` → Auto Google Sheet (`gns_Bug_Report_Tracking.xlsx`)

Tài liệu này mô tả chính xác từng bước mà AI Agent thực hiện từ lúc bắt đầu kiểm thử đến khi ticket hiển thị đầy đủ trên **Jira Board `#135` (`Internship Program 2026`)** và dòng báo cáo tiếng Việt có hyperlink hoạt động xuất hiện trên **Google Drive Tracker (`gns_Bug_Report_Tracking.xlsx`)**.

---

## 1. Bản Đồ Tài Nguyên & Hằng Số Hệ Thống

| Thành phần | Giá trị chuẩn | Ghi chú quan trọng |
| :--- | :--- | :--- |
| **Staging Web** | `https://web.stag.goodnstay.com/<locale>/home` | Mọi live API test & QA audit **chỉ nhắm Staging** (`FORBIDDEN_PRODUCTION_URL` chặn cứng `goodnstay.com`) |
| **Staging API** | `https://services.stag.goodnstay.com` | Backend Strapi + API Gateway Staging |
| **Jira Cloud Site** | `https://optibide-org.atlassian.net` | Đọc cấu hình từ `.env.jira` |
| **Jira Project / Type** | `Optibide` (`key: OP`, `id: 10001`) · `Bug` (`id: 10009`) | `labels` bị bỏ qua tự động vì không có trên Create Screen của `OP` |
| **Jira Scrum Board** | **Board `#135`** (`Internship Program 2026`) | Lọc qua **`Filter 10233`**: ticket **bắt buộc có `assignee`** (giữ `JIRA_AUTO_ASSIGN_SELF=true`) mới hiện lên Board |
| **12 Trường Custom Tab `OP`** | `Reporting`: `10053` (Environment), `10170` (Pre-condition), `10135` (Step-by-step), `10137` (Actual Result), `10057` (UI References)<br>`Expectation`: `10136` (Expected Result)<br>`RCA`: `10049` (Signals & Clues), `10051` (Detailed Analysis), `10004` (Impact), `10038` (Platform), `10039` (Original Source Location), `priority` | Tự động điền đủ bởi `jira_bug_reporter.py` (`build_structured_custom_fields`) kèm ảnh `mediaSingle` nhúng trực tiếp |
| **Google Drive Tracker** | `gns_Bug_Report_Tracking.xlsx` · **`file_id = 1u11CxA99JxABEny9Gtgvi8Ylk0zOj8mo`** | Tải bản mới nhất trước khi sửa bằng `google-workspace` MCP `get_drive_file_download_url` |
| **Sheet UI / E2E / Functional** | **`BUG_TRACKER`** (20 cột `A10:T10`) | Cập nhật bằng `scripts/sync_bug_tracker_sheet.py` |
| **Sheet API / Security** | **`API_BUGS`** (`gid=985739379`, `Table1_4`, 20 cột `A10:T10`) | Cập nhật bằng `.agents/skills/api-qa-testing/scripts/sync_api_bugs_sheet.py` |
| **Thư mục Upload MCP** | `~/.workspace-mcp/attachments/` | Bắt buộc lưu file `.xlsx` output vào đây để thỏa `ALLOWED_FILE_DIRS` của `google-workspace` MCP `update_drive_file` |
| **Confluence Specs** | `166952975` (Accommodation Route), `165937257` (Payment & FX), `171376745` (Design & Responsive), `524593` (API Standard), `144015744` (OpenAPI & Error Contract), `184944019` (QA Guide API Test Cases) | Đọc qua `atlassian` MCP `getConfluenceContent` trước khi chốt `classification` |

---

## 2. Quy Trình A — Kiểm Thử Web UI / E2E / Responsive / i18n → Jira → `BUG_TRACKER`

```text
[1. Pre-Check]  Đọc AGENTS.md + templates/existing_bugs_exclude.md + Confluence Specs (atlassian MCP)
       │
[2. Execute]    Playwright / Chrome DevTools test đa viewport (1440, 1280, 768, 390, 375, 360)
       │        cả Guest & Signed-in, đo getBoundingClientRect(), bắt F12 Console & Network
       │
[3. Scrub PII]  Che tên thật, avatar Google, email/SĐT trên DOM (TreeWalker) hoặc làm mờ (Pillow)
       │        + BẮT BUỘC mở từng file .png bằng read_file để kiểm tra 0% lộ PII
       │
[4. Package]    Đóng gói 1 Issue = 1 Payload 7-field (json_payloads/BUG-XXX.json) + consolidated_bugs.json
       │
[5. Jira Sync]  Chạy upload_jira_batch.py (dry-run trước -> --confirm sau khi duyệt)
       │        -> Chống trùng theo Board #135 -> Ghi ngay vào uploaded_jira_tickets.json
       │        -> Verify live: on_board == True, đủ 12 custom fields, đủ ảnh inline
       │
[6. Sheet Sync] get_drive_file_download_url(1u11CxA99JxABEny9Gtgvi8Ylk0zOj8mo)
       │        -> scripts/sync_bug_tracker_sheet.py (lxml.etree, 20 cột, hyperlink L & N)
       │        -> ./scripts/verify_xlsx_excel.sh (ZIP CRC + XML + macOS Excel osascript)
       │        -> update_drive_file(1u11CxA99JxABEny9Gtgvi8Ylk0zOj8mo, file_path=~/.workspace-mcp/attachments/...)
```

### Lệnh mẫu cho Quy Trình A
```bash
# Bước 5a: Xem trước toàn bộ batch (an toàn, không tạo ticket)
python3 scripts/upload_jira_batch.py \
  --consolidated ./run_YYYY-MM-DD/consolidated_bugs.json

# Bước 5b: Đẩy thật lên Jira Board #135 & tự động verify 12 custom fields + ảnh inline
python3 scripts/upload_jira_batch.py \
  --consolidated ./run_YYYY-MM-DD/consolidated_bugs.json \
  --expected-assignee "Nguyen Bao Minh" \
  --confirm

# Bước 6a: Đồng bộ vào sheet BUG_TRACKER (sau khi gọi MCP get_drive_file_download_url)
python3 scripts/sync_bug_tracker_sheet.py \
  --xlsx ~/.workspace-mcp/attachments/gns_Bug_Report_Tracking.xlsx \
  --consolidated ./run_YYYY-MM-DD/consolidated_bugs.json \
  --uploaded ./run_YYYY-MM-DD/uploaded_jira_tickets.json \
  --reported-by "Nguyen Bao Minh" \
  --reported-on "$(date +%Y-%m-%d)" \
  --output ~/.workspace-mcp/attachments/gns_Bug_Report_Tracking_updated.xlsx

# Bước 6b: Bắt buộc kiểm định OpenXML + mở sạch bằng Microsoft Excel trước khi upload Drive
./scripts/verify_xlsx_excel.sh ~/.workspace-mcp/attachments/gns_Bug_Report_Tracking_updated.xlsx
```
Sau bước 6b, Agent gọi `google-workspace` MCP:
`update_drive_file(file_id="1u11CxA99JxABEny9Gtgvi8Ylk0zOj8mo", file_path="~/.workspace-mcp/attachments/gns_Bug_Report_Tracking_updated.xlsx")` (dùng đường dẫn tuyệt đối mở rộng từ `$HOME`).

---

## 3. Quy Trình B — Kiểm Thử Staging API & OWASP Top 10:2025 → Auto Jira → Auto `API_BUGS`

> **Lưu ý Pre-Authorized:** Đối với kiểm thử API trên **Staging (`web.stag.goodnstay.com` / `services.stag.goodnstay.com`)**, theo `AGENTS.md` §3 & §6, mọi lỗi API đã xác nhận (`FAIL`) được ủy quyền **tự động đẩy Jira (`--confirm`) VÀ tự động cập nhật sheet `API_BUGS`** ngay sau khi vượt qua Cổng Tự Kiểm Định 8 Điểm.

### 6 Bước Bắt Buộc
1. **Pre-Test Audit (Bắt buộc trước khi gửi bất kỳ request nào):**
   ```bash
   python3 .agents/skills/api-qa-testing/scripts/api_test_helper.py lessons
   ```
   - Đọc lại `guides/QA Guide — How to Write API Test Cases.md`.
   - Kiểm tra 7 đầu vào bắt buộc (Requirement/Jira, OpenAPI, Staging Base URL, Method+Path, Auth, Fixtures, Deployed SHA).
   - **Không bao giờ đoán contract:** Nếu thiếu OpenAPI/Error Registry hoặc Backend SHA, giữ `<CHECK_OPENAPI>`, `<CHECK_ERROR_REGISTRY>`, `<CHECK_DEPLOYED_SHA>`; case không fail khi thiếu SHA phải để `NOT VERIFIED` (không để `PASS`), case mơ hồ contract để `BLOCKED` (`Needs Verification` trên Jira / `NEEDS REVIEW` trên `API_BUGS`).
2. **Thiết kế Fixture hợp lệ + Đột biến đơn biến (`1 Test Case = 1 Endpoint = 1 Mutation = 1 Result`):**
   - Mỗi endpoint có `endpointBaseFixtures` riêng (và `GET`/`DELETE` không mang body trong Postman).
   - Gắn thẻ bảo mật `"owaspMapping"` (`SEC-M01`..`SEC-M08`, `A01:2025`..`A10:2025`, `API1:2023`..`API10:2023`) + `"owaspRemediationUrl"`.
3. **Kiểm định Strict + Chạy Suite + Xuất Artifacts:**
   ```bash
   python3 .agents/skills/api-qa-testing/scripts/api_test_helper.py validate path/to/suite.json --strict
   python3 .agents/skills/api-qa-testing/scripts/api_test_helper.py export-markdown path/to/suite.json --output path/to/test_cases.md
   python3 .agents/skills/api-qa-testing/scripts/api_test_helper.py export-postman path/to/suite.json --output path/to/suite.postman_collection.json
   # Xuất Postman cô lập cho từng bug để đính kèm Jira:
   python3 .agents/skills/api-qa-testing/scripts/api_test_helper.py export-postman path/to/suite.json --case-id STAG-API-001 --output path/to/STAG-API-001.postman_collection.json
   ```
4. **Cổng Tự Kiểm Định 8 Điểm (Post-Test Self-Audit Gate):**
   - `validate --strict` đạt `0 ERROR, 0 WARN`
   - 0% đoán contract, 0% `PASS` khi thiếu Backend SHA
   - 1 Issue = 1 Endpoint = 1 Single-Variable Mutation
   - Postman chạy được 100% (đúng schema từng endpoint, không có body trên `GET`)
   - Đã scrub DOM + avatar và **xem bằng mắt từng ảnh `.png` qua `read_file`** (0% lộ PII/token/hash)
   - Đã dọn sạch dữ liệu test tạo ra trên Staging (hủy đơn test, khôi phục profile qua `GET` readback)
5. **Auto-Publish Jira Board `#135` (đính kèm 3 file chuẩn: `.png` + `<CASE_ID>.postman_collection.json` + `<fixture>.json` nếu có body):**
   ```bash
   python3 .agents/skills/jira-bug-reporter/scripts/jira_bug_reporter.py \
     --input path/to/BUG-API-01.json --confirm
   ```
   *(Nếu cập nhật lại ảnh của ticket cũ, phải `DELETE /rest/api/3/attachment/{old_id}` trước để không sót ảnh cũ trên Jira.)*
6. **Auto-Sync Sheet `API_BUGS` (`gid=985739379`) & Upload lên Google Drive:**
   ```bash
   python3 .agents/skills/api-qa-testing/scripts/sync_api_bugs_sheet.py \
     --xlsx ~/.workspace-mcp/attachments/gns_Bug_Report_Tracking.xlsx \
     --bugs path/to/api_bugs_sheet_rows.json \
     --output ~/.workspace-mcp/attachments/gns_Bug_Report_Tracking_updated.xlsx

   ./scripts/verify_xlsx_excel.sh ~/.workspace-mcp/attachments/gns_Bug_Report_Tracking_updated.xlsx
   ```
   Sau đó gọi `update_drive_file(file_id="1u11CxA99JxABEny9Gtgvi8Ylk0zOj8mo", file_path="<ABS_HOME>/.workspace-mcp/attachments/gns_Bug_Report_Tracking_updated.xlsx")`.

---

## 4. Quy Trình C — Seed Auto-Bid Test Payment & Dashboard QA

- **Seed offer sống từ `Stay Hotel H11` trên Staging (bypass lỗi `OP-1787` Korea LocationPicker):**
  ```bash
  python3 .agents/skills/stag-autobid-seeder/scripts/seed_stag_autobid.py --seed
  # Dọn các yêu cầu mồ côi chưa có offer sau khi test:
  python3 .agents/skills/stag-autobid-seeder/scripts/seed_stag_autobid.py --cancel-unmatched
  ```
- **Dashboard QA Regression (`dashboard/dashboard`):**
  - Mọi chỉnh sửa code/UI/master-data phải kèm unit/E2E/responsive test mới và chạy `npm test && npm run build` đạt 100% PASS (chi tiết trong `.agents/skills/dashboard-qa-testing/SKILL.md` & `guides/dashboard_AGENTS.md`).

---

## 5. Chuẩn 20 Cột Excel (`BUG_TRACKER` & `API_BUGS`, `A10:T10`)

| Cột | Tên Cột | Giá trị chuẩn / Dropdown bắt buộc |
| :---: | :--- | :--- |
| `A` | `ID` | Số thứ tự tăng dần (`max_seq_id + 1`) |
| `B` | `Bug ID / Jira ID` | `BUG-086` (`BUG_TRACKER`) hoặc `BUG-API-01` (`API_BUGS`) |
| `C` | `Summary / Title` | Tiếng Việt rõ ràng `[Khu vực - Thành phần] Lỗi thực tế + Ngữ cảnh` |
| `D` | `Feature / Area / Epic` | Module / Endpoint / Epic tương ứng |
| `E` | `Type` | `FUNCTIONAL`, `End to End`, `UI/UX (FE)`, `I18N`, `RESPONSIVE`, `CONTENT`, `PERFORMANCE`, `DATA INVALID`, `OTHER` |
| `F` | `Severity` | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` |
| `G` | `Steps to Reproduce` | Các bước tái hiện đánh số rõ ràng (tiếng Việt) |
| `H` | `Expected Result` | Kết quả mong đợi bám Confluence Spec / OpenAPI / OWASP |
| `I` | `Actual Result` | Số liệu thực tế đo được (HTTP status, px, DOM state, `requestId`) |
| `J` | `Environment / Build` | **`STAG`** (bắt buộc cho `API_BUGS`) |
| `K` | `Device / Locale` | VD: `Staging API & Chrome · 1440×900 · en-US` hoặc `Mobile 375×667 · vi-VN` |
| `L` | `Evidence Link` | Tên file `.png` + Jira key, gắn **external hyperlink** trực tiếp tới Jira attachment URL |
| `M` | `QA Stage` | `NEW`, `NEEDS REVIEW`, `CONFIRMED`, `IN PROGRESS`, `READY FOR RETEST`, `REOPENED`, `CLOSED`, `NOT A BUG`, `DUPLICATE`, `OBSERVATION` |
| `N` | `Jira Bug` | URL `https://optibide-org.atlassian.net/browse/OP-XXXX` gắn **external hyperlink** |
| `O` | `Reported By` | `Nguyen Bao Minh` (hoặc tên QA phụ trách) |
| `P` | `Reported On` | Excel serial date (`YYYY-MM-DD`) |
| `Q` | `Assigned To` | Để trống (PM/Lead phân công) |
| `R` | `Retest Result` | `NOT RUN`, `PASS`, `FAIL`, `BLOCKED`, `NOT VERIFIED`, `N/A` |
| `S` | `Retest Date` | Để trống khi mới tạo |
| `T` | `Notes / Link` | Mã Test Case, nguyên nhân gốc CSS/JS/BE, phân loại OWASP Top 10:2025 + CWE + Cheat Sheet link |

---

## 6. Prompt Mẫu Kích Hoạt Agent Chạy Đúng Quy Trình

### Mẫu 1 — Chạy Staging UI / Responsive / Functional QA + Auto Jira + Auto `BUG_TRACKER`
> *"Hãy đọc `AGENTS.md`, `templates/existing_bugs_exclude.md` và `guides/END_TO_END_WORKFLOW_SHEET_JIRA.md`. Thực hiện kiểm thử Staging (`https://web.stag.goodnstay.com`) cho luồng `<TÊN LUỒNG>` trên đủ 6 viewports (`1440x900`, `1280x800`, `768x1024`, `390x844`, `375x667`, `360x800`) và các ngôn ngữ `<en-US, vi-VN, ...>`. Chỉ báo cáo lỗi mới không trùng, scrub sạch 100% PII trên ảnh chụp (mở kiểm tra từng ảnh bằng `read_file`), chạy preview `upload_jira_batch.py` trước để tôi duyệt; sau khi tôi đồng ý hãy đẩy lên Jira Board `#135`, verify đủ 12 trường custom `OP`, rồi đồng bộ vào sheet `BUG_TRACKER` trên Google Drive (`1u11CxA99JxABEny9Gtgvi8Ylk0zOj8mo`) sau khi kiểm định bằng `scripts/verify_xlsx_excel.sh`."*

### Mẫu 2 — Chạy Staging API & OWASP Security QA + Auto Jira + Auto `API_BUGS`
> *"Hãy kích hoạt skill `api-qa-testing` và tuân thủ `AGENTS.md` §6. Trước hết chạy `api_test_helper.py lessons` và đọc `guides/QA Guide — How to Write API Test Cases.md`. Thực hiện kiểm thử API phi phá hủy trên Staging (`https://services.stag.goodnstay.com`) cho nhóm endpoint `<TÊN MODULE/ENDPOINT>` theo chuẩn 14 trường + đơn biến + OWASP Top 10:2025 (`SEC-M01`..`SEC-M08`). Sau khi vượt qua cổng tự kiểm định 8 điểm (`validate --strict` 0 ERROR/0 WARN, 0% PII trên ảnh `.png`), tự động đẩy các lỗi `FAIL` lên Jira Board `#135` (kèm ảnh + Postman từng case + fixture) và đồng bộ ngay vào sheet `API_BUGS` (`gid=985739379`) của file `gns_Bug_Report_Tracking.xlsx` (`1u11CxA99JxABEny9Gtgvi8Ylk0zOj8mo`)."*
