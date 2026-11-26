#!/usr/bin/env python3
"""Idempotent, anti-duplicate Jira Board #135 batch publisher & live verifier.

Portable version of the goodNstay QA batch uploader:
- Safe dry-run preview by default (pass --confirm to publish live tickets)
- Queries GET /rest/agile/1.0/board/<board_id>/issue by summary before creating
- Flushes each created issue_key immediately to uploaded_jira_tickets.json so retries never duplicate
- Recovers cleanly across TLS resets ([Errno 54] Connection reset by peer) with bounded retries
- Verifies live post-upload state: on_board, attachment count, inline media count, assignee, and all 12 OP custom fields
"""

from __future__ import annotations

import argparse
import base64
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

KIT_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_REPORTER = KIT_ROOT / ".agents/skills/jira-bug-reporter/scripts/jira_bug_reporter.py"
DEFAULT_ENV_FILE = KIT_ROOT / ".env.jira"

REQUIRED_CUSTOM_FIELDS = [
    "customfield_10053",  # Environment
    "customfield_10170",  # Pre-condition
    "customfield_10135",  # Step-by-step
    "customfield_10137",  # Actual Result
    "customfield_10136",  # Expected Result
    "customfield_10057",  # UI References
    "customfield_10049",  # Signals and Clues
    "customfield_10051",  # Detailed Analysis
    "customfield_10004",  # Impact
    "customfield_10038",  # Platform
    "customfield_10039",  # Original Source Location
    "priority",
]


def load_jira_env(env_file: pathlib.Path) -> tuple[str, str]:
    if not env_file.is_file():
        raise FileNotFoundError(
            f"Missing Jira env file: {env_file}. Copy .env.jira.example to .env.jira and set JIRA_API_TOKEN."
        )
    env: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    for req_key in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
        if not env.get(req_key) or env[req_key] == "PASTE_YOUR_ATLASSIAN_API_TOKEN_HERE":
            raise ValueError(f"{req_key} is not configured in {env_file}")
    auth = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_API_TOKEN']}".encode()).decode()
    return env["JIRA_BASE_URL"].rstrip("/"), auth


def jira_get(site: str, auth: str, path: str, retries: int = 4) -> dict[str, Any]:
    url = f"{site}{path}"
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace")
            finally:
                exc.close()
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"HTTP {exc.code} on {path}: {body[:300]}") from exc
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"Exhausted retries on {path}")


def fetch_board_map(site: str, auth: str, board_id: int) -> tuple[dict[str, str], set[str]]:
    by_summary: dict[str, str] = {}
    keys: set[str] = set()
    start = 0
    while True:
        data = jira_get(
            site,
            auth,
            f"/rest/agile/1.0/board/{board_id}/issue?startAt={start}&maxResults=100&fields=summary",
        )
        issues = data.get("issues", [])
        for iss in issues:
            k = iss["key"]
            keys.add(k)
            s = (iss.get("fields", {}).get("summary") or "").strip()
            if s:
                by_summary[s] = k
        if len(keys) >= data.get("total", 0) or not issues:
            break
        start += len(issues)
    return by_summary, keys


def count_media_nodes(adf: Any) -> int:
    if isinstance(adf, dict):
        c = 1 if adf.get("type") == "media" else 0
        for v in adf.values():
            c += count_media_nodes(v)
        return c
    if isinstance(adf, list):
        return sum(count_media_nodes(x) for x in adf)
    return 0


