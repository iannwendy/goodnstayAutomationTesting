---
name: stag-autobid-seeder
description: >-
  Use when testing Payment, checkout, offer acceptance, or traveler bidding flows on
  goodNstay Staging (web.stag.goodnstay.com or services.stag.goodnstay.com) that require
  an active open room request with a live hotel bid, or when Staging room requests fail
  with 400 INVALID_CITY_CODE / INVALID_DISTRICT_CODE (OP-1787) or return isNoMatchedHotel.
---

# goodNstay Staging Auto-Bid Seeder

## Overview

Seeds, reuses, inspects, and cleans up live hotel Auto-Bid offers (`Stay Hotel H11`, `169.4 KRW` / `$0.12`, `bidStatus: "waiting"`) on **goodNstay Staging** via [`scripts/seed_stag_autobid.py`](./scripts/seed_stag_autobid.py) using direct HTTP authentication (`POST /api/traveler/login`)—no browser session or `auth_state.json` required.

## When to Use

- Preparing an active `waiting` hotel offer (`CHOOSE THIS OFFER`) on `https://web.stag.goodnstay.com/<locale>/accommodation` for **Payment**, **FX**, **checkout**, or **booking** QA.
- Bypassing Web UI `LocationPicker` bug **`OP-1787`** (`400 INVALID_CITY_CODE` / `400 INVALID_DISTRICT_CODE` on Korea) when testing downstream bidding/payment flows.
- Troubleshooting `isNoMatchedHotel: true` or `0` coverage on Staging.
- Cleaning up orphan `isNoMatchedHotel` or expired open requests without touching active offers.

**When NOT to use:** Never run against Production (`goodnstay.com`), and do not use to mask UI location bugs when testing `LocationPicker` itself.

## Quick Reference (`seed_stag_autobid.py`)

```bash
# Seed or reuse an unexpired (>=5 min left) waiting Auto-Bid (DEFAULT)
python3 .agents/skills/stag-autobid-seeder/scripts/seed_stag_autobid.py --seed

# Force-create a brand-new request + poll BullMQ (~3s)
python3 .agents/skills/stag-autobid-seeder/scripts/seed_stag_autobid.py --seed --force-new

# Inspect open requests & waiting bids (read-only) / preview payload
python3 .agents/skills/stag-autobid-seeder/scripts/seed_stag_autobid.py --list
python3 .agents/skills/stag-autobid-seeder/scripts/seed_stag_autobid.py --dry-run

# Cancel open requests that have 0 active waiting bids
python3 .agents/skills/stag-autobid-seeder/scripts/seed_stag_autobid.py --cancel-unmatched
```

Run `--help` for `--checkin`, `--checkout`, `--guests`, `--rooms`, `--cancel <id>`, `--email`, `--locale`, and `--json`. Reads Staging QA credentials from `GNS_STAG_EMAIL` / `GNS_STAG_PASSWORD` (`.env.stag` or environment variables).

## Staging Auto-Bid Matching Invariants (`Stay Hotel H11`, Branch `#46`)

`POST https://services.stag.goodnstay.com/api/traveler/request-bids` only triggers an automatic bid on Staging when **all** of these invariants hold:

| Field | Required Value | Why It Matters |
|---|---|---|
| `stayingCountry` | `"KR"` | Test hotel `Stay Hotel H11` (`user.isTestAccount: true`) is registered in Seoul (`KR-11`). |
| `stayingProvince` | `"KR-11"` | Canonical L2 province code for Seoul. |
| `stayingCity` | `"KR-11"` | **Must mirror `stayingProvince` (`OP-834`)**. Sending `""` yields `isNoMatchedHotel: true`; using Web UI sends `KR-11-GANGNAM` and fails `400 INVALID_CITY_CODE` (`OP-1787`). |
| `stayingDistrict` / `stayingWard` | `""` / `""` | Sending `KR-11-JUNG` fails branch matching (`isNoMatchedHotel: true`). |
| `accommodationType` | `"hotel"` | Matches branch property type. |
| `roomTypes` | `["suite", "anyRoom"]` | Satisfies `hardRulesFilter: ["accommodation.room"]` (`Moonlight Room 4` only has `["Suite", "Double"]`; `["standard"]` matches `0` rooms). |
| `guestCount` / `roomCount` | `1..8` / `1..4` | Exceeding Auto-Bid max guardrails (`guests > 8` or `rooms > 4`) skips automatic bidding. |

## Common Mistakes

- **Reading `hotelBids` right after `POST`**: BullMQ (`OP-1560` / `OP-1564`) populates Auto-Bids asynchronously in ~2–3.5s; let `seed_stag_autobid.py` poll `GET /api/traveler/request-bids?requestStatus=open&locale=en-US`.
- **Trusting `/api/traveler/partner-network-coverage`**: Test properties (`isTestAccount: true`) show `0` public coverage yet still auto-bid for test travelers on `KR-11`.
- **Expired offers**: Auto-Bids expire after **1 hour** (`expiredAt`); `--seed` skips offers with `< 5` min left.
- **Secret & test hygiene**: Never print `data.jwt` or passwords. Validate changes with:
  ```bash
  python3 -W error -m unittest discover -s .agents/skills/stag-autobid-seeder/tests
  ```
