# AliExpress Coins Bot

AliExpress 웹의 Daily check-in Coins를 Home Assistant에서 자동으로 수령합니다.

## v0.1.5 주요 기능

- `/data/chromium-profile`에 로그인 상태 영구 보존
- 매일 지정 시각 자동 Collect
- 실패 시 재시도 및 최종 모바일 알림
- 빠른 Ingress 상태/제어 UI
- 로그인 만료 시에만 사용하는 VNC 브라우저
- 수동 로그인/출석 상태 확인
- 수동 출석 테스트
- 버튼 클릭 즉시 작업 중 상태 표시 및 중복 클릭 방지
- 오늘 획득 코인과 현재 코인 잔액 표시
- 자동 출석 성공 시 모바일 성공 알림

성공 알림 예시:

`오늘 +20 코인 수령 완료 · 현재 527 코인 · 연속 1일`

AliExpress 화면 구조가 바뀌면 보상량/잔액 표시는 `확인 불가`가 될 수 있지만, 출석 성공 여부 판정과 실패 알림은 별도로 동작하도록 구성되어 있습니다.


### 21:00 safety reminder
If the bot has not confirmed today's check-in by `manual_reminder_time` (default 21:00), it sends one mobile reminder so you can check in manually before the day ends.
