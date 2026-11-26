#!/usr/bin/env python3
"""Consolidate, deduplicate, PII-scrub, and package the 25-11-2026 Staging QA audit."""

from __future__ import annotations

import json
import pathlib
import re
import shutil
from typing import Any
from PIL import Image, ImageFilter

BASE = pathlib.Path("/Users/iannwendy/Desktop/goodNstay/bug_report_25-11-2026")
CAND = BASE / "candidates"
SHOTS = BASE / "screenshots"
PAYLOADS = BASE / "json_payloads"

SHOTS.mkdir(parents=True, exist_ok=True)
PAYLOADS.mkdir(parents=True, exist_ok=True)

PII_BLUR_BOXES: dict[str, list[tuple[int, int, int, int]]] = {
    "A5-01_history_cancelled_nan_en_1440.png": [(1295, 25, 1435, 58)],
    "A5-01_history_cancelled_nan_vi_1440.png": [(1295, 25, 1435, 58)],
    "A5-05_history_vi_untranslated_sort_1440.png": [(1295, 25, 1435, 58)],
    "A5-03_profile_personal_readonly_1440.png": [
        (450, 238, 610, 272),
        (845, 238, 960, 272),
        (860, 488, 1020, 522),
    ],
    "A5-03_profile_edit_modal_blank_country_1440.png": [
        (670, 290, 825, 322),
        (645, 500, 745, 530),
    ],
    "A5-02_edit_modal_fab_overlap_375.png": [
        (30, 350, 130, 385),
    ],
}


def load_all_candidates() -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for sub in sorted(CAND.iterdir()):
        fj = sub / "findings.json"
        if fj.exists():
            items = json.loads(fj.read_text(encoding="utf-8"))
            for item in items:
                by_id[item["local_id"]] = item
    return by_id


def copy_and_scrub(src_path: pathlib.Path, dst_path: pathlib.Path) -> None:
    boxes = PII_BLUR_BOXES.get(src_path.name)
    if not boxes:
        shutil.copy2(src_path, dst_path)
        return
    im = Image.open(src_path).convert("RGBA")
    for box in boxes:
        crop = im.crop(box)
        blurred = crop.filter(ImageFilter.GaussianBlur(radius=9))
        im.paste(blurred, box)
    im.save(dst_path, format="PNG")


def scrub_text(s: str) -> str:
    return s.replace("Bảo Minh Nguyễn", "TEST_BAOMINH")


def clean_step(s: str) -> str:
    return re.sub(r"^\s*\d+\.\s+", "", scrub_text(s).strip())


def clean_ref_url(val: str) -> str:
    s = scrub_text(str(val)).strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    m = re.search(r"\b(OP-\d+)\b", s)
    if m:
        return f"https://optibide-org.atlassian.net/browse/{m.group(1)}"
    return "https://web.stag.goodnstay.com/en-US/home"


