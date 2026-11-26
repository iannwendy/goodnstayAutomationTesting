#!/usr/bin/env python3
"""OpenXML-safe updater for sheet 'BUG_TRACKER' in gns_Bug_Report_Tracking.xlsx.

Follows AGENTS.md §4 strictly:
- Uses lxml.etree (standalone=True), NEVER xml.etree.ElementTree
- Preserves all worksheet namespace declarations & unprefixed default xmlns on .rels
- Clones exact cell styles from canonical formatted rows (Row 73 / 60 / 67)
- Validates all dropdown columns against BUG_TRACKER DataValidations
- Computes sequential ID (Col A) from last populated numeric ID + 1 (not row - 10)
- Deduplicates in-place by Bug ID (Col B) or Jira URL (Col N)
- Binds clickable external hyperlinks on Col L (Evidence Link) and Col N (Jira Bug)
- Recomputes exact sst/@count and sst/@uniqueCount across all sheets
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import pathlib
import sys
from typing import Any
import zipfile
from lxml import etree

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
HYPERLINK_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
NS = {"main": MAIN_NS, "r": REL_NS, "pkg": PKG_REL_NS}

ALLOWED_TYPES = frozenset({
    "FUNCTIONAL",
    "End to End",
    "UI/UX (FE)",
    "I18N",
    "RESPONSIVE",
    "CONTENT",
    "PERFORMANCE",
    "DATA INVALID",
    "OTHER",
})
ALLOWED_SEVERITIES = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW"})
ALLOWED_ENVIRONMENTS = frozenset({"STAG", "DEV", "PROD"})
ALLOWED_QA_STAGES = frozenset({
    "NEW", "NEEDS REVIEW", "CONFIRMED", "IN PROGRESS", "READY FOR RETEST",
    "REOPENED", "CLOSED", "NOT A BUG", "DUPLICATE", "OBSERVATION",
})
ALLOWED_RETEST = frozenset({"NOT RUN", "PASS", "FAIL", "BLOCKED", "NOT VERIFIED", "N/A"})
COLUMNS_ORDER = tuple("ABCDEFGHIJKLMNOPQRST")
AFTER_HYPERLINKS_TAGS = frozenset({
    "printOptions", "pageMargins", "pageSetup", "headerFooter", "rowBreaks",
    "colBreaks", "customProperties", "cellWatches", "ignoredErrors", "smartTags",
    "drawing", "drawingHF", "picture", "oleObjects", "controls", "webPublishItems",
    "tableParts", "extLst",
})


def to_excel_serial(d_str: str) -> int:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            d = datetime.strptime(d_str.strip(), fmt).date()
            return (d - date(1899, 12, 30)).days
        except ValueError:
            continue
    raise ValueError(f"Unsupported date: {d_str!r}")


def resolve_sheet_paths(zf: zipfile.ZipFile, sheet_name: str) -> tuple[str, str]:
    wb = etree.fromstring(zf.read("xl/workbook.xml"))
    rels = etree.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rmap = {rel.get("Id"): rel.get("Target", "") for rel in rels}
    for sh in wb.findall(".//main:sheet", NS):
        if sh.get("name") == sheet_name:
            rid = sh.get(f"{{{REL_NS}}}id")
            target = rmap.get(rid, "")
            ws_path = target if target.startswith("xl/") else f"xl/{target.lstrip('/')}"
            ws_file = pathlib.PurePosixPath(ws_path)
            rels_path = str(ws_file.parent / "_rels" / f"{ws_file.name}.rels")
            return ws_path, rels_path
    raise ValueError(f"Worksheet {sheet_name!r} not found.")


def upsert_bug_tracker(
    input_xlsx: pathlib.Path,
    output_xlsx: pathlib.Path,
    rows_to_upsert: list[dict[str, Any]],
    sheet_name: str = "BUG_TRACKER",
) -> dict[str, Any]:
    for row in rows_to_upsert:
        assert row["type"] in ALLOWED_TYPES, f"Bad type: {row['type']}"
        assert row["severity"] in ALLOWED_SEVERITIES, f"Bad severity: {row['severity']}"
        assert row["environment"] in ALLOWED_ENVIRONMENTS, f"Bad env: {row['environment']}"
        assert row["qa_stage"] in ALLOWED_QA_STAGES, f"Bad stage: {row['qa_stage']}"
        assert row["retest_result"] in ALLOWED_RETEST, f"Bad retest: {row['retest_result']}"
        assert row["jira_url"].startswith("https://"), f"Bad jira_url: {row['jira_url']}"

    with zipfile.ZipFile(input_xlsx, "r") as zin:
        entries = {name: zin.read(name) for name in zin.namelist()}
        ws_path, rels_path = resolve_sheet_paths(zin, sheet_name)

    parser = etree.XMLParser(remove_blank_text=False)
    ws_root = etree.fromstring(entries[ws_path], parser=parser)
    sst_root = etree.fromstring(entries["xl/sharedStrings.xml"], parser=parser)
    rels_root = (
        etree.fromstring(entries[rels_path], parser=parser)
        if rels_path in entries
        else etree.Element(f"{{{PKG_REL_NS}}}Relationships", nsmap={None: PKG_REL_NS})
    )

    sst_list: list[str] = []
    sst_index: dict[str, int] = {}
    for idx, si in enumerate(sst_root.findall("main:si", NS)):
        txt = "".join(t.text or "" for t in si.findall(".//main:t", NS))
        sst_list.append(txt)
        if txt not in sst_index:
            sst_index[txt] = idx

    def intern_str(s: str) -> int:
        if s in sst_index:
            return sst_index[s]
        new_idx = len(sst_list)
        sst_list.append(s)
        sst_index[s] = new_idx
        si_el = etree.SubElement(sst_root, f"{{{MAIN_NS}}}si")
        t_el = etree.SubElement(si_el, f"{{{MAIN_NS}}}t")
        if s.startswith(" ") or s.endswith(" ") or "\n" in s or "\t" in s:
            t_el.set(XML_SPACE, "preserve")
        t_el.text = s
        return new_idx

    def read_cell_text(c_el: etree._Element | None) -> str:
        if c_el is None:
            return ""
        v_el = c_el.find("main:v", NS)
        if v_el is None or v_el.text is None:
            return ""
        if c_el.get("t") == "s":
            i = int(v_el.text)
            return sst_list[i] if 0 <= i < len(sst_list) else ""
        return v_el.text

    sheet_data = ws_root.find("main:sheetData", NS)
    assert sheet_data is not None

    template_styles: dict[str, str] = {}
    for cand_r in (73, 60, 67, 11):
        tr = sheet_data.find(f"main:row[@r='{cand_r}']", NS)
        if tr is not None:
            for c in tr.findall("main:c", NS):
                col = "".join(ch for ch in c.get("r", "") if ch.isalpha())
                if col in COLUMNS_ORDER and c.get("s"):
                    template_styles[col] = c.get("s", "")
            if len(template_styles) == 20:
                break

    row_elements: dict[int, etree._Element] = {}
    existing_by_bug_id: dict[str, int] = {}
    existing_by_jira_url: dict[str, int] = {}
    max_populated_row = 10
    max_seq_id = 0

    for r_el in sheet_data.findall("main:row", NS):
        r_num = int(r_el.get("r", "0"))
        row_elements[r_num] = r_el
        if r_num >= 11:
            a_txt = read_cell_text(r_el.find(f"main:c[@r='A{r_num}']", NS)).strip()
            b_txt = read_cell_text(r_el.find(f"main:c[@r='B{r_num}']", NS)).strip()
            c_txt = read_cell_text(r_el.find(f"main:c[@r='C{r_num}']", NS)).strip()
            n_txt = read_cell_text(r_el.find(f"main:c[@r='N{r_num}']", NS)).strip()
            if b_txt or c_txt or n_txt:
                max_populated_row = max(max_populated_row, r_num)
                if a_txt:
                    try:
                        max_seq_id = max(max_seq_id, int(float(a_txt)))
                    except ValueError:
                        pass
            if b_txt:
                existing_by_bug_id[b_txt] = r_num
            if n_txt:
                existing_by_jira_url[n_txt] = r_num

    hyperlinks_el = ws_root.find("main:hyperlinks", NS)
    if hyperlinks_el is None:
        hyperlinks_el = etree.Element(f"{{{MAIN_NS}}}hyperlinks")
        insert_pos = len(ws_root)
        for idx, child in enumerate(ws_root):
            if etree.QName(child).localname in AFTER_HYPERLINKS_TAGS:
                insert_pos = idx
                break
        ws_root.insert(insert_pos, hyperlinks_el)

    existing_hl = {hl.get("ref", ""): hl for hl in hyperlinks_el.findall("main:hyperlink", NS) if hl.get("ref")}
    used_rids = {rel.get("Id", "") for rel in rels_root}

    def next_rid() -> str:
        n = 1
        while f"rId{n}" in used_rids:
            n += 1
        rid = f"rId{n}"
        used_rids.add(rid)
        return rid

    def set_hyperlink(cell_ref: str, url: str) -> None:
        if not url:
            return
        if cell_ref in existing_hl:
            rid = existing_hl[cell_ref].get(f"{{{REL_NS}}}id", "")
            for rel in rels_root:
                if rel.get("Id") == rid:
                    rel.set("Target", url)
                    rel.set("TargetMode", "External")
                    return
        rid = next_rid()
        rel_el = etree.SubElement(rels_root, f"{{{PKG_REL_NS}}}Relationship")
        rel_el.set("Id", rid)
        rel_el.set("Type", HYPERLINK_REL_TYPE)
        rel_el.set("Target", url)
        rel_el.set("TargetMode", "External")
        hl_el = etree.SubElement(hyperlinks_el, f"{{{MAIN_NS}}}hyperlink")
        hl_el.set("ref", cell_ref)
        hl_el.set(f"{{{REL_NS}}}id", rid)
        existing_hl[cell_ref] = hl_el

    def ensure_row(r_num: int) -> etree._Element:
        if r_num in row_elements:
            r_el = row_elements[r_num]
            r_el.set("ht", "276.75")
            r_el.set("customHeight", "1")
            return r_el
        r_el = etree.Element(f"{{{MAIN_NS}}}row", r=str(r_num), ht="276.75", customHeight="1")
        placed = False
        for idx, existing in enumerate(sheet_data):
            if int(existing.get("r", "0")) > r_num:
                sheet_data.insert(idx, r_el)
                placed = True
                break
        if not placed:
            sheet_data.append(r_el)
        row_elements[r_num] = r_el
        return r_el

    def set_cell(r_el: etree._Element, r_num: int, col: str, val: Any, is_num: bool = False) -> None:
        ref = f"{col}{r_num}"
        c_el = r_el.find(f"main:c[@r='{ref}']", NS)
        if c_el is None:
            c_el = etree.Element(f"{{{MAIN_NS}}}c", r=ref)
            pos = COLUMNS_ORDER.index(col)
            placed = False
            for idx, ex in enumerate(r_el):
                ex_col = "".join(ch for ch in ex.get("r", "") if ch.isalpha())
                if ex_col in COLUMNS_ORDER and COLUMNS_ORDER.index(ex_col) > pos:
                    r_el.insert(idx, c_el)
                    placed = True
                    break
            if not placed:
                r_el.append(c_el)

        style_id = template_styles.get(col) or c_el.get("s") or "204"
        c_el.attrib.clear()
        c_el.set("r", ref)
        c_el.set("s", style_id)
        for ch in list(c_el):
            c_el.remove(ch)

        if val is None or (isinstance(val, str) and val == ""):
            return
        v_el = etree.SubElement(c_el, f"{{{MAIN_NS}}}v")
        if is_num:
            v_el.text = str(val)
        else:
            c_el.set("t", "s")
            v_el.text = str(intern_str(str(val)))

    inserted = 0
    updated = 0
    written_rows: list[dict[str, Any]] = []

    for item in rows_to_upsert:
        jira_url = item["jira_url"].strip()
        target_row = existing_by_jira_url.get(jira_url) or existing_by_bug_id.get(item.get("bug_id", "").strip())
        if target_row is None:
            max_populated_row += 1
            max_seq_id += 1
            target_row = max_populated_row
            seq_id = max_seq_id
            bug_id = item.get("bug_id", "").strip() or f"BUG-{seq_id:03d}"
            existing_by_bug_id[bug_id] = target_row
            existing_by_jira_url[jira_url] = target_row
            inserted += 1
        else:
            r_exist = row_elements[target_row]
            a_exist = read_cell_text(r_exist.find(f"main:c[@r='A{target_row}']", NS)).strip()
            seq_id = int(float(a_exist)) if a_exist else int(item.get("seq_id") or 0)
            bug_id = read_cell_text(r_exist.find(f"main:c[@r='B{target_row}']", NS)).strip() or item["bug_id"]
            updated += 1

        r_el = ensure_row(target_row)
        serial_date = to_excel_serial(item["reported_on"])
        ev_url = item.get("evidence_url", "").strip()
        ev_label = item.get("evidence_label", "").strip() or ev_url

        set_cell(r_el, target_row, "A", seq_id, is_num=True)
        set_cell(r_el, target_row, "B", bug_id)
        set_cell(r_el, target_row, "C", item["summary"].strip())
        set_cell(r_el, target_row, "D", item["area"].strip())
        set_cell(r_el, target_row, "E", item["type"].strip())
        set_cell(r_el, target_row, "F", item["severity"].strip())
        set_cell(r_el, target_row, "G", item["steps"].strip())
        set_cell(r_el, target_row, "H", item["expected"].strip())
        set_cell(r_el, target_row, "I", item["actual"].strip())
        set_cell(r_el, target_row, "J", item["environment"].strip())
        set_cell(r_el, target_row, "K", item["device_locale"].strip())
        set_cell(r_el, target_row, "L", ev_label)
        set_cell(r_el, target_row, "M", item["qa_stage"].strip())
        set_cell(r_el, target_row, "N", jira_url)
        set_cell(r_el, target_row, "O", item.get("reported_by", "Nguyen Bao Minh").strip())
        set_cell(r_el, target_row, "P", serial_date, is_num=True)
        set_cell(r_el, target_row, "Q", "")
        set_cell(r_el, target_row, "R", item["retest_result"].strip())
        set_cell(r_el, target_row, "S", "")
        set_cell(r_el, target_row, "T", item["notes"].strip())

        if ev_url:
            set_hyperlink(f"L{target_row}", ev_url)
        set_hyperlink(f"N{target_row}", jira_url)

        written_rows.append({"row": target_row, "id": seq_id, "bug_id": bug_id, "jira_url": jira_url})

    total_s_refs = 0
    for name, raw in entries.items():
        if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
            root = ws_root if name == ws_path else etree.fromstring(raw, parser=parser)
            total_s_refs += len(root.findall(".//main:c[@t='s']", NS))
    sst_root.set("count", str(total_s_refs))
    sst_root.set("uniqueCount", str(len(sst_list)))

    entries[ws_path] = etree.tostring(ws_root, encoding="UTF-8", xml_declaration=True, standalone=True)
    entries[rels_path] = etree.tostring(rels_root, encoding="UTF-8", xml_declaration=True, standalone=True)
    entries["xl/sharedStrings.xml"] = etree.tostring(sst_root, encoding="UTF-8", xml_declaration=True, standalone=True)

    output_xlsx.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_xlsx, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name, content in entries.items():
            zout.writestr(name, content)

    with zipfile.ZipFile(output_xlsx, "r") as zchk:
        bad = zchk.testzip()
        assert bad is None, f"Corrupt ZIP entry: {bad}"
        for xname in (ws_path, rels_path, "xl/sharedStrings.xml"):
            etree.fromstring(zchk.read(xname))

    return {
        "sheet_name": sheet_name,
        "inserted": inserted,
        "updated": updated,
        "first_row": written_rows[0]["row"] if written_rows else None,
        "last_row": written_rows[-1]["row"] if written_rows else None,
        "bug_range": f"{written_rows[0]['bug_id']}..{written_rows[-1]['bug_id']}" if written_rows else "",
        "sst_count": total_s_refs,
        "sst_uniqueCount": len(sst_list),
        "output_xlsx": str(output_xlsx),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="OpenXML-safe updater for sheet 'BUG_TRACKER' in gns_Bug_Report_Tracking.xlsx.")
    ap.add_argument("--xlsx", required=True, help="Downloaded gns_Bug_Report_Tracking.xlsx path.")
    ap.add_argument("--output", required=True, help="Output updated .xlsx path (keep inside ~/.workspace-mcp/attachments/).")
    ap.add_argument("--consolidated", default="", help="Path to consolidated_bugs.json (used with --uploaded).")
    ap.add_argument("--uploaded", default="", help="Path to uploaded_jira_tickets.json (used with --consolidated).")
    ap.add_argument("--rows", default="", help="Alternative: direct JSON array of pre-formatted BUG_TRACKER row objects.")
    ap.add_argument("--sheet", default="BUG_TRACKER", help="Target worksheet name (default: BUG_TRACKER).")
    ap.add_argument("--reported-by", default="Nguyen Bao Minh", help="Reporter name for Col O.")
    ap.add_argument("--reported-on", default=date.today().isoformat(), help="Report date YYYY-MM-DD for Col P.")
    ap.add_argument("--environment", default="STAG", help="Environment dropdown value for Col J (default: STAG).")
    ap.add_argument("--qa-stage", default="NEW", help="QA Stage dropdown value for Col M (default: NEW).")
    ap.add_argument("--retest-result", default="NOT RUN", help="Retest Result dropdown value for Col R (default: NOT RUN).")
    args = ap.parse_args()

    if args.rows:
        rows = json.loads(pathlib.Path(args.rows).read_text(encoding="utf-8"))
    elif args.consolidated and args.uploaded:
        cons = json.loads(pathlib.Path(args.consolidated).read_text(encoding="utf-8"))
        up = json.loads(pathlib.Path(args.uploaded).read_text(encoding="utf-8"))
        up_by_bug = {t["bug_id"]: t for t in up["tickets"]}
        rows = []
        for c in cons:
            t = up_by_bug[c["bug_id"]]
            att_names = " & ".join(t.get("attachment_names", [])[:2])
            if len(t.get("attachment_names", [])) > 2:
                att_names += f" (+{len(t['attachment_names']) - 2} PNGs)"
            ev_label = f"{att_names} (Jira {t['issue_key']})" if att_names else f"Jira {t['issue_key']}"
            ev_url = (t.get("attachment_urls") or [t["issue_url"]])[0]
            rows.append({
                "seq_id": c.get("seq_id", 0),
                "bug_id": c["bug_id"],
                "summary": c["vi_summary"],
                "area": c["area"],
                "type": c["type"],
                "severity": c["sheet_severity"],
                "steps": c["vi_steps"],
                "expected": c["vi_expected"],
                "actual": c["vi_actual"],
                "environment": args.environment,
                "device_locale": c["environment"].replace("Staging (STAG) · ", ""),
                "evidence_label": ev_label,
                "evidence_url": ev_url,
                "qa_stage": args.qa_stage,
                "jira_url": t["issue_url"],
                "reported_by": args.reported_by,
                "reported_on": args.reported_on,
                "retest_result": args.retest_result,
                "notes": c["vi_notes"],
            })
    else:
        ap.error("Provide either --rows <rows.json> OR both --consolidated and --uploaded.")

    res = upsert_bug_tracker(
        input_xlsx=pathlib.Path(args.xlsx),
        output_xlsx=pathlib.Path(args.output),
        rows_to_upsert=rows,
        sheet_name=args.sheet,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
