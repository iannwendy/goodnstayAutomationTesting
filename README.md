# goodNstay QA Automation Testing Kit (`agent_automationTesting`)

Bộ đóng gói hoàn chỉnh gồm **toàn bộ quy trình (Workflow), bộ luật (`AGENTS.md`), 4 kỹ năng AI Agent (`.agents/skills/`), tài liệu chuẩn QA/OWASP (`guides/`), template chống trùng & báo cáo (`templates/`), cấu hình MCP mẫu (`config/`) và bộ script tự động (`scripts/`)** để thiết lập một AI Agent chạy kiểm thử tự động và **tự đẩy lỗi chuẩn lên Jira Board `#135` + đồng bộ lên Google Drive Excel (`gns_Bug_Report_Tracking.xlsx`)** theo đúng chuẩn đang áp dụng tại goodNstay.

---

## 1. Cấu Trúc Thư Mục

```text
agent_automationTesting/
├── AGENTS.md                                  # Bộ luật gốc bắt buộc cho AI Agent (QA Rules, Jira Board #135, OpenXML, API QA, OWASP, Seeder)
├── README.md                                  # Tài liệu setup nhanh & điều hướng toàn bộ bộ công cụ (file này)
├── requirements.txt                           # Thư viện Python cần cài (lxml cho Excel OpenXML, Pillow cho làm mờ PII)
├── .env.jira.example                          # Mẫu biến môi trường kết nối Jira Cloud (copy thành .env.jira, KHÔNG commit token thật)
├── .env.stag.example                          # Mẫu tài khoản QA Staging (tùy chọn ghi đè cho stag-autobid-seeder)
├── .gitignore                                 # Chặn commit nhầm token (.env.jira, .env.stag), cache và file .xlsx tạm
│
├── .agents/skills/                            # 4 AI Agent Skills tự động nhận diện bởi Antigravity / AI IDE
│   ├── jira-bug-reporter/                     # Skill + CLI tạo/cập nhật Jira Bug 7-field + đủ 12 trường OP + ảnh inline
│   ├── api-qa-testing/                        # Skill + CLI kiểm định 14-field API, Postman v2.1, OWASP, sync sheet API_BUGS & bộ nhớ tự học
│   ├── stag-autobid-seeder/                   # Skill + CLI seed/reuse/cleanup Auto-Bid trên Staging (bypass OP-1787 để test Payment)
│   └── dashboard-qa-testing/                  # Skill kiểm thử hồi quy bắt buộc (Unit + E2E + RBAC + 7 Viewports) cho Partner Dashboard
│
├── scripts/                                   # Bộ script pipeline tái sử dụng cho mọi đợt test
│   ├── upload_jira_batch.py                   # Đẩy hàng loạt lên Jira Board #135 (anti-duplicate, retry, verify đủ 12 custom fields)
│   ├── sync_bug_tracker_sheet.py              # Đồng bộ OpenXML-safe (lxml) vào sheet BUG_TRACKER (20 cột + hyperlink)
│   ├── verify_xlsx_excel.sh                   # Kiểm định ZIP CRC, XML namespaces (không có ns0:) và mở kiểm tra bằng Microsoft Excel (macOS)
│   └── verify_setup.sh                        # Chạy kiểm tra 1 lệnh: Python, lxml/Pillow, toàn bộ unit tests, strict suite & kết nối Jira
│
├── guides/                                    # Bộ tài liệu chuẩn & SOP vận hành chi tiết
│   ├── END_TO_END_WORKFLOW_SHEET_JIRA.md      # SOP từ A–Z: Test Web/API -> Scrub PII -> Auto Jira Board #135 -> Auto Google Sheet
│   ├── QA Guide — How to Write API Test Cases.md   # Chuẩn viết API Test Case 14 trường + Section 5.2 JSON (v1.0 EN / v3.0 VI)
│   ├── O-QA Guide — How to Write API Test Cases-111126-025244.pdf
│   ├── goodNstay_OWASP_API_Security_And_Staging_Audit_Guide.md # Chuẩn OWASP Top 10:2025 + 8 đột biến SEC-M01..SEC-M08
│   └── dashboard_AGENTS.md                    # Luật kiểm thử bắt buộc cho dự án Partner Auction Dashboard v2
│
├── templates/                                 # Biểu mẫu & sổ chống trùng bug
│   ├── existing_bugs_exclude.md               # Danh sách bug đã báo cáo (OP-XXXX / BUG-XXX) để Agent lọc chống trùng trước khi log
│   ├── api_bugs_sheet_rows.example.json       # Mẫu JSON đầu vào cho sync_api_bugs_sheet.py (sheet API_BUGS)
│   ├── consolidated_bugs.example.json         # Mẫu JSON đầu vào cho upload_jira_batch.py & sync_bug_tracker_sheet.py (sheet BUG_TRACKER)
│   └── [Vinh]goodNstay_Marketplace_Accommodation_Bug_Report_Template_v1.docx
│
├── config/
│   └── mcp_config.example.json                # Mẫu cấu hình 4 MCP Servers: atlassian, google-workspace, playwright, chrome-devtools
│
└── examples/                                  # Bộ suite và script mẫu thực chiến
    ├── suites/stag_owasp_security_smoke_suite/# Bộ mẫu OWASP Security Smoke (OWASP-SEC-001..008, fixtures, Postman, Markdown)
    └── workflows/                             # Script mẫu xử lý báo cáo: gom bug + blur PII, tạo Jira payload, tạo dòng API_BUGS
```

