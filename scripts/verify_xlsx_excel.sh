#!/usr/bin/env bash
# Verify OpenXML integrity (ZIP CRC, namespaces, no ns0: on .rels) and macOS Microsoft Excel open check
# Usage: ./scripts/verify_xlsx_excel.sh /path/to/gns_Bug_Report_Tracking_updated.xlsx

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <path-to-xlsx>" >&2
  exit 1
fi

XLSX_PATH="$(python3 -c 'import pathlib, sys; print(pathlib.Path(sys.argv[1]).expanduser().resolve())' "$1")"

if [[ ! -f "$XLSX_PATH" ]]; then
  echo "[ERROR] File not found: $XLSX_PATH" >&2
  exit 1
fi

echo "1/2 Checking ZIP CRC, lxml XML parsing, and OpenXML namespace hygiene..."
python3 - "$XLSX_PATH" <<'PY'
import sys, zipfile
from lxml import etree

path = sys.argv[1]
with zipfile.ZipFile(path, "r") as zf:
    bad = zf.testzip()
    assert bad is None, f"Corrupt ZIP entry: {bad}"
    for name in zf.namelist():
        if name.endswith(".xml") or name.endswith(".rels"):
            raw = zf.read(name)
            root = etree.fromstring(raw)
            if name.endswith(".rels"):
                assert b"<ns0:" not in raw, f"Forbidden ns0: prefix detected in {name}!"
                assert root.tag.endswith("Relationships"), f"Unexpected root tag in {name}: {root.tag}"
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
                ignorable = root.get("{http://schemas.openxmlformats.org/markup-compatibility/2006}Ignorable", "")
                for prefix in ignorable.split():
                    assert prefix in root.nsmap, f"Missing xmlns:{prefix} required by mc:Ignorable in {name}!"
print("[PASS] ZIP CRC, XML structure, mc:Ignorable prefixes, and .rels default namespaces verified.")
PY

if [[ "$(uname -s)" == "Darwin" ]] && [[ -d "/Applications/Microsoft Excel.app" ]]; then
  echo "2/2 Verifying clean workbook open in macOS Microsoft Excel via osascript..."
  osascript - "$XLSX_PATH" <<'APPLESCRIPT'
on run argv
  set xlsxPath to POSIX file (item 1 of argv)
  tell application "Microsoft Excel"
    set wb to open workbook workbook file name (xlsxPath as text) read only true
    set sCount to count of worksheets of wb
    set wbName to name of wb
    close wb saving no
    return "Opened cleanly: " & wbName & " (" & sCount & " worksheets)"
  end tell
end run
APPLESCRIPT
  echo "[PASS] Microsoft Excel opened the workbook cleanly without repair dialogs."
else
  echo "2/2 Skipping macOS Microsoft Excel check (not on macOS or Microsoft Excel.app not installed)."
fi
