# AliExpress Coins Bot — Home Assistant App

## What it does

- Runs a real Chromium browser inside Home Assistant.
- Keeps the browser profile under `/data/chromium-profile`.
- Provides the browser through Home Assistant Ingress/noVNC for manual login when required.
- At the configured time, navigates to the AliExpress Coins page and clicks `Collect`.
- Retries after the configured delays.
- Creates a Home Assistant persistent notification after final failure.
- Performs a morning recheck and can send a mobile notification if the failure remains unresolved.
- Every log entry includes local date/time and timezone.

## Why a real browser?

The AliExpress web check-in request uses MTOP request signing and browser security values. Letting AliExpress's own JavaScript run inside Chromium is more robust than trying to reimplement those values in Python.

## First login

Open the App's **OPEN WEB UI**. The noVNC screen is the same Chromium instance the scheduler later controls. Sign in to your own AliExpress account there. Do not place passwords in App Configuration.

## Success criteria for the first test

When `run_on_start` is temporarily enabled or the scheduled time arrives, the logs should include:

```text
[YYYY-MM-DD HH:MM:SS KST] [INFO] Checking AliExpress daily coin check-in.
[YYYY-MM-DD HH:MM:SS KST] [INFO] Collect button clicked.
[YYYY-MM-DD HH:MM:SS KST] [INFO] AliExpress coins OK: success / ...
```

If today's reward was already claimed, it should report `already_done` instead.
