# AliExpress Coins Bot v0.1.2

Home Assistant App that keeps a persistent Chromium profile and collects the AliExpress daily browser coin check-in.

## v0.1.2 workflow

OPEN WEB UI now opens a lightweight control/status page instead of noVNC directly.

- **지금 로그인 · 출석 상태 확인**: checks the stored browser session and today's Collect state without intentionally collecting.
- **지금 출석 테스트**: if Collect is available, performs the real Collect action.
- **로그인 브라우저 열기**: opens the slower noVNC browser only when login renewal is necessary.
- Login profile remains in `/data/chromium-profile` across App restarts and upgrades.

Coin balance and streak are best-effort values parsed from visible AliExpress page text. If AliExpress changes its UI, they may show `확인 불가` while the core Collect automation can still work.
