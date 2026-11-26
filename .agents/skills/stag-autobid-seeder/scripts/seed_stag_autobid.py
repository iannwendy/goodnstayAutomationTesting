#!/usr/bin/env python3
"""goodNstay Staging Auto-Bid Seeder & Cleanup CLI.

Authenticates directly against services.stag.goodnstay.com, inspects or cleans up
open accommodation requests, and seeds a guaranteed live Auto-Bid from Stay Hotel H11
(KR / KR-11 mirrored stayingCity, roomTypes=["suite", "anyRoom"]) so QA can test
Payment, checkout, and offer-acceptance flows on web.stag.goodnstay.com without
being blocked by UI LocationPicker bug OP-1787 or 0-hotel coverage gaps.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import datetime
import json
import os
import pathlib
import sys
import time
from typing import Any
import urllib.error
from urllib.parse import quote
import urllib.request

DEFAULT_API_BASE_URL = "https://services.stag.goodnstay.com"
DEFAULT_WEB_ORIGIN = "https://web.stag.goodnstay.com"
DEFAULT_STAG_EMAIL = ""
DEFAULT_STAG_PASSWORD = ""
DEFAULT_LOCALE = "en-US"

MAX_AUTOBID_GUESTS = 8
MAX_AUTOBID_ROOMS = 4


class ValidationError(ValueError):
    """Raised when request parameters violate Staging Auto-Bid guardrails."""


class StagApiError(RuntimeError):
    """Raised when services.stag.goodnstay.com returns an HTTP or network error."""


@dataclass
class StagConfig:
    api_base_url: str = DEFAULT_API_BASE_URL
    web_origin: str = DEFAULT_WEB_ORIGIN
    email: str = DEFAULT_STAG_EMAIL
    password: str = field(default=DEFAULT_STAG_PASSWORD, repr=False)
    locale: str = DEFAULT_LOCALE


@dataclass
class LoginSession:
    jwt: str = field(repr=False)
    user: dict[str, Any] = field(default_factory=dict)


def _parse_dotenv(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        values[key] = val
    return values


def load_config(
    env_paths: list[pathlib.Path] | None = None,
    email_override: str | None = None,
    locale_override: str | None = None,
) -> StagConfig:
    workspace_root = pathlib.Path(__file__).resolve().parents[4]
    candidates = env_paths if env_paths is not None else [workspace_root / ".env.stag"]
    merged: dict[str, str] = {}
    for p in candidates:
        merged.update(_parse_dotenv(p))
    for key in (
        "GNS_STAG_API_BASE_URL",
        "GNS_STAG_WEB_ORIGIN",
        "GNS_STAG_EMAIL",
        "GNS_STAG_PASSWORD",
        "GNS_STAG_LOCALE",
    ):
        if os.environ.get(key):
            merged[key] = os.environ[key]

    return StagConfig(
        api_base_url=merged.get("GNS_STAG_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/"),
        web_origin=merged.get("GNS_STAG_WEB_ORIGIN", DEFAULT_WEB_ORIGIN).rstrip("/"),
        email=(email_override or merged.get("GNS_STAG_EMAIL") or DEFAULT_STAG_EMAIL).strip(),
        password=merged.get("GNS_STAG_PASSWORD") or DEFAULT_STAG_PASSWORD,
        locale=(locale_override or merged.get("GNS_STAG_LOCALE") or DEFAULT_LOCALE).strip(),
    )


def _parse_iso_date(value: str, field_name: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid {field_name} '{value}': expected YYYY-MM-DD.") from exc


def _parse_iso_datetime(value: str | None) -> datetime.datetime | None:
    if not value or not isinstance(value, str):
        return None
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def is_bid_unexpired_waiting(
    bid: dict[str, Any],
    now: datetime.datetime | None = None,
    min_remaining_seconds: int = 300,
) -> bool:
    if str(bid.get("bidStatus") or "").lower() != "waiting":
        return False
    exp = _parse_iso_datetime(bid.get("expiredAt"))
    if exp is None:
        return True
    ref = now or datetime.datetime.now(datetime.timezone.utc)
    return (exp - ref).total_seconds() >= min_remaining_seconds


def extract_waiting_bids(
    deal: dict[str, Any],
    now: datetime.datetime | None = None,
    min_remaining_seconds: int = 60,
) -> list[dict[str, Any]]:
    bids = deal.get("hotelBids") or []
    if not isinstance(bids, list):
        return []
    return [
        b
        for b in bids
        if isinstance(b, dict)
        and is_bid_unexpired_waiting(b, now=now, min_remaining_seconds=min_remaining_seconds)
    ]


def build_autobid_request_payload(
    user: dict[str, Any],
    check_in: str | None = None,
    check_out: str | None = None,
    guests: int = 2,
    rooms: int = 1,
    notes: str = "",
    today: datetime.date | None = None,
) -> dict[str, Any]:
    ref_today = today or datetime.date.today()
    ci_date = _parse_iso_date(check_in, "checkInDate") if check_in else (ref_today + datetime.timedelta(days=5))
    co_date = _parse_iso_date(check_out, "checkOutDate") if check_out else (ci_date + datetime.timedelta(days=2))

    if ci_date < ref_today:
        raise ValidationError(f"checkInDate ({ci_date.isoformat()}) cannot be in the past (today={ref_today.isoformat()}).")
    if co_date <= ci_date:
        raise ValidationError(
            f"checkOutDate ({co_date.isoformat()}) must be strictly after checkInDate ({ci_date.isoformat()})."
        )
    if not (1 <= guests <= MAX_AUTOBID_GUESTS):
        raise ValidationError(
            f"guests ({guests}) must be between 1 and {MAX_AUTOBID_GUESTS} to satisfy Stay Hotel H11 Auto-Bid guardrails."
        )
    if not (1 <= rooms <= MAX_AUTOBID_ROOMS):
        raise ValidationError(
            f"rooms ({rooms}) must be between 1 and {MAX_AUTOBID_ROOMS} to satisfy Stay Hotel H11 Auto-Bid guardrails."
        )

    raw_dob = str(user.get("dob") or "2005-01-01").strip()
    dob = raw_dob[:10] if len(raw_dob) >= 10 else "2005-01-01"
    raw_phone = str(user.get("phone") or "900000000").strip().lstrip("+")
    if raw_phone.startswith("84") and len(raw_phone) > 9:
        raw_phone = raw_phone[2:]

    return {
        "data": {
            "fullName": str(user.get("fullName") or "QA Traveler").strip(),
            "email": str(user.get("email") or DEFAULT_STAG_EMAIL or "qa-sample@example.test").strip(),
            "phone": raw_phone or "900000000",
            "dob": dob,
            "gender": str(user.get("gender") or "male").strip(),
            "country": str(user.get("country") or "VN").strip(),
            "checkInDate": ci_date.isoformat(),
            "checkOutDate": co_date.isoformat(),
            "guestCount": int(guests),
            "roomCount": int(rooms),
            # Stay Hotel H11 (branch #46) Auto-Bid matching invariants:
            # 1) KR-11 province + mirrored stayingCity="KR-11" (OP-834; bypasses UI bug OP-1787)
            # 2) Empty district/ward (setting KR-11-JUNG or empty stayingCity yields isNoMatchedHotel=true)
            # 3) roomTypes=["suite", "anyRoom"] to pass hardRulesFilter=["accommodation.room"]
            "stayingCountry": "KR",
            "stayingProvince": "KR-11",
            "stayingCity": "KR-11",
            "stayingDistrict": "",
            "stayingWard": "",
            "accommodationType": "hotel",
            "serviceTypes": [],
            "roomTypes": ["suite", "anyRoom"],
            "bedTypes": [],
            "viewTypes": [],
            "others": [],
            "filterOptions": {},
            "notes": notes,
            "guestComposition": {
                "adults": int(guests),
                "children": 0,
                "infants": 0,
                "pets": 0,
            },
        }
    }


class StagTravelerClient:
    def __init__(self, config: StagConfig, timeout: float = 20.0):
        self.config = config
        self.timeout = timeout

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        bearer_jwt: str | None = None,
    ) -> Any:
        url = f"{self.config.api_base_url}{path}"
        headers: dict[str, str] = {
            "Accept": "application/json",
            "Origin": self.config.web_origin,
        }
        if bearer_jwt:
            headers["Authorization"] = f"Bearer {bearer_jwt}"
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        last_exc: Exception | None = None
        for attempt in range(3):
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                    if not raw:
                        return {}
                    return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                try:
                    detail = exc.read().decode("utf-8", errors="replace")
                finally:
                    exc.close()
                raise StagApiError(
                    f"Staging API {method} {path} failed (HTTP {exc.code}): {detail}"
                ) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(0.4 * (attempt + 1))
                    continue
        reason = getattr(last_exc, "reason", str(last_exc))
        raise StagApiError(f"Connection to {url} failed after 3 attempts: {reason}") from last_exc

    def login(self) -> LoginSession:
        if (
            not self.config.email
            or not self.config.password
            or self.config.password == "PASTE_YOUR_STAGING_QA_PASSWORD_HERE"
        ):
            raise ValidationError(
                "Missing Staging QA credentials: copy .env.stag.example to .env.stag (chmod 600) "
                "and set GNS_STAG_EMAIL and GNS_STAG_PASSWORD."
            )
        resp = self._request_json(
            "POST",
            "/api/traveler/login",
            payload={"username": self.config.email, "password": self.config.password},
        )
        data = (resp or {}).get("data") if isinstance(resp, dict) else None
        jwt_tok = (data or {}).get("jwt") if isinstance(data, dict) else None
        if not jwt_tok or not isinstance(jwt_tok, str):
            raise StagApiError("POST /api/traveler/login succeeded without returning data.jwt.")
        user = (data or {}).get("user")
        return LoginSession(jwt=jwt_tok, user=dict(user) if isinstance(user, dict) else {})

    def list_open_requests(self, session: LoginSession) -> list[dict[str, Any]]:
        loc = quote(self.config.locale, safe="")
        resp = self._request_json(
            "GET",
            f"/api/traveler/request-bids?requestStatus=open&locale={loc}",
            bearer_jwt=session.jwt,
        )
        deals = (resp or {}).get("data") if isinstance(resp, dict) else []
        return [d for d in deals if isinstance(d, dict)] if isinstance(deals, list) else []

    def create_request(self, session: LoginSession, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._request_json(
            "POST",
            "/api/traveler/request-bids",
            payload=payload,
            bearer_jwt=session.jwt,
        )
        return resp if isinstance(resp, dict) else {}

    def cancel_request(self, session: LoginSession, request_id: int) -> dict[str, Any]:
        resp = self._request_json(
            "PUT",
            f"/api/customer-requests/{int(request_id)}",
            payload={"data": {"action": "cancel"}},
            bearer_jwt=session.jwt,
        )
        return resp if isinstance(resp, dict) else {}


def summarize_open_deals(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for deal in deals:
        bids = deal.get("hotelBids") or []
        waiting = extract_waiting_bids(deal, min_remaining_seconds=0)
        summaries.append(
            {
                "requestId": deal.get("id"),
                "code": deal.get("code"),
                "checkInDate": deal.get("checkInDate"),
                "checkOutDate": deal.get("checkOutDate"),
                "isNoMatchedHotel": bool(deal.get("isNoMatchedHotel")),
                "totalBids": len(bids) if isinstance(bids, list) else 0,
                "waitingBids": [
                    {
                        "bidId": b.get("id"),
                        "hotelName": b.get("hotelName"),
                        "bidStatus": b.get("bidStatus"),
                        "totalPrice": b.get("totalPrice"),
                        "currency": b.get("currency"),
                        "expiredAt": b.get("expiredAt"),
                    }
                    for b in waiting
                ],
            }
        )
    return summaries


def cancel_unmatched_open_requests(
    client: StagTravelerClient,
    session: LoginSession,
) -> list[int]:
    deals = client.list_open_requests(session)
    cancelled: list[int] = []
    for deal in deals:
        rid = deal.get("id")
        if rid is None:
            continue
        if extract_waiting_bids(deal, min_remaining_seconds=60):
            continue
        client.cancel_request(session, int(rid))
        cancelled.append(int(rid))
    return cancelled


def seed_or_reuse_autobid(
    client: StagTravelerClient,
    session: LoginSession,
    check_in: str | None = None,
    check_out: str | None = None,
    guests: int = 2,
    rooms: int = 1,
    notes: str = "",
    reuse_existing: bool = True,
    poll_interval: float = 1.5,
    poll_timeout: float = 15.0,
) -> dict[str, Any]:
    if reuse_existing:
        open_deals = client.list_open_requests(session)
        for deal in open_deals:
            waiting = extract_waiting_bids(deal, min_remaining_seconds=300)
            if waiting:
                summary = summarize_open_deals([deal])[0]
                return {
                    "action": "reused",
                    "accommodationUrl": f"{client.config.web_origin}/{client.config.locale}/accommodation",
                    **summary,
                }

    payload = build_autobid_request_payload(
        user=session.user,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        rooms=rooms,
        notes=notes,
    )
    created = client.create_request(session, payload)
    c_data = (created or {}).get("data") or {}
    rid = c_data.get("requestId") or c_data.get("id")
    if rid is None:
        raise StagApiError(f"POST /api/traveler/request-bids did not return data.requestId: {created}")
    rid_int = int(rid)

    deadline = time.monotonic() + max(0.1, poll_timeout)
    matched_deal: dict[str, Any] | None = None
    while True:
        time.sleep(max(0.01, poll_interval))
        deals = client.list_open_requests(session)
        matched_deal = next((d for d in deals if d.get("id") == rid_int), None)
        if matched_deal and extract_waiting_bids(matched_deal, min_remaining_seconds=0):
            break
        if matched_deal and matched_deal.get("isNoMatchedHotel"):
            break
        if time.monotonic() >= deadline:
            break

    if matched_deal is None:
        return {
            "action": "created",
            "requestId": rid_int,
            "code": c_data.get("code"),
            "checkInDate": payload["data"]["checkInDate"],
            "checkOutDate": payload["data"]["checkOutDate"],
            "isNoMatchedHotel": False,
            "totalBids": 0,
            "waitingBids": [],
            "accommodationUrl": f"{client.config.web_origin}/{client.config.locale}/accommodation",
        }

    summary = summarize_open_deals([matched_deal])[0]
    return {
        "action": "created",
        "accommodationUrl": f"{client.config.web_origin}/{client.config.locale}/accommodation",
        **summary,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed, inspect, or clean up live Auto-Bid room requests on goodNstay Staging for Payment QA."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="List open requests and waiting hotel bids (read-only).")
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify Staging login and print the exact request payload without creating a request.",
    )
    mode.add_argument(
        "--seed",
        action="store_true",
        help="Ensure an active waiting Auto-Bid exists (reuses an unexpired waiting bid unless --force-new is set).",
    )
    mode.add_argument(
        "--cancel",
        type=int,
        action="append",
        metavar="REQUEST_ID",
        help="Cancel specific open request ID(s) via PUT /api/customer-requests/<id>.",
    )
    mode.add_argument(
        "--cancel-unmatched",
        action="store_true",
        help="Cancel open requests that have 0 active waiting bids while preserving active offers.",
    )

    parser.add_argument("--force-new", action="store_true", help="Create a new request even if a waiting bid exists.")
    parser.add_argument("--checkin", help="Check-in date YYYY-MM-DD (default: today + 5 days).")
    parser.add_argument("--checkout", help="Check-out date YYYY-MM-DD (default: checkin + 2 days).")
    parser.add_argument("--guests", type=int, default=2, help="Guest count 1..8 (default: 2).")
    parser.add_argument("--rooms", type=int, default=1, help="Room count 1..4 (default: 1).")
    parser.add_argument("--notes", default="", help="Optional request notes.")
    parser.add_argument("--email", help="Override Staging traveler account email.")
    parser.add_argument("--locale", default=DEFAULT_LOCALE, help="Locale for readback URL (default: en-US).")
    parser.add_argument("--poll-timeout", type=float, default=15.0, help="Max seconds to poll for BullMQ Auto-Bid.")
    parser.add_argument("--json", action="store_true", help="Print output as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        cfg = load_config(email_override=args.email, locale_override=args.locale)
        client = StagTravelerClient(cfg)
        session = client.login()

        if args.dry_run:
            payload = build_autobid_request_payload(
                user=session.user,
                check_in=args.checkin,
                check_out=args.checkout,
                guests=args.guests,
                rooms=args.rooms,
                notes=args.notes,
            )
            out = {
                "mode": "dry-run",
                "authenticatedEmail": cfg.email,
                "endpoint": f"POST {cfg.api_base_url}/api/traveler/request-bids",
                "payload": payload,
            }
            if args.json:
                print(json.dumps(out, ensure_ascii=False, indent=2))
            else:
                print(f"[DRY-RUN] Authenticated as {cfg.email} against {cfg.api_base_url}")
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        if args.list:
            deals = summarize_open_deals(client.list_open_requests(session))
            if args.json:
                print(json.dumps({"openRequests": deals}, ensure_ascii=False, indent=2))
            else:
                print(f"Open requests for {cfg.email}: {len(deals)}")
                for d in deals:
                    print(
                        f"- Request #{d['requestId']} ({d['code']}) | {d['checkInDate']} -> {d['checkOutDate']} | "
                        f"waitingBids={len(d['waitingBids'])}/{d['totalBids']} | noMatch={d['isNoMatchedHotel']}"
                    )
                    for b in d["waitingBids"]:
                        print(
                            f"    * Bid #{b['bidId']}: {b['hotelName']} | {b['totalPrice']} {b['currency']} | "
                            f"status={b['bidStatus']} | expires={b['expiredAt']}"
                        )
            return 0

        if args.cancel:
            for rid in args.cancel:
                client.cancel_request(session, rid)
            if args.json:
                print(json.dumps({"cancelledRequestIds": args.cancel}, ensure_ascii=False, indent=2))
            else:
                print(f"Cancelled request IDs: {args.cancel}")
            return 0

        if args.cancel_unmatched:
            cancelled = cancel_unmatched_open_requests(client, session)
            if args.json:
                print(json.dumps({"cancelledUnmatchedIds": cancelled}, ensure_ascii=False, indent=2))
            else:
                print(f"Cancelled unmatched/expired open requests ({len(cancelled)}): {cancelled}")
            return 0

        # Default or --seed
        result = seed_or_reuse_autobid(
            client=client,
            session=session,
            check_in=args.checkin,
            check_out=args.checkout,
            guests=args.guests,
            rooms=args.rooms,
            notes=args.notes,
            reuse_existing=not args.force_new,
            poll_timeout=args.poll_timeout,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(
                f"[{result['action'].upper()}] Request #{result['requestId']} ({result['code']}) | "
                f"{result['checkInDate']} -> {result['checkOutDate']} | "
                f"waitingBids={len(result['waitingBids'])}"
            )
            for b in result["waitingBids"]:
                print(
                    f"  -> Bid #{b['bidId']}: {b['hotelName']} | {b['totalPrice']} {b['currency']} | "
                    f"status={b['bidStatus']} | expires={b['expiredAt']}"
                )
            print(f"  -> Open in UI: {result['accommodationUrl']}")
        return 0 if result["waitingBids"] else 2

    except (ValidationError, StagApiError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