---

## 2. Hướng Dẫn Setup Agent Từ Đầu (5 Bước Nhanh)

### Cách dùng bộ thư mục này
- **Cách 1 (Chạy độc lập):** Mở thẳng thư mục `agent_automationTesting/` làm Workspace trong Antigravity / AI Coding Agent — hệ thống sẽ tự động nạp `AGENTS.md` và toàn bộ 4 skills trong `.agents/skills/`.
- **Cách 2 (Tích hợp vào repo dự án mới):** Copy `AGENTS.md`, `.agents/`, `scripts/`, `guides/`, `templates/`, `.env.jira.example` và `requirements.txt` vào thư mục gốc của repo đích.

### Bước 1: Cài đặt Python 3 và thư viện cần thiết
```bash
python3 -m pip install -r requirements.txt
```
> *Ghi chú:* Các CLI lõi (`jira_bug_reporter.py`, `api_test_helper.py`, `seed_stag_autobid.py`, `upload_jira_batch.py`) dùng 100% thư viện chuẩn Python 3. Riêng `lxml` cần cho đồng bộ Excel OpenXML (`sync_api_bugs_sheet.py`, `sync_bug_tracker_sheet.py`) và `Pillow` cần khi dùng làm mờ vùng PII trên ảnh `.png`.

### Bước 2: Thiết lập Jira API Token (`.env.jira`)
1. Tạo Personal API Token tại: https://id.atlassian.com/manage-profile/security/api-tokens
2. Tạo file `.env.jira` từ mẫu và khóa quyền đọc cá nhân (`chmod 600`):
   ```bash
   cp .env.jira.example .env.jira
   chmod 600 .env.jira
   ```
3. Mở `.env.jira`, điền `JIRA_EMAIL` và `JIRA_API_TOKEN` của bạn (giữ `JIRA_PROJECT_KEY=OP`, `JIRA_AUTO_ASSIGN_SELF=true` để ticket tự hiện trên Board `#135 — Internship Program 2026`).
4. *(Tùy chọn)* Nếu muốn dùng tài khoản Staging QA khác mặc định cho `stag-autobid-seeder`:
   ```bash
   cp .env.stag.example .env.stag
   chmod 600 .env.stag
   ```

> [!CAUTION]
> **Nguyên tắc Secret Hygiene:** Tuyệt đối **KHÔNG** commit `.env.jira`, `.env.stag`, không in/echo `JIRA_API_TOKEN` ra terminal và không đưa token thật vào prompt/file JSON.

### Bước 3: Kết nối 4 MCP Servers cho Agent
Tham khảo cấu trúc mẫu tại [`config/mcp_config.example.json`](./config/mcp_config.example.json) để cài/bật 4 MCP Servers trên Antigravity (qua Plugins Manager hoặc `~/.gemini/config/mcp_config.json` với `chmod 600`):
1. **`atlassian`** (`https://mcp.atlassian.com/v2/mcp`) — Đọc Confluence specs (`166952975`, `165937257`, `171376745`, `524593`, `184944019`) và tra cứu ticket Jira tránh trùng.
2. **`google-workspace`** — Tải file `gns_Bug_Report_Tracking.xlsx` mới nhất (`get_drive_file_download_url`) và cập nhật đè an toàn (`update_drive_file`) với `file_id = 1u11CxA99JxABEny9Gtgvi8Ylk0zOj8mo`.
3. **`playwright`** — Chạy kiểm thử trình duyệt đa viewport (`1440×900`, `1280×800`, `768×1024`, `390×844`, `375×667`, `360×800`), đo tọa độ DOM và chụp ảnh bằng chứng.
4. **`chrome-devtools`** — Kiểm tra F12 Console, F12 Network và computed CSS styles.