def build_consolidated_fab_bug(a5_02: dict[str, Any], a2_05: dict[str, Any], a4_03: dict[str, Any]) -> dict[str, Any]:
    return {
        "local_id": "FAB-CONSOLIDATED",
        "title": "[Global Layout - Floating GNS AI & Back-to-Top FABs] Excessive z-[9997]/z-[9998] Occludes 95% of Mobile Chat \"Send\" Button, Overlaps Tablet \"Google Play\" CTA, and Pierces Above z-[1400]/z-50 Modals & Popovers",
        "area": "Global Layout – Floating Action Buttons (GNS AI / Back-to-Top Layering)",
        "type": "RESPONSIVE",
        "severity": "S2 – Major",
        "sheet_severity": "HIGH",
        "priority_label": "P1",
        "environment": "Staging (STAG) · Tablet 768×1024, Mobile 390×844 / 375×667 / 360×800, Desktop 1440×900 · Chromium (Playwright) · All 7 Locales (https://web.stag.goodnstay.com/en-US/messages, /app-download, /user-profile/profile-details, /accommodation)",
        "test_account": "Both Guest Session & Signed-In Session (TEST_BAOMINH / baominh.internship@gmail.com)",
        "steps_to_reproduce": [
            "1. Sign in on Staging using TEST_BAOMINH, set viewport to Mobile 375×667 (iPhone SE), navigate to /en-US/history/completed -> click 'Message' (opens /en-US/messages?conversation=booking-1502), and inspect/tap the chat composer 'Send' button.",
            "2. At Mobile 375×667, navigate to /en-US/user-profile/profile-details -> click 'Edit' under Personal Information to open the 'Edit profile' modal (z-[1400]), and scroll the form to 'Save changes'.",
            "3. Open https://web.stag.goodnstay.com/en-US/app-download at Tablet 768×1024 (initial load, scrollY = 0) and inspect the 'Google Play →' CTA; then switch to Mobile 390×844, scroll to #download, and click the QR code card to open the 'Scan with iOS or Android' modal (z-index: 1400).",
            "4. On /en-US/accommodation at Mobile 360×800, click '+' -> expand '2/3 Request overview' -> tap 'Total guests *' to open the guest stepper popover (z-50) while scrolled down."
        ],
        "actual_result": (
            "The global floating buttons ('GNS AI' z-index: 9997 and 'Back to top' z-index: 9998 in /_next/static/chunks/3-q5yte2ewrs4.js) sit far above all dialogs (z-[1400]) and popovers (z-50), causing severe cross-page primary CTA obstruction:\n"
            "1. Message Center (/messages, Mobile 375×667): 'GNS AI' (left=248..351, top=599..643) covers 95% (66×38px) of the chat 'Send' button (left=276..342, top=597..637). document.elementFromPoint() at both center (309,617) and left edge (280,617) of 'Send' hits <a href='https://aperon.stag.optibide.com/en-US/'>GNS AI</a>, navigating users away instead of sending messages.\n"
            "2. Edit Profile Modal (/user-profile/profile-details, Mobile 375×667): Both FABs render unblurred above the z-[1400] dialog; even scrolled to the bottom, 'GNS AI' covers 28% of 'Save changes' (elementFromPoint(319,607) hits GNS AI) while 'Back to top' floats across the bottom-right corner.\n"
            "3. App Download Landing Page (/app-download, OP-2008): At Tablet 768×1024 initial load across all 7 locales, 'GNS AI' (641..744, 956..1000) directly overlaps the right 74×44px of 'Google Play →' (391..715, 947..1015). At Mobile 390×844, both FABs pierce razor-sharp and clickable above the blurred 'Scan with iOS or Android' QR Info Modal (z-index: 1400).\n"
            "4. Accommodation Request Form (/accommodation, Mobile 360×800): When the 'Total guests' popover (z-50) is open, 'Back to top' (z-[9998]) covers the 'Pets +' stepper button and 'GNS AI' (z-[9997]) covers the 'OK' button."
        ),
        "expected_result": (
            "1. Global floating widgets ('GNS AI' and 'Back to top') must use a z-index strictly lower than global modals, drawers, and form popovers (e.g., z-30/z-40 < z-50 popovers < z-[1400] HeadlessUI dialogs) or hide automatically whenever any modal/drawer/chat composer is active.\n"
            "2. Floating buttons must never intercept taps on primary conversion or messaging CTAs ('Send', 'Save changes', 'Google Play', 'OK')."
        ),
        "evidence": {
            "url": "https://web.stag.goodnstay.com/en-US/messages?conversation=booking-1502",
            "datetime": "25/11/2026 11:30 ICT",
            "console": "0 JavaScript console errors.",
            "network": "200 OK across /messages, /user-profile/profile-details, /app-download, and /accommodation.",
            "notes": (
                "Single global CSS stacking root cause in /_next/static/chunks/3-q5yte2ewrs4.js: 'AperonFloatButton' (GNS AI) uses fixed z-[9997] and 'Back to top' uses fixed z-[9998], overriding HeadlessUI Dialogs (z-[1400]) and form popovers (z-50) site-wide. "
                "Consolidated across 4 verified Staging surfaces (distinct from OP-1756 which covered Login/Sign-Up forms only)."
            ),
            "reference_url": "https://web.stag.goodnstay.com/en-US/app-download",
        },
        "classification": "Confirmed Bug — Global Z-Index Stacking Hierarchy Violation Blocking Mobile Chat Send, Profile Save, App Download CTA & Modals",
        "reproducibility": "Always (100% — reproduced across 4 distinct Staging pages on 768×1024, 390×844, 375×667, and 360×800)",
        "attachments": [
            a5_02["attachments"][0],
            a5_02["attachments"][1],
            a2_05["attachments"][1],
            a4_03["attachments"][1],
        ],
        "vi_summary": "[Bố cục toàn trang - Nút nổi GNS AI & Lên đầu trang] Gán cứng z-[9997]/z-[9998] che khuất 95% nút \"Send\" trong Tin nhắn mobile, đè nút \"Google Play\" trên Tablet và xuyên đè lên trên các Modal/Popover (z-[1400]/z-50)",
        "vi_steps": (
            "1. Mở /en-US/messages?conversation=booking-1502 ở Mobile 375×667 và thử nhấn nút 'Send'.\n"
            "2. Mở /en-US/user-profile/profile-details ở 375×667 -> nhấn 'Edit' mở modal 'Edit profile' (z-[1400]) và cuộn xuống nút 'Save changes'.\n"
            "3. Mở /en-US/app-download ở Tablet 768×1024 (xem nút Google Play) và Mobile 390×844 (mở modal hướng dẫn QR z-index: 1400).\n"
            "4. Mở /en-US/accommodation ở Mobile 360×800 -> mở popover 'Total guests' (z-50)."
        ),
        "vi_expected": "Nút nổi toàn cục 'GNS AI' và 'Lên đầu trang' phải có z-index thấp hơn modal/popover (<= z-40 < z-50 < z-[1400]) hoặc tự ẩn khi mở hộp thoại/khung chat, tuyệt đối không che khuất nút hành động chính (Send, Save changes, Google Play, OK).",
        "vi_actual": (
            "Hai nút nổi (GNS AI z-[9997], Back-to-top z-[9998]) đè xuyên trên mọi lớp giao diện: "
            "(1) Che 95% nút 'Send' ở Message Center 375×667 (bấm Send bị chuyển sang GNS AI); "
            "(2) Nổi sắc nét đè lên trên modal 'Edit profile' (z-[1400]), che 28% nút 'Save changes'; "
            "(3) Đè 74px lên nút 'Google Play →' ngay khi tải /app-download 768×1024 và nổi đè lên trên modal QR (z-index: 1400) ở 390×844; "
            "(4) Che đè nút '+' và 'OK' của popover 'Total guests' (z-50) ở /accommodation 360×800."
        ),
        "vi_notes": "Cùng 1 nguyên nhân gốc toàn cục trong chunk 3-q5yte2ewrs4.js (z-[9997]/z-[9998] > HeadlessUI Dialog z-[1400] & popover z-50). Hợp nhất từ 4 màn hình đã kiểm chứng (khác với OP-1756 chỉ trên form Login/Sign-Up).",
    }


