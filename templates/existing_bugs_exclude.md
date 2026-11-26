# Already Reported Bugs — DO NOT DUPLICATE

All agents MUST cross-check every candidate finding against this list before reporting.
Only report **genuinely NEW** bugs, OR **broken/incomplete regressions on recently Resolved tickets (`OP-1953`, `OP-1965`, `OP-1978`, `OP-2006`, `OP-2008`)** with concrete proof!

## Global Home (`/home`) — Already Reported
- `OP-1663` / `BUG-018`: Mobile drawer fullscreen with no close button
- `OP-1664` / `BUG-019` (Fixed in `OP-1978`? Verify if fixed or new edge case): Drawer currency/language dropdown clipped off-screen & double-click desync
- `OP-1665` / `BUG-021`: "Đăng ký làm Đối Tác" pointing to staging URL on prod; Support/About links hardcoding `en-US` on `vi-VN/home`
- `OP-1666` / `BUG-022`: Clicking "Lịch sử" (History) as Guest silently closes drawer with zero feedback
- `OP-1667` / `BUG-023`: Hero request form empty check-in/check-out bypasses validation, missing date error text, 14-day max date lock, squashed inline error on `<1440px`
- `OP-1668` / `BUG-025`: Hero "Lưu trú" button hardcoded 466px width overflowing mobile + 0px horizontal padding `<1440px`
- `OP-1669` / `BUG-026`: Destination carousel unclamped parallax 73px blank strip & empty card back face
- `OP-1670` / `BUG-027`: Partner Network cards, Inspiration/Community CTAs & Marketplace cards `aria-disabled="true"`
- `OP-1671` / `BUG-028`: Signed-in hardcoded drawer badge `"1"`, unclipped floating bell, duplicate notification API calls, FocusTrap warning
- `OP-1760` / `BUG-016`: Home page horizontal overflow on mobile
- `OP-1761` / `BUG-017`: Welcome popup "Explore accommodation" redirects back to home
- `OP-1769` / `BUG-035`: Title overlapping description in "How the marketplace works" at 412px
- `OP-1773` / `BUG-039`: Duplicate 2 headers when navigating back to home from Travel Inspiration
- `OP-1775` / `BUG-041`: 2 blurred gaps when opening hamburger drawer at `<=756px`
- `OP-1776` / `BUG-042`: "Trung tâm đối tác" and "Lưu trú" touching on header at 1240px
- `OP-1777` / `BUG-043`: Bell icon suddenly appearing offscreen after clicking Notification in drawer
- `OP-1781` / `BUG-046`: "Log in" action disappears on `<=1439px` with 222px blank deadspace on mobile (Check if fixed by `OP-2006`!)
- `OP-1782` / `BUG-047`: Mobile hamburger drawer overflows off left viewport edge `-10px` to `-25px` on `<=399px`
- `OP-1783` / `BUG-048`: Hero Travelers popover hardcodes `left: 16px` & clamps height hiding Cancel/OK
- `OP-1784` / `BUG-049`: Hero Property Type popover clips Clear/Done footer buttons on `1440x900`
- `OP-1785` / `BUG-050`: Destination carousel featured card locked at `620x316px` overflows mobile/tablet carousel slicing "Rome"
- `OP-1786` / `BUG-051`: Partner Network editorial photo `.gns-home-partners-photo` locked at `563x237px` on `758-1439px`
- `OP-1944`: Destination search box missing keyword search & dropdown too narrow (1-2 rows) (Addressed in `OP-1953`)

## Auth / Login / Signup / Forgot Password — Already Reported
- `OP-1755` / `BUG-009`: Login page header "Accommodation" clipped on narrow screen
- `OP-1756` / `BUG-012`: Floating action buttons overlap login and sign-up form controls
- `OP-1757` / `BUG-013`: Google Play download badge partially clipped on mobile
- `BUG-010`: Forgot Password showing Sign Up guide content
- `BUG-052`: Wrong password login error stored inside Notification bell list

## Accommodation / Bidding / Offers — Already Reported
- `OP-1749` / `BUG-001`: Inconsistent currency display across offers (USD/KRW)
- `OP-1750` / `BUG-004`: Your Stay form missing dropdown list
- `OP-1751` / `BUG-005`: Cannot cancel request via "x" after clicking "+"
- `OP-1753` / `BUG-007`: Delayed form rendering switching tabs
- `OP-1758` / `BUG-014`: Location dropdown exposes raw GeoNames category header
- `OP-1759` / `BUG-015`: Your Stay dropdown flashes and auto-closes
- `OP-1763` / `OP-1771` / `BUG-024` / `BUG-037`: Can enter payment page of expired/rejected offer via image click
- `OP-1765` / `BUG-030`: Detail & payment screen always displays KRW despite USD selection
- `OP-1770` / `BUG-036`: Clicking bidding room jumps to photo gallery instead of overview
- `OP-1772` / `BUG-038`: Tutorial scrolls misaligned at step 2/5 and highlights wrong targets at 3,4,5
- `OP-1774` / `BUG-040`: Text overlapping image at `<=698px` on Partner page
- `OP-1778` / `BUG-044`: Review modal clipped at top on iPhone SE `375x667`
- `OP-1787` / `BUG-053`: Korea LocationPicker sends shifted codes causing `400 INVALID_DISTRICT_CODE` / `INVALID_CITY_CODE`

## Payment / History / Receipt / Notifications / Linked Accounts / AI — Already Reported
- `OP-1762` / `BUG-020`: Cannot distinguish read vs unread notifications
- `OP-1764` / `BUG-029` / `BUG-002`: Clicking notification redirects to home / resets locale from `vi-VN` to `en-US`
- `OP-1788`..`OP-1793`: Account Link Backend API bugs (`BUG-BE-01`..`BUG-BE-06`)
- `OP-1814`..`OP-1820`: Payment PayPal E2E & Receipt/History post-payment bugs (`BUG-PAY-01`..`BUG-PAY-07`: deadlock on popup close, `/payment/fail` hidden buttons & broken retry link, dual stacked checkout modals + Escape key, DD/MM/YYYY date flip in checkout modal, 109-day stale FX rates & `"KWR"`, future paid stay marked Completed + Receipt Room/Nights:1 + decimal KRW, deposit API leaking `paypalData`)
- `OP-1928`..`OP-1940`: Agents page React #418, `<html lang="en">`, Agents step 3 missing links, Agents GET form, Street Address border; AI Planner & AI Chatbot & AI Ticket bugs
- `OP-1947`..`OP-1964`: Staging API security/validation bugs (`API_BUGS`)

## Recently Resolved Features (Check for Regressions & New Edge-Case Bugs!)
- `OP-1953` (Resolved 2026-11-19): `[Global Home] Fix Destination Search Dropdown Height Glitch and Mouse Wheel Scroll Trapping`
- `OP-1965` (Resolved 2026-11-19): `[Customer Web][Bidding] Fix Incorrect No-Bid Mascot Sticker Art for th-TH and en-SG`
- `OP-1978` (Resolved 2026-11-20): `[Customer Web][Global Home] Fix Drawer Currency Overflow, Floating Popups on Scroll, and Hero Form Input Target Area`
- `OP-2006` (Resolved 2026-11-23): `[Customer Web][Global Home] Update Login to Login/Signup and add App download entry in header & hamburger drawer (7 locales)`
- `OP-2008` (Resolved 2026-11-23): `[Web] Implement /[locale]/app-download landing page, OS-aware QR redirect, and 7-locale i18n`
