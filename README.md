# AliExpress Home Assistant Apps

Home Assistant에서 AliExpress Daily check-in Coins를 자동 수령하기 위한 App 저장소입니다.

현재 버전: **AliExpress Coins Bot v0.1.5**

앱은 영구 Chromium 프로필을 사용해 로그인 상태를 유지합니다. 평소에는 빠른 Ingress UI에서 상태를 확인하고, AliExpress 로그인이 풀린 경우에만 VNC 로그인 브라우저를 사용합니다.

v0.1.5부터 자동 출석 성공 시 오늘 획득 코인, 현재 코인 잔액, 가능한 경우 연속 출석일을 Home Assistant 모바일 알림으로 전송합니다.


### 21:00 safety reminder
If the bot has not confirmed today's check-in by `manual_reminder_time` (default 21:00), it sends one mobile reminder so you can check in manually before the day ends.
