# AliExpress Coins Bot 사용법

## 최초 설정

1. App을 시작합니다.
2. OPEN WEB UI를 엽니다.
3. 로그인이 필요할 때만 `로그인 브라우저 열기`를 누릅니다.
4. VNC 안의 Chromium에서 AliExpress에 로그인합니다.
5. 로그인이 끝나면 VNC 화면은 닫아도 됩니다. 프로필은 `/data/chromium-profile`에 유지됩니다.

## 평소 사용

OPEN WEB UI에서 `지금 로그인 · 출석 상태 확인`으로 로그인/출석 상태를 확인할 수 있습니다. `지금 출석 테스트`는 오늘 미출석이면 실제 Collect를 실행합니다.

v0.1.3부터 두 버튼은 누르는 즉시 작업 중 표시로 바뀌며, Selenium 확인이 끝날 때까지 중복 클릭이 차단됩니다.

## 모바일 성공 알림

`notify_on_success: true`이면 자동 출석 성공 시 `mobile_notify_entity`로 성공 알림을 보냅니다.

가능한 경우 다음 정보를 포함합니다.

- 오늘 획득 코인
- 현재 코인 잔액
- 연속 출석일

실제 Collect 전후 코인 잔액을 모두 읽을 수 있으면 그 차이를 오늘 획득량으로 우선 사용합니다. 잔액 차이를 읽지 못하면 Daily check-in 카드에 표시된 오늘 보상량을 사용합니다. AliExpress UI 변경으로 숫자를 읽지 못한 경우 해당 항목은 생략됩니다.

수동 `지금 출석 테스트`는 반복 테스트로 인한 알림 스팸을 막기 위해 성공 모바일 알림을 보내지 않습니다. 자동 스케줄 실행과 오전 실패 복구 성공 시에만 성공 알림을 보냅니다.

- 21:00 manual reminder: if no successful or already-confirmed check-in exists for the current day, send a mobile reminder to check in manually.