def save_progress(
    out_json: pathlib.Path,
    site: str,
    board_id: int,
    board_name: str,
    project_key: str,
    tickets: list[dict[str, Any]],
) -> None:
    doc = {
        "board_name": board_name,
        "board_id": board_id,
        "board_url": f"{site}/jira/software/c/projects/{project_key}/boards/{board_id}/backlog",
        "total_uploaded": len(tickets),
        "tickets": tickets,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Idempotent anti-duplicate Jira Board batch publisher & live verifier."
    )
    ap.add_argument(
        "--consolidated",
        required=True,
        help="Path to consolidated_bugs.json containing bug_id, title, payload_path, attachments.",
    )
    ap.add_argument(
        "--output",
        default="",
        help="Output uploaded_jira_tickets.json path (defaults to <consolidated_dir>/uploaded_jira_tickets.json).",
    )
    ap.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Path to .env.jira file.")
    ap.add_argument("--reporter", default=str(DEFAULT_REPORTER), help="Path to jira_bug_reporter.py.")
    ap.add_argument("--board-id", type=int, default=135, help="Jira Scrum Board ID (default: 135).")
    ap.add_argument("--board-name", default="Internship Program 2026", help="Jira Board display name.")
    ap.add_argument("--project-key", default="OP", help="Jira Project key (default: OP).")
    ap.add_argument(
        "--expected-assignee",
        default="",
        help="Optional displayName expected on Board filter (e.g. 'Nguyen Bao Minh').",
    )
    ap.add_argument(
        "--confirm",
        action="store_true",
        help="Actually publish live Jira tickets. Without --confirm, runs dry-run preview only.",
    )
    args = ap.parse_args()

    cons_path = pathlib.Path(args.consolidated).resolve()
    out_json = (
        pathlib.Path(args.output).resolve()
        if args.output
        else cons_path.parent / "uploaded_jira_tickets.json"
    )
    env_file = pathlib.Path(args.env_file).resolve()
    reporter = pathlib.Path(args.reporter).resolve()
    bugs = json.loads(cons_path.read_text(encoding="utf-8"))

    if not args.confirm:
        print(f"[DRY-RUN] Previewing {len(bugs)} bug payloads via {reporter.name} (pass --confirm to publish):")
        for bug in bugs:
            payload_path = pathlib.Path(bug["payload_path"])
            if not payload_path.is_absolute():
                payload_path = (cons_path.parent / payload_path).resolve()
            proc = subprocess.run(
                [sys.executable, str(reporter), "--env-file", str(env_file), "--input", str(payload_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            status = "OK" if proc.returncode == 0 else f"ERROR ({proc.returncode})"
            print(f"  - {bug['bug_id']}: {status} | {bug['title'][:90]}")
            if proc.returncode != 0:
                print((proc.stderr or proc.stdout).strip(), file=sys.stderr)
                return 1
        print("[DRY-RUN] All payloads validated cleanly. Re-run with --confirm to publish live tickets.")
        return 0

    site, auth = load_jira_env(env_file)
    existing_records: dict[str, dict[str, Any]] = {}
    if out_json.exists():
        prev = json.loads(out_json.read_text(encoding="utf-8"))
        for t in prev.get("tickets", []):
            existing_records[t["bug_id"]] = t

    board_by_summary, board_keys = fetch_board_map(site, auth, args.board_id)
    print(f"Board #{args.board_id} pre-check: {len(board_keys)} existing issues loaded.", flush=True)

    ordered_tickets: list[dict[str, Any]] = []
    for bug in bugs:
        bug_id = bug["bug_id"]
        title = bug["title"].strip()
        attachments = bug.get("attachments", [])
        expected_att = len(attachments)
        payload_path = pathlib.Path(bug["payload_path"])
        if not payload_path.is_absolute():
            payload_path = (cons_path.parent / payload_path).resolve()

        if bug_id in existing_records and existing_records[bug_id].get("issue_key"):
            rec = existing_records[bug_id]
            print(f"[SKIP-RESUME] {bug_id} already uploaded -> {rec['issue_key']}", flush=True)
            ordered_tickets.append(rec)
            continue

        if title in board_by_summary:
            key = board_by_summary[title]
            print(f"[SKIP-EXISTS] {bug_id} already on Board #{args.board_id} -> {key}", flush=True)
            rec = {
                "bug_id": bug_id,
                "issue_key": key,
                "issue_url": f"{site}/browse/{key}",
                "title": title,
                "severity": bug.get("severity", ""),
                "priority_label": bug.get("priority_label", ""),
                "expected_attachments": expected_att,
                "attachment_names": [pathlib.Path(p).name for p in attachments],
            }
            existing_records[bug_id] = rec
            ordered_tickets.append(rec)
            save_progress(out_json, site, args.board_id, args.board_name, args.project_key, ordered_tickets)
            continue

        created_key = None
        last_err = ""
        for attempt in range(1, 4):
            if attempt > 1:
                board_by_summary, board_keys = fetch_board_map(site, auth, args.board_id)
                if title in board_by_summary:
                    created_key = board_by_summary[title]
                    print(f"[RECOVERED] {bug_id} found on Board #{args.board_id} after retry -> {created_key}", flush=True)
                    break

            proc = subprocess.run(
                [
                    sys.executable,
                    str(reporter),
                    "--env-file",
                    str(env_file),
                    "--input",
                    str(payload_path),
                    "--confirm",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode == 0:
                out_txt = proc.stdout.strip()
                try:
                    j_start = out_txt.find("{")
                    j_end = out_txt.rfind("}")
                    parsed = json.loads(out_txt[j_start : j_end + 1])
                    created_key = parsed.get("issue_key")
                except Exception:
                    m = re.search(rf"\b({re.escape(args.project_key)}-\d+)\b", out_txt)
                    created_key = m.group(1) if m else None
                if created_key:
                    print(f"[CREATED] {bug_id} -> {created_key} ({expected_att} attachments)", flush=True)
                    break
            last_err = (proc.stderr or proc.stdout)[-400:]
            print(f"[RETRY {attempt}/3] {bug_id} failed: {last_err}", flush=True)
            time.sleep(3 * attempt)

        if not created_key:
            print(f"[ERROR] Failed to publish {bug_id}: {last_err}", file=sys.stderr)
            return 1

        rec = {
            "bug_id": bug_id,
            "issue_key": created_key,
            "issue_url": f"{site}/browse/{created_key}",
            "title": title,
            "severity": bug.get("severity", ""),
            "priority_label": bug.get("priority_label", ""),
            "expected_attachments": expected_att,
            "attachment_names": [pathlib.Path(p).name for p in attachments],
        }
        existing_records[bug_id] = rec
        ordered_tickets.append(rec)
        save_progress(out_json, site, args.board_id, args.board_name, args.project_key, ordered_tickets)
        time.sleep(0.4)

    print(f"\nRunning full live post-upload verification on Board #{args.board_id}...", flush=True)
    _, live_board_keys = fetch_board_map(site, auth, args.board_id)
    failures = []
    for rec in ordered_tickets:
        key = rec["issue_key"]
        iss = jira_get(site, auth, f"/rest/api/3/issue/{key}")
        f = iss.get("fields", {})
        atts = f.get("attachment") or []
        missing_cf = [cf for cf in REQUIRED_CUSTOM_FIELDS if not f.get(cf)]
        inline_count = count_media_nodes(f.get("description"))
        on_board = key in live_board_keys
        assignee = (f.get("assignee") or {}).get("displayName", "")
        prio = (f.get("priority") or {}).get("name", "")
        rec["verified_on_board_135"] = on_board
        rec["verified_jira_attachments"] = len(atts)
        rec["inline_embedded_count"] = inline_count
        rec["verified_priority"] = prio
        rec["verified_assignee"] = assignee
        rec["missing_custom_fields"] = missing_cf
        rec["attachment_urls"] = [a.get("content", "") for a in atts]
        assignee_bad = bool(args.expected_assignee and assignee != args.expected_assignee)
        if not on_board or len(atts) != rec["expected_attachments"] or missing_cf or assignee_bad:
            failures.append((rec["bug_id"], key, on_board, len(atts), rec["expected_attachments"], inline_count, missing_cf, assignee))

    save_progress(out_json, site, args.board_id, args.board_name, args.project_key, ordered_tickets)
    print(f"Verified {len(ordered_tickets)} tickets. Failures: {len(failures)}", flush=True)
    if failures:
        for fail in failures:
            print("  VERIFY FAIL:", fail, file=sys.stderr)
        return 2
    print(f"ALL {len(ordered_tickets)} TICKETS 100% VERIFIED ON BOARD #{args.board_id}!", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
