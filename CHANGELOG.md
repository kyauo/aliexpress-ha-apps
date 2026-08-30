# Changelog

## 0.1.2
- Fix Selenium connection to the already-running Chromium instance by using the packaged Alpine chromedriver explicitly.
- Pin Chromium binary path to `/usr/bin/chromium-browser`.
- Avoid Selenium Manager attempting to download or discover a Chrome driver inside the Home Assistant App container.


## v0.1.1

- Replaced direct noVNC Ingress landing page with a lightweight status/control dashboard.
- Added login and today's check-in status check button.
- Added manual Collect test button with confirmation.
- Moved noVNC behind a separate **로그인 브라우저 열기** button for login renewal only.
- Added explicit post-login guidance.
- Added best-effort current coin balance and streak display.
- Added last status-check and last collection timestamps.
- Added close button to the Ingress dashboard.
- Kept the persistent Chromium profile under `/data/chromium-profile`.
- Kept timestamped KST logs and existing retry/notification schedule.
