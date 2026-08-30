# AliExpress Coins Bot

## First setup

1. Start the App.
2. Open **OPEN WEB UI**.
3. Choose **로그인 브라우저 열기** only for the initial AliExpress login.
4. Complete the login in the noVNC Chromium window and close it when the account is visibly logged in.
5. Return to the control UI and press **지금 로그인 · 출석 상태 확인**.

The Chromium profile is stored under `/data/chromium-profile`, so a normal App restart should preserve the AliExpress login.

## Normal operation

The control UI is intended for normal use. noVNC is intentionally separated because it is slow on Home Assistant Yellow and is only needed for login renewal.

The App runs the daily Collect at the configured time, retries twice, and can notify Home Assistant if the failure remains unresolved.

## Manual buttons

- **지금 로그인 · 출석 상태 확인** does not intentionally click Collect. It verifies that AliExpress is logged in and detects whether the Collect button is visible.
- **지금 출석 테스트** may perform the real daily Collect if today's button is available.

The UI's coin balance and streak values are best-effort visual parsing and are not used as the primary success condition.