### Bước 4: Kiểm tra toàn bộ hệ thống bằng 1 lệnh
```bash
chmod +x scripts/verify_setup.sh scripts/verify_xlsx_excel.sh
./scripts/verify_setup.sh
```
Lệnh trên sẽ tự động xác minh:
- Phiên bản Python 3, `lxml`, `Pillow`
- 100% Unit Tests của cả 3 skill (`jira-bug-reporter`, `api-qa-testing`, `stag-autobid-seeder`) với cờ `python3 -W error`
- Bộ nhớ bài học `api_test_helper.py lessons` và kiểm định `--strict` 2 bộ test suite mẫu (`OP-1593` & `OWASP Security Smoke`)
- Kết nối thực tế tới Jira Cloud (`jira_bug_reporter.py --verify`) nếu `.env.jira` đã cấu hình.

### Bước 5: Chạy Quy Trình Thực Chiến (Auto Test → Auto Jira → Auto Sheet)
Xem chi tiết từng lệnh, sơ đồ luồng, cấu trúc 20 cột của `BUG_TRACKER` & `API_BUGS`, quy trình scrub PII và prompt mẫu kích hoạt Agent tại:
- **[`guides/END_TO_END_WORKFLOW_SHEET_JIRA.md`](./guides/END_TO_END_WORKFLOW_SHEET_JIRA.md)**

---

## 3. Tra Cứu Nhanh Các Lệnh Hay Dùng

| Tác vụ | Lệnh thực thi |
| :--- | :--- |
| Kiểm tra sức khỏe toàn bộ bộ setup | `./scripts/verify_setup.sh` |
| Kiểm tra kết nối Jira & Project `OP` | `python3 .agents/skills/jira-bug-reporter/scripts/jira_bug_reporter.py --verify` |
| Xem trước 1 ticket Jira (`dry-run`) | `python3 .agents/skills/jira-bug-reporter/scripts/jira_bug_reporter.py --input path/to/BUG-01.json` |
| Đẩy 1 ticket Jira kèm ảnh inline | `python3 .agents/skills/jira-bug-reporter/scripts/jira_bug_reporter.py --input path/to/BUG-01.json --confirm` |
| Cập nhật/bổ sung ticket Jira đã tạo | `python3 .agents/skills/jira-bug-reporter/scripts/jira_bug_reporter.py --input path/to/BUG-01.json --update OP-XXXX --confirm` |
| Đẩy hàng loạt lên Jira Board `#135` (chống trùng + verify) | `python3 scripts/upload_jira_batch.py --consolidated path/to/consolidated_bugs.json --confirm` |
| Đọc bài học QA API trước khi test | `python3 .agents/skills/api-qa-testing/scripts/api_test_helper.py lessons` |
| Kiểm định strict bộ API Test Suite | `python3 .agents/skills/api-qa-testing/scripts/api_test_helper.py validate path/to/suite.json --strict` |
| Xuất Postman cho 1 case đính kèm Jira | `python3 .agents/skills/api-qa-testing/scripts/api_test_helper.py export-postman path/to/suite.json --case-id CASE-01 --output CASE-01.postman_collection.json` |
| Đồng bộ lỗi UI/E2E vào sheet `BUG_TRACKER` | `python3 scripts/sync_bug_tracker_sheet.py --xlsx ~/.workspace-mcp/attachments/<file>.xlsx --consolidated consolidated_bugs.json --uploaded uploaded_jira_tickets.json --output ~/.workspace-mcp/attachments/gns_Bug_Report_Tracking_updated.xlsx` |
| Đồng bộ lỗi API vào sheet `API_BUGS` | `python3 .agents/skills/api-qa-testing/scripts/sync_api_bugs_sheet.py --xlsx ~/.workspace-mcp/attachments/<file>.xlsx --bugs api_bugs_sheet_rows.json --output ~/.workspace-mcp/attachments/gns_Bug_Report_Tracking_updated.xlsx` |
| Kiểm định file `.xlsx` trước khi up Drive | `./scripts/verify_xlsx_excel.sh ~/.workspace-mcp/attachments/gns_Bug_Report_Tracking_updated.xlsx` |
| Seed / tái sử dụng Auto-Bid trên Staging | `python3 .agents/skills/stag-autobid-seeder/scripts/seed_stag_autobid.py --seed` |
| Dọn đơn test unmatched trên Staging | `python3 .agents/skills/stag-autobid-seeder/scripts/seed_stag_autobid.py --cancel-unmatched` |