def refine_a4_05(item: dict[str, Any]) -> dict[str, Any]:
    out = dict(item)
    out["title"] = "[Accommodation - Partner Network Coverage Drawer] Drawer Exposes Internal \"Mock snapshot · not connected to production\" Copy on Live Snapshot & Shows \"No matching places for this search.\" on Empty Search Input"
    out["type"] = "UI/UX (FE)"
    out["severity"] = "S3 – Moderate"
    out["sheet_severity"] = "MEDIUM"
    out["priority_label"] = "P2"
    out["actual_result"] = (
        "1) Across all tested locales (en-US, vi-VN, ko-KR, th-TH, en-SG), even though GET /api/traveler/partner-network-coverage returns a live backend snapshot (`snapshot: \"live-2026-11-25T04:44:22.597Z\"`), the drawer renders hardcoded internal engineering/mock copy directly to end users: "
        "body copy states \"Global, country, and city totals come from the same mock snapshot. The list only shows places with at least one valid property.\" and the footer renders \"Source: Mock snapshot live-2026-11-25T04:44:22.597Z · not connected to production\" "
        "(localized into vi-VN: \"Nguồn: Mock snapshot ... · Không kết nối production\" and th-TH: \"แหล่งที่มา: สแนปช็อตจำลอง ... · ยังไม่เชื่อมต่อระบบจริง\").\n"
        "2) When `countries: []` (0 public non-test properties on Staging), the drawer immediately displays the search-empty message \"No matching places for this search.\" (\"Không tìm thấy địa điểm phù hợp với từ khóa.\") even though the search input is completely empty (`query === \"\"`)."
    )
    out["expected_result"] = (
        "1) User-facing Partner Network Coverage copy must NEVER expose internal development disclaimers such as \"Mock snapshot\" or \"not connected to production\" across any locale when reading live coverage data.\n"
        "2) When the country list is empty and the search input is blank (`query === \"\"`), the drawer must display a proper empty-catalog state rather than falsely claiming \"No matching places for this search.\""
    )
    out["classification"] = "Confirmed Bug — Internal developer \"Mock snapshot / not connected to production\" copy leaked in user-facing UI & wrong empty-state copy on blank search"
    out["vi_summary"] = "[Lưu trú - Mạng lưới đối tác] Drawer 'Accommodation network' lộ chuỗi nội bộ \"Mock snapshot · Không kết nối production\" trên dữ liệu live và báo sai \"Không tìm thấy... với từ khóa\" khi ô tìm kiếm đang rỗng"
    out["vi_expected"] = "Giao diện người dùng tuyệt đối không hiển thị ghi chú nội bộ \"Mock snapshot / Không kết nối production\"; khi danh sách trống và ô tìm kiếm rỗng, cần hiển thị trạng thái chưa có cơ sở công khai thay vì báo sai không tìm thấy theo từ khóa."
    out["vi_actual"] = "Dù API trả về snapshot live (`live-2026-11-25T...`), drawer vẫn chèn thẳng timestamp live vào dòng chữ nội bộ 'Mock snapshot ... · not connected to production' (vi-VN: 'Nguồn: Mock snapshot ... · Không kết nối production') trên cả 5 ngôn ngữ, đồng thời báo 'Không tìm thấy địa điểm phù hợp với từ khóa.' dù người dùng chưa nhập từ khóa nào."
    return out


