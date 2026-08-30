# Changelog

## 0.1.4
- Added a configurable 21:00 manual check-in reminder when no successful AliExpress coin check-in has been confirmed for the day.
- Reminder is sent once per day and skipped when `success` or `already_done` is already recorded.
- Added `manual_reminder_time` and `notify_manual_reminder` options.


## 0.1.3

- 상태 확인/출석 테스트 버튼을 누르는 즉시 진행 상태를 표시하고 중복 클릭을 막도록 UI를 개선했습니다.
- 작업 중 버튼 문구를 `상태 확인 중...` 또는 `출석 처리 중...`으로 바꾸고 완료 후 자동으로 화면을 갱신합니다.
- 오늘 획득 코인과 현재 코인 잔액을 best-effort로 읽어 상태 화면에 표시합니다.
- 실제 Collect 전후 잔액 차이를 우선 사용해 오늘 획득량을 계산하고, 잔액 차이를 얻지 못하면 Daily check-in 카드의 오늘 보상값을 사용합니다.
- 자동 출석이 성공하거나 이미 완료된 상태로 확인되면 Home Assistant 모바일 알림으로 오늘 획득량, 현재 잔액, 연속 출석일을 보냅니다.
- `notify_on_success` 옵션을 추가했습니다. 기본값은 `true`입니다.

## 0.1.2

- Selenium이 시스템 Chromium/ChromeDriver를 직접 사용하도록 경로를 명시했습니다.
- `/usr/bin/chromium-browser`와 `/usr/bin/chromedriver`를 사용합니다.

## 0.1.1

- 빠른 Ingress 상태/제어 UI를 추가했습니다.
- VNC는 로그인 갱신용으로 분리했습니다.
- 수동 상태 확인과 수동 출석 테스트를 추가했습니다.

## 0.1.0

- 최초 버전.
