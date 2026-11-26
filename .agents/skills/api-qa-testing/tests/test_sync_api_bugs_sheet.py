#!/usr/bin/env python3
"""Unit tests for API_BUGS Google Drive Excel tracker sync (sync_api_bugs_sheet.py)."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import zipfile
from lxml import etree

SCRIPT_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import sync_api_bugs_sheet as sync_sheet  # noqa: E402

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"main": MAIN_NS, "r": REL_NS}


def _build_minimal_tracking_xlsx(target_path: pathlib.Path) -> None:
    """Create a minimal valid OpenXML workbook mirroring gns_Bug_Report_Tracking.xlsx (API_BUGS)."""
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}">'
        '<sheets>'
        '<sheet name="PAYMENT_BUGS" sheetId="3" state="visible" r:id="rId1"/>'
        '<sheet name="API_BUGS" sheetId="4" state="visible" r:id="rId2"/>'
        '</sheets>'
        '</workbook>'
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{PKG_REL_NS}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet4.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        '</Relationships>'
    )
    sst_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="{MAIN_NS}" count="2" uniqueCount="2">'
        '<si><t>ID</t></si>'
        '<si><t>Bug ID / Jira ID</t></si>'
        '</sst>'
    )
    sheet3_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{MAIN_NS}" xmlns:r="{REL_NS}">'
        '<sheetData><row r="10"><c r="A10" t="s"><v>0</v></c></row></sheetData>'
        '</worksheet>'
    )
    # Mirror API_BUGS (sheet4.xml): row 10 headers, empty styled row 11..15, dataValidations, printOptions, tableParts
    row11_cells = "".join([
        '<c r="A11" s="24"/><c r="B11" s="26"/><c r="C11" s="27"/><c r="D11" s="27"/>',
        '<c r="E11" s="29"/><c r="F11" s="31"/><c r="G11" s="27"/><c r="H11" s="27"/>',
        '<c r="I11" s="27"/><c r="J11" s="32"/><c r="K11" s="27"/><c r="L11" s="98"/>',
        '<c r="M11" s="43"/><c r="N11" s="98"/><c r="O11" s="27"/><c r="P11" s="38"/>',
        '<c r="Q11" s="39"/><c r="R11" s="47"/><c r="S11" s="42"/><c r="T11" s="44"/>',
    ])
    sheet4_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{MAIN_NS}" xmlns:r="{REL_NS}" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:x14ac="http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac">'
        '<sheetData>'
        '<row r="10"><c r="A10" s="19" t="s"><v>0</v></c><c r="B10" s="20" t="s"><v>1</v></c></row>'
        f'<row r="11" ht="273.75" customHeight="1">{row11_cells}</row>'
        '<row r="12" ht="273.75" customHeight="1"><c r="A12" s="24"/></row>'
        '</sheetData>'
        '<dataValidations count="1">'
        '<dataValidation type="list" sqref="J11:J59"><formula1>"STAG,QA,DEV,PROD (APPROVED)"</formula1></dataValidation>'
        '</dataValidations>'
        '<printOptions/>'
        '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>'
        '<tableParts count="1"><tablePart r:id="rId4"/></tableParts>'
        '</worksheet>'
    )
    sheet4_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{PKG_REL_NS}">'
        '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/table" Target="../tables/table8.xml"/>'
        '</Relationships>'
    )
    table8_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<table xmlns="{MAIN_NS}" ref="A10:T59" displayName="Table1_4" name="Table1_4" id="2">'
        '<autoFilter ref="$A$10:$T$59"/>'
        '</table>'
    )
    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/sharedStrings.xml", sst_xml)
        zf.writestr("xl/worksheets/sheet3.xml", sheet3_xml)
        zf.writestr("xl/worksheets/sheet4.xml", sheet4_xml)
        zf.writestr("xl/worksheets/_rels/sheet4.xml.rels", sheet4_rels_xml)
        zf.writestr("xl/tables/table8.xml", table8_xml)


class TestSyncApiBugsSheet(unittest.TestCase):
    def test_upserts_rows_hyperlinks_sst_and_idempotent_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = pathlib.Path(tmp)
            src_xlsx = tmp_dir / "tracking.xlsx"
            out_xlsx = tmp_dir / "tracking_out.xlsx"
            _build_minimal_tracking_xlsx(src_xlsx)

            bug_rows = [
                {
                    "bug_id": "BUG-API-01",
                    "summary": "[Traveler API - Sample] API trả thiếu errorCode trên STAG",
                    "area": "Traveler API – Request Validation",
                    "type": "DATA INVALID",
                    "severity": "HIGH",
                    "steps": "1. Đăng nhập tại https://web.stag.goodnstay.com/en-US\n2. Gửi request kiểm thử\n3. Kiểm tra response và DB",
                    "expected": "API trả HTTP 400 kèm errorCode chuẩn trong OpenAPI.",
                    "actual": "API trả HTTP 400 không có errorCode.",
                    "environment": "STAG",
                    "device_locale": "Staging API & Chrome · 1440×900 · en-US",
                    "evidence_label": "bug_api_01.png (OP-1901)",
                    "evidence_url": "https://optibide-org.atlassian.net/rest/api/3/attachment/content/99001",
                    "qa_stage": "NEW",
                    "jira_url": "https://optibide-org.atlassian.net/browse/OP-1901",
                    "reported_by": "Nguyen Bao Minh",
                    "reported_on": "2026-11-19",
                    "retest_result": "NOT RUN",
                    "notes": "Tái hiện 100% trên STAG (https://web.stag.goodnstay.com/).",
                }
            ]

            res1 = sync_sheet.upsert_api_bugs(src_xlsx, out_xlsx, bug_rows)
            self.assertEqual(res1["inserted"], 1)
            self.assertEqual(res1["updated"], 0)

            # Second run: update BUG-API-01 in place + insert BUG-API-02 without duplicating BUG-API-01
            bug_rows[0]["qa_stage"] = "CONFIRMED"
            bug_rows.append({
                **bug_rows[0],
                "bug_id": "BUG-API-02",
                "summary": "[Traveler API - Sample 2] Lỗi phân quyền readback",
                "evidence_label": "bug_api_02.png (OP-1902)",
                "evidence_url": "https://optibide-org.atlassian.net/rest/api/3/attachment/content/99002",
                "jira_url": "https://optibide-org.atlassian.net/browse/OP-1902",
            })
            out_xlsx2 = tmp_dir / "tracking_out2.xlsx"
            res2 = sync_sheet.upsert_api_bugs(out_xlsx, out_xlsx2, bug_rows)
            self.assertEqual(res2["inserted"], 1)
            self.assertEqual(res2["updated"], 1)

            with zipfile.ZipFile(out_xlsx2, "r") as zf:
                self.assertIsNone(zf.testzip())
                sst_raw = zf.read("xl/sharedStrings.xml")
                sst_root = etree.fromstring(sst_raw)
                strings = ["".join(t.text or "" for t in si.findall(".//main:t", NS)) for si in sst_root.findall("main:si", NS)]
                self.assertEqual(int(sst_root.get("uniqueCount")), len(strings))

                ws4 = etree.fromstring(zf.read("xl/worksheets/sheet4.xml"))
                tag_order = [etree.QName(ch).localname for ch in ws4]
                # OpenXML CT_Worksheet requirement: hyperlinks MUST precede printOptions!
                self.assertLess(tag_order.index("hyperlinks"), tag_order.index("printOptions"))

                # Verify unprefixed default xmlns in sheet4.xml.rels (never ns0:Relationships)
                rels_text = zf.read("xl/worksheets/_rels/sheet4.xml.rels").decode("utf-8")
                self.assertNotIn("ns0:", rels_text)
                self.assertIn("https://optibide-org.atlassian.net/browse/OP-1901", rels_text)
                self.assertIn("https://optibide-org.atlassian.net/browse/OP-1902", rels_text)

                # Verify Row 11 updated in place (CONFIRMED) & Row 12 inserted (BUG-API-02)
                def cell_str(row_num: int, col: str) -> str:
                    c = ws4.find(f".//main:sheetData/main:row[@r='{row_num}']/main:c[@r='{col}{row_num}']", NS)
                    self.assertIsNotNone(c)
                    v = c.find("main:v", NS)
                    if c.get("t") == "s":
                        return strings[int(v.text)]
                    return v.text or ""

                self.assertEqual(cell_str(11, "A"), "1")
                self.assertEqual(cell_str(11, "B"), "BUG-API-01")
                self.assertEqual(cell_str(11, "M"), "CONFIRMED")
                self.assertEqual(cell_str(12, "A"), "2")
                self.assertEqual(cell_str(12, "B"), "BUG-API-02")

    def test_rejects_non_stag_environment_and_invalid_dropdowns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = pathlib.Path(tmp)
            src_xlsx = tmp_dir / "tracking.xlsx"
            _build_minimal_tracking_xlsx(src_xlsx)
            bad_row = {
                "bug_id": "BUG-API-99",
                "summary": "Prod leak",
                "area": "API",
                "type": "FUNCTIONAL",
                "severity": "HIGH",
                "steps": "1. Step",
                "expected": "Exp",
                "actual": "Act",
                "environment": "PROD (APPROVED)",
                "device_locale": "Chrome · en-US",
                "evidence_label": "ev.png",
                "evidence_url": "https://optibide-org.atlassian.net/rest/api/3/attachment/content/1",
                "qa_stage": "NEW",
                "jira_url": "https://optibide-org.atlassian.net/browse/OP-1999",
            }
            with self.assertRaisesRegex(ValueError, "STAG"):
                sync_sheet.upsert_api_bugs(src_xlsx, tmp_dir / "out.xlsx", [bad_row])


if __name__ == "__main__":
    unittest.main()