def main() -> None:
    cand = load_all_candidates()
    print(f"Loaded {len(cand)} raw candidates across 5 agents.")

    # Ordered list of 27 deduplicated, high-signal bugs (BUG-086 .. BUG-112):
    # Priority order: CRITICAL (P0) -> HIGH (P1) grouped by domain -> MEDIUM (P2) grouped by domain
    ordered: list[dict[str, Any]] = [
        # --- CRITICAL (P0) ---
        cand["A2-01"],
        # --- HIGH (P1) ---
        cand["A2-02"],
        cand["A2-03"],
        cand["A1-01"],
        cand["A1-02"],
        cand["A1-03"],
        cand["A3-01"],
        cand["A3-02"],
        cand["A3-03"],
        cand["A3-04"],
        cand["A3-05"],
        cand["A4-01"],
        cand["A4-02"],
        cand["A5-01"],
        build_consolidated_fab_bug(cand["A5-02"], cand["A2-05"], cand["A4-03"]),
        cand["A5-03"],
        cand["A5-04"],
        # --- MEDIUM (P2) ---
        cand["A2-04"],
        cand["A2-06"],
        cand["A1-04"],
        cand["A1-06"],
        cand["A3-06"],
        cand["A4-04"],
        refine_a4_05(cand["A4-05"]),
        cand["A4-06"],
        cand["A5-05"],
        cand["A5-06"],
    ]

    consolidated: list[dict[str, Any]] = []
    start_num = 86

    for idx, raw in enumerate(ordered):
        bug_num = start_num + idx
        bug_id = f"BUG-{bug_num:03d}"
        bug_slug = f"bug{bug_num:03d}"

        # Copy & PII-scrub attachments
        new_attachments: list[str] = []
        for a_idx, src_str in enumerate(raw["attachments"]):
            src_p = pathlib.Path(src_str)
            assert src_p.exists(), f"Missing attachment: {src_p}"
            letter = chr(ord("a") + a_idx)
            # Clean short stem from original filename
            orig_stem = src_p.stem
            # strip leading A1-01_ etc.
            parts = orig_stem.split("_", 1)
            tail = parts[1] if len(parts) == 2 and parts[0].startswith(("A1-", "A2-", "A3-", "A4-", "A5-")) else orig_stem
            dst_name = f"{bug_slug}{letter}_{tail}.png"
            dst_p = SHOTS / dst_name
            copy_and_scrub(src_p, dst_p)
            new_attachments.append(str(dst_p))

        title = scrub_text(raw["title"]).strip()
        assert len(title) <= 255, f"{bug_id} title too long ({len(title)}): {title}"

        # Build Jira payload matching jira_bug_reporter.py schema
        evidence_clean = {
            k: (clean_ref_url(v) if k == "reference_url" else scrub_text(str(v)).strip())
            for k, v in raw["evidence"].items()
        }
        jira_payload = {
            "title": title,
            "environment": scrub_text(raw["environment"]).strip(),
            "test_account": scrub_text(raw["test_account"]).strip(),
            "steps_to_reproduce": [clean_step(s) for s in raw["steps_to_reproduce"]],
            "actual_result": scrub_text(raw["actual_result"]).strip(),
            "expected_result": scrub_text(raw["expected_result"]).strip(),
            "evidence": evidence_clean,
            "classification": scrub_text(raw["classification"]).strip(),
            "severity": raw["severity"],
            "priority_label": raw["priority_label"],
            "reproducibility": scrub_text(raw["reproducibility"]).strip(),
            "attachments": new_attachments,
        }

        payload_path = PAYLOADS / f"{bug_id}.json"
        payload_path.write_text(json.dumps(jira_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        consolidated.append({
            "seq_id": bug_num,
            "bug_id": bug_id,
            "source_local_id": raw["local_id"],
            "payload_path": str(payload_path),
            "title": title,
            "area": raw["area"],
            "type": raw["type"],
            "severity": raw["severity"],
            "sheet_severity": raw["sheet_severity"],
            "priority_label": raw["priority_label"],
            "environment": jira_payload["environment"],
            "attachments": new_attachments,
            "vi_summary": scrub_text(raw["vi_summary"]).strip(),
            "vi_steps": scrub_text(raw["vi_steps"]).strip(),
            "vi_expected": scrub_text(raw["vi_expected"]).strip(),
            "vi_actual": scrub_text(raw["vi_actual"]).strip(),
            "vi_notes": scrub_text(raw["vi_notes"]).strip(),
        })

    out_master = BASE / "consolidated_bugs.json"
    out_master.write_text(json.dumps(consolidated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Successfully packaged {len(consolidated)} bugs ({consolidated[0]['bug_id']}..{consolidated[-1]['bug_id']}) and {sum(len(c['attachments']) for c in consolidated)} screenshots!")
    counts = {}
    for c in consolidated:
        counts[c["sheet_severity"]] = counts.get(c["sheet_severity"], 0) + 1
    print("Severity breakdown:", counts)


if __name__ == "__main__":
    main()
