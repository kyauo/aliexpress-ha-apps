# AliExpress Coins Bot

Home Assistant App that keeps a real Chromium profile and automatically clicks the AliExpress web Daily check-in `Collect` button.

## First setup

1. Install and start the App.
2. Click **OPEN WEB UI**.
3. A Chromium window running inside the App is shown through noVNC.
4. Log in to AliExpress normally in that browser.
5. Open the Coins page and make sure the Daily check-in card is visible.
6. Leave the App running. The browser profile is stored in `/data/chromium-profile` and reused after restarts/updates.

The scheduled bot navigates to the Coins page by itself, finds `Collect`, clicks it and records the result.

## Important

AliExpress changes its UI and anti-bot logic frequently. v0.1.0 is intentionally a first test build. If the browser page layout changes, the selector may need an update.
