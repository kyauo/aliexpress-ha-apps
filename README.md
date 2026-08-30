# AliExpress HA Apps

Home Assistant App repository for AliExpress automation.

## Included app

### AliExpress Coins Bot v0.1.0

Uses a persistent Chromium profile to open the AliExpress Coins page and perform the daily check-in through the normal web interface. Home Assistant Ingress exposes the browser through noVNC for the initial AliExpress login and later login renewal when required.

## Repository layout

```text
repository.yaml
README.md
aliexpress_bot/
```

## Home Assistant installation

1. Create/publish this repository on GitHub.
2. Add the repository URL to Home Assistant's App store repositories.
3. Refresh/check for updates.
4. Install **AliExpress Coins Bot**.
5. Start the App and use **Open Web UI** for the initial AliExpress login.

The Chromium profile is persisted under the App's `/data` directory so normal App restarts and upgrades retain the browser session.
