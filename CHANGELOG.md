# Changelog

## 0.1.5
- Prevent the control UI from spinning indefinitely: 55 s request timeout and 60 s watchdog reload.
- Keep action buttons disabled immediately while Selenium work is active, then always return to a usable status screen.
- Make coin-balance parsing conservative so streak/reward numbers are no longer misreported as the account balance. Unknown is preferred to a false value.
- Repository display name standardized to `KY Home Assistant Apps`.
- Retains 21:00 manual reminder, success notifications, persistent Chromium profile, and daily retry schedule.
