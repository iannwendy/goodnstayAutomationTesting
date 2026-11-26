#!/usr/bin/env python3
"""OpenXML-safe updater for sheet 'API_BUGS' in gns_Bug_Report_Tracking.xlsx.

Enforces AGENTS.md §4 & §6:
- Uses lxml.etree (standalone=True) — NEVER xml.etree.ElementTree
- Preserves all worksheet namespace declarations (nsmap) & unprefixed default xmlns on .rels
- Recomputes exact sst/@count and sst/@uniqueCount in xl/sharedStrings.xml
- Validates dropdown columns against API_BUGS DataValidations (Environment MUST be 'STAG')
- Inserts <hyperlinks> strictly before <printOptions> per OpenXML CT_Worksheet schema
- Deduplicates rows in-place by Bug ID (Col B) or Jira URL (Col N)
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import pathlib
import re
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
ALLOWED_QA_STAGES = frozenset({
    "NEW",
    "NEEDS REVIEW",
    "CONFIRMED",
    "IN PROGRESS",
    "READY FOR RETEST",
    "REOPENED",
    "CLOSED",
    "NOT A BUG",
    "DUPLICATE",
    "OBSERVATION",
})
ALLOWED_RETEST_RESULTS = frozenset({"NOT RUN", "PASS", "FAIL", "BLOCKED", "NOT VERIFIED", "N/A"})

# Canonical cell styles cloned from API_BUGS / PAYMENT_BUGS Row 11
DEFAULT_COL_STYLES: dict[str, str] = {
    "A": "24",
    "B": "26",
    "C": "27",
    "D": "27",
    "E": "29",
    "F": "31",
    "G": "27",
    "H": "27",
    "I": "27",
    "J": "32",
    "K": "27",
    "L": "41",
    "M": "43",
    "N": "41",
    "O": "27",
    "P": "38",
    "Q": "39",
    "R": "47",
    "S": "42",
    "T": "44",
}
COLUMNS_ORDER: tuple[str, ...] = (
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
    "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
)

AFTER_HYPERLINKS_TAGS: frozenset[str] = frozenset({
    "printOptions",
    "pageMargins",
    "pageSetup",
    "headerFooter",
    "rowBreaks",
    "colBreaks",
    "customProperties",
    "cellWatches",
    "ignoredErrors",
    "smartTags",
    "drawing",
    "drawingHF",
    "picture",
    "oleObjects",
    "controls",
    "webPublishItems",
    "tableParts",
    "extLst",
})


def _to_excel_serial(val: str | int | float | None) -> int:
    if val is None or str(val).strip() == "":
        d = date.today()
    elif isinstance(val, (int, float)):
        return int(val)
    else:
        s = str(val).strip()
        if re.fullmatch(r"\d+(?:\.0)?", s):
            return int(float(s))
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                d = datetime.strptime(s, fmt).date()
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"Unsupported reported_on date format: {val!r} (use YYYY-MM-DD or DD/MM/YYYY)")
    return (d - date(1899, 12, 30)).days


def _validate_bug_row(row: dict[str, Any]) -> None:
    for req in ("bug_id", "summary", "area", "type", "severity", "steps", "expected", "actual", "jira_url"):
        if not str(row.get(req, "")).strip():
            raise ValueError(f"Missing required field {req!r} in bug row {row.get('bug_id')!r}.")

    env = str(row.get("environment", "STAG")).strip()
    if env != "STAG":
        raise ValueError(
            f"Invalid environment={env!r} for {row.get('bug_id')!r}: API testing on API_BUGS must strictly use 'STAG'."
        )
    btype = str(row.get("type", "")).strip()
    if btype not in ALLOWED_TYPES:
        raise ValueError(f"Invalid type={btype!r} (allowed: {sorted(ALLOWED_TYPES)}).")
    sev = str(row.get("severity", "")).strip()
    if sev not in ALLOWED_SEVERITIES:
        raise ValueError(f"Invalid severity={sev!r} (allowed: {sorted(ALLOWED_SEVERITIES)}).")
    stage = str(row.get("qa_stage", "NEW")).strip()
    if stage not in ALLOWED_QA_STAGES:
        raise ValueError(f"Invalid qa_stage={stage!r} (allowed: {sorted(ALLOWED_QA_STAGES)}).")
    retest = str(row.get("retest_result", "NOT RUN")).strip()
    if retest not in ALLOWED_RETEST_RESULTS:
        raise ValueError(f"Invalid retest_result={retest!r} (allowed: {sorted(ALLOWED_RETEST_RESULTS)}).")


def _resolve_sheet_paths(zf: zipfile.ZipFile, sheet_name: str) -> tuple[str, str]:
    wb = etree.fromstring(zf.read("xl/workbook.xml"))
    rels = etree.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.get("Id"): rel.get("Target", "") for rel in rels}
    for sh in wb.findall(".//main:sheet", NS):
        if sh.get("name") == sheet_name:
            rid = sh.get(f"{{{REL_NS}}}id")
            target = rel_map.get(rid, "")
            if not target:
                break
            ws_path = target if target.startswith("xl/") else f"xl/{target.lstrip('/')}"
            ws_file = pathlib.PurePosixPath(ws_path)
            rels_path = str(ws_file.parent / "_rels" / f"{ws_file.name}.rels")
            return ws_path, rels_path
    raise ValueError(f"Worksheet {sheet_name!r} not found in workbook.")


def upsert_api_bugs(
    input_xlsx: pathlib.Path,
    output_xlsx: pathlib.Path,
    bug_rows: list[dict[str, Any]],
    sheet_name: str = "API_BUGS",
) -> dict[str, Any]:
    """Upsert API bug rows into sheet_name while preserving 100% OpenXML integrity."""
    for row in bug_rows:
        _validate_bug_row(row)

    with zipfile.ZipFile(input_xlsx, "r") as zin:
        entries = {name: zin.read(name) for name in zin.namelist()}
        ws_path, rels_path = _resolve_sheet_paths(zin, sheet_name)

    parser = etree.XMLParser(remove_blank_text=False)
    ws_root = etree.fromstring(entries[ws_path], parser=parser)
    sst_root = etree.fromstring(entries["xl/sharedStrings.xml"], parser=parser)

    if rels_path in entries:
        rels_root = etree.fromstring(entries[rels_path], parser=parser)
    else:
        rels_root = etree.Element(f"{{{PKG_REL_NS}}}Relationships", nsmap={None: PKG_REL_NS})

    # Build sharedStrings index
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

    def read_cell_text(cell_el: etree._Element | None) -> str:
        if cell_el is None:
            return ""
        v_el = cell_el.find("main:v", NS)
        if v_el is None or v_el.text is None:
            return ""
        if cell_el.get("t") == "s":
            s_idx = int(v_el.text)
            return sst_list[s_idx] if 0 <= s_idx < len(sst_list) else ""
        return v_el.text

    sheet_data = ws_root.find("main:sheetData", NS)
    if sheet_data is None:
        raise ValueError(f"Missing <sheetData> in {ws_path}.")

    # Map existing rows >= 11 by row number and scan existing Bug IDs / Jira URLs
    row_elements: dict[int, etree._Element] = {}
    existing_by_bug_id: dict[str, int] = {}
    existing_by_jira_url: dict[str, int] = {}
    max_populated_row = 10

    for r_el in sheet_data.findall("main:row", NS):
        r_num = int(r_el.get("r", "0"))
        row_elements[r_num] = r_el
        if r_num >= 11:
            b_txt = read_cell_text(r_el.find(f"main:c[@r='B{r_num}']", NS)).strip()
            n_txt = read_cell_text(r_el.find(f"main:c[@r='N{r_num}']", NS)).strip()
            c_txt = read_cell_text(r_el.find(f"main:c[@r='C{r_num}']", NS)).strip()
            if b_txt or c_txt or n_txt:
                max_populated_row = max(max_populated_row, r_num)
            if b_txt:
                existing_by_bug_id[b_txt] = r_num
            if n_txt:
                existing_by_jira_url[n_txt] = r_num

    # Prepare <hyperlinks> container in strict OpenXML CT_Worksheet order (before printOptions/pageMargins/...)
    hyperlinks_el = ws_root.find("main:hyperlinks", NS)
    if hyperlinks_el is None:
        hyperlinks_el = etree.Element(f"{{{MAIN_NS}}}hyperlinks")
        insert_pos = len(ws_root)
        for idx, child in enumerate(ws_root):
            if etree.QName(child).localname in AFTER_HYPERLINKS_TAGS:
                insert_pos = idx
                break
        ws_root.insert(insert_pos, hyperlinks_el)

    existing_hl_by_ref: dict[str, etree._Element] = {
        hl.get("ref", ""): hl for hl in hyperlinks_el.findall("main:hyperlink", NS) if hl.get("ref")
    }
    used_rids: set[str] = {rel.get("Id", "") for rel in rels_root}

    def next_rid() -> str:
        n = 1
        while f"rId{n}" in used_rids:
            n += 1
        rid = f"rId{n}"
        used_rids.add(rid)
        return rid

    def set_external_hyperlink(cell_ref: str, url: str) -> None:
        if not url:
            return
        if cell_ref in existing_hl_by_ref:
            rid = existing_hl_by_ref[cell_ref].get(f"{{{REL_NS}}}id", "")
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
        existing_hl_by_ref[cell_ref] = hl_el

    def ensure_row_element(r_num: int) -> etree._Element:
        if r_num in row_elements:
            r_el = row_elements[r_num]
            try:
                cur_ht = float(r_el.get("ht", "0"))
            except ValueError:
                cur_ht = 0.0
            if cur_ht < 200.0:
                r_el.set("ht", "276.75")
            r_el.set("customHeight", "1")
            return r_el
        r_el = etree.Element(f"{{{MAIN_NS}}}row", r=str(r_num), ht="273.75", customHeight="1")
        # Insert in ascending row order
        inserted = False
        for idx, existing in enumerate(sheet_data):
            if int(existing.get("r", "0")) > r_num:
                sheet_data.insert(idx, r_el)
                inserted = True
                break
        if not inserted:
            sheet_data.append(r_el)
        row_elements[r_num] = r_el
        return r_el

    def set_cell(r_el: etree._Element, r_num: int, col: str, value: Any, is_numeric: bool = False) -> None:
        ref = f"{col}{r_num}"
        c_el = r_el.find(f"main:c[@r='{ref}']", NS)
        if c_el is None:
            c_el = etree.Element(f"{{{MAIN_NS}}}c", r=ref)
            # Insert in column order A..T
            col_pos = COLUMNS_ORDER.index(col)
            placed = False
            for idx, existing_c in enumerate(r_el):
                ex_ref = existing_c.get("r", "")
                ex_col = "".join(ch for ch in ex_ref if ch.isalpha())
                if ex_col in COLUMNS_ORDER and COLUMNS_ORDER.index(ex_col) > col_pos:
                    r_el.insert(idx, c_el)
                    placed = True
                    break
            if not placed:
                r_el.append(c_el)

        style_id = c_el.get("s") or DEFAULT_COL_STYLES[col]
        if col in ("L", "N") and str(value or "").strip():
            style_id = "41" if style_id == "98" else style_id
        c_el.attrib.clear()
        c_el.set("r", ref)
        c_el.set("s", style_id)
        for ch in list(c_el):
            c_el.remove(ch)

        if value is None or (isinstance(value, str) and value == ""):
            return

        v_el = etree.SubElement(c_el, f"{{{MAIN_NS}}}v")
        if is_numeric:
            v_el.text = str(value)
        else:
            c_el.set("t", "s")
            v_el.text = str(intern_str(str(value)))

    inserted = 0
    updated = 0

    for item in bug_rows:
        bug_id = str(item["bug_id"]).strip()
        jira_url = str(item["jira_url"]).strip()
        target_row = existing_by_bug_id.get(bug_id) or existing_by_jira_url.get(jira_url)
        if target_row is None:
            max_populated_row += 1
            target_row = max_populated_row
            existing_by_bug_id[bug_id] = target_row
            existing_by_jira_url[jira_url] = target_row
            inserted += 1
        else:
            updated += 1

        seq_id = target_row - 10
        r_el = ensure_row_element(target_row)
        serial_date = _to_excel_serial(item.get("reported_on"))
        ev_url = str(item.get("evidence_url", "")).strip()
        ev_label = str(item.get("evidence_label", "")).strip() or ev_url

        set_cell(r_el, target_row, "A", seq_id, is_numeric=True)
        set_cell(r_el, target_row, "B", bug_id)
        set_cell(r_el, target_row, "C", str(item["summary"]).strip())
        set_cell(r_el, target_row, "D", str(item["area"]).strip())
        set_cell(r_el, target_row, "E", str(item["type"]).strip())
        set_cell(r_el, target_row, "F", str(item["severity"]).strip())
        set_cell(r_el, target_row, "G", str(item["steps"]).strip())
        set_cell(r_el, target_row, "H", str(item["expected"]).strip())
        set_cell(r_el, target_row, "I", str(item["actual"]).strip())
        set_cell(r_el, target_row, "J", "STAG")
        set_cell(r_el, target_row, "K", str(item.get("device_locale", "Staging API & Chrome · 1440×900 · en-US")).strip())
        set_cell(r_el, target_row, "L", ev_label)
        set_cell(r_el, target_row, "M", str(item.get("qa_stage", "NEW")).strip())
        set_cell(r_el, target_row, "N", jira_url)
        set_cell(r_el, target_row, "O", str(item.get("reported_by", "Nguyen Bao Minh")).strip())
        set_cell(r_el, target_row, "P", serial_date, is_numeric=True)
        set_cell(r_el, target_row, "Q", str(item.get("assigned_to", "")).strip())
        set_cell(r_el, target_row, "R", str(item.get("retest_result", "NOT RUN")).strip())
        retest_date = str(item.get("retest_date", "")).strip()
        if retest_date:
            set_cell(r_el, target_row, "S", _to_excel_serial(retest_date), is_numeric=True)
        else:
            set_cell(r_el, target_row, "S", "")
        set_cell(r_el, target_row, "T", str(item.get("notes", "")).strip())

        if ev_url:
            set_external_hyperlink(f"L{target_row}", ev_url)
        set_external_hyperlink(f"N{target_row}", jira_url)

    if len(hyperlinks_el) == 0:
        ws_root.remove(hyperlinks_el)

    # Recompute exact sst/@count and sst/@uniqueCount across all worksheets in workbook
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

    return {
        "sheet_name": sheet_name,
        "worksheet_path": ws_path,
        "inserted": inserted,
        "updated": updated,
        "last_row": max_populated_row,
        "output_xlsx": str(output_xlsx),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Upsert API bug rows into sheet API_BUGS of gns_Bug_Report_Tracking.xlsx.")
    ap.add_argument("--xlsx", required=True, help="Input .xlsx file path downloaded from Google Drive.")
    ap.add_argument("--bugs", required=True, help="JSON file containing a list of API bug row objects.")
    ap.add_argument("--output", required=True, help="Output .xlsx file path.")
    ap.add_argument("--sheet", default="API_BUGS", help="Target worksheet name (default: API_BUGS).")
    args = ap.parse_args(argv)

    rows = json.loads(pathlib.Path(args.bugs).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        print("ERROR: --bugs JSON must be a list of objects.", file=sys.stderr)
        return 1
    res = upsert_api_bugs(
        input_xlsx=pathlib.Path(args.xlsx).resolve(),
        output_xlsx=pathlib.Path(args.output).resolve(),
        bug_rows=rows,
        sheet_name=args.sheet,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
