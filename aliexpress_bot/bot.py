import html
import json
import os
import re
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

import requests
from selenium import webdriver
from selenium.common.exceptions import JavascriptException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

OPTIONS_PATH = Path("/data/options.json")
STATUS_PATH = Path("/data/status.json")
COINS_URL = "https://www.aliexpress.com/p/coin-pc-index/index.html"
PERSISTENT_NOTIFICATION_ID = "aliexpress_coins_failure"
OK_STATES = {"success", "already_done"}
BROWSER_LOCK = threading.Lock()


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_options():
    return load_json(OPTIONS_PATH, {})


def now_local(options=None):
    options = options or load_options()
    return datetime.now(ZoneInfo(options.get("timezone", "Asia/Seoul")))


def fmt_time(value):
    if not value:
        return "아직 없음"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return str(value)


def log(level, message):
    try:
        stamp = now_local().strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"[{stamp}] [{level}] {message}", flush=True)


def save_status(**updates):
    status = load_json(STATUS_PATH, {})
    status.update(updates)
    save_json(STATUS_PATH, status)


def ha_service(domain, service, payload):
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        log("WARNING", "SUPERVISOR_TOKEN is missing.")
        return False
    try:
        r = requests.post(
            f"http://supervisor/core/api/services/{domain}/{service}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        return True
    except Exception as exc:
        log("WARNING", f"Home Assistant service call failed: {exc}")
        return False


def persistent_failure(message):
    if ha_service("persistent_notification", "create", {
        "notification_id": PERSISTENT_NOTIFICATION_ID,
        "title": "AliExpress 코인 출석 실패",
        "message": message,
    }):
        log("INFO", "Persistent failure notification created.")


def dismiss_failure():
    ha_service("persistent_notification", "dismiss", {"notification_id": PERSISTENT_NOTIFICATION_ID})


def mobile_push(entity_id, message, title="AliExpress 코인 출석 실패"):
    if ha_service("notify", "send_message", {
        "entity_id": entity_id,
        "title": title,
        "message": message,
    }):
        log("INFO", f"Mobile notification sent to {entity_id}: {title}")


def parse_int(value):
    if value is None:
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except Exception:
        return None


def success_notification(options, state):
    if not options.get("notify_on_success", True):
        return
    status = load_json(STATUS_PATH, {})
    reward = parse_int(status.get("today_reward"))
    balance = parse_int(status.get("coin_balance"))
    streak = status.get("streak_days")

    if state == "success":
        if reward is not None:
            first = f"오늘 +{reward} 코인 수령 완료"
        else:
            first = "오늘 코인 수령 완료"
    else:
        if reward is not None:
            first = f"오늘 +{reward} 코인 · 이미 수령 완료 상태 확인"
        else:
            first = "오늘 코인은 이미 수령 완료 상태입니다"

    parts = [first]
    if balance is not None:
        parts.append(f"현재 {balance:,} 코인")
    if isinstance(streak, int):
        parts.append(f"연속 {streak}일")
    mobile_push(
        options.get("mobile_notify_entity", "notify.ky17"),
        " · ".join(parts),
        title="AliExpress 코인 출석 완료",
    )


def browser_driver():
    opts = Options()
    opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    opts.binary_location = "/usr/bin/chromium-browser"
    service = Service(executable_path="/usr/bin/chromedriver")
    return webdriver.Chrome(service=service, options=opts)


def page_text(driver):
    try:
        return driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        return ""


def text_contains(driver, needles):
    body = page_text(driver).lower()
    return any(n.lower() in body for n in needles)


def find_collect(driver):
    xpaths = [
        "//button[normalize-space(.)='Collect']",
        "//*[@role='button' and normalize-space(.)='Collect']",
        "//*[normalize-space(text())='Collect']",
    ]
    for xp in xpaths:
        for el in driver.find_elements(By.XPATH, xp):
            try:
                if el.is_displayed() and el.is_enabled():
                    return el
            except Exception:
                continue
    return None


def click_element(driver, el):
    try:
        el.click()
        return
    except Exception:
        pass
    try:
        driver.execute_script("arguments[0].click();", el)
    except JavascriptException as exc:
        raise WebDriverException(str(exc))


def extract_best_effort(body):
    """Best-effort visible-text parsing only. AliExpress UI wording can change."""
    result = {"coin_balance": None, "streak_days": None, "daily_reward": None}
    compact = " ".join(body.split())

    # Prefer the account-balance card over reward-card numbers.
    coin_patterns = [
        r"My\s+coins\s*[:：]?\s*([0-9][0-9,]*)",
        r"내\s*코인\s*[:：]?\s*([0-9][0-9,]*)",
        r"(?:Coins?|코인)\s*[:：]?\s*([0-9][0-9,]*)",
        r"([0-9][0-9,]*)\s*(?:Coins?|코인)",
    ]
    for p in coin_patterns:
        m = re.search(p, compact, re.I)
        if m:
            result["coin_balance"] = parse_int(m.group(1))
            break

    reward_patterns = [
        r"Today[^0-9+]{0,30}\+\s*([0-9][0-9,]*)",
        r"오늘[^0-9+]{0,30}\+\s*([0-9][0-9,]*)",
        r"Daily\s+check-in[^+]{0,120}\+\s*([0-9][0-9,]*)",
    ]
    for p in reward_patterns:
        m = re.search(p, compact, re.I)
        if m:
            result["daily_reward"] = parse_int(m.group(1))
            break

    streak_patterns = [
        r"(?:streak|연속[^0-9]{0,8})\s*([0-9]+)\s*(?:day|days|일)?",
        r"([0-9]+)\s*(?:day|days|일)\s*(?:streak|연속)",
    ]
    for p in streak_patterns:
        m = re.search(p, compact, re.I)
        if m:
            result["streak_days"] = int(m.group(1))
            break
    return result


def inspect_coins_page():
    with BROWSER_LOCK:
        driver = None
        try:
            driver = browser_driver()
            driver.get(COINS_URL)
            WebDriverWait(driver, 25).until(
                lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
            )
            time.sleep(4)

            current = driver.current_url.lower()
            body = page_text(driver)
            if "login" in current or "signin" in current or text_contains(driver, ["sign in to aliexpress", "로그인"]):
                state = "login_required"
                message = "AliExpress 로그인이 필요합니다. 로그인 브라우저를 열어 로그인해 주세요."
                info = {"logged_in": False, "today_status": "로그인 필요"}
            else:
                collect = find_collect(driver)
                if collect:
                    state = "ready"
                    message = "로그인 상태 정상. 오늘 Collect 버튼이 보입니다."
                    info = {"logged_in": True, "today_status": "아직 수령 전"}
                elif text_contains(driver, ["collected", "checked in", "come back tomorrow", "already collected"]):
                    state = "already_done"
                    message = "로그인 상태 정상. 오늘 코인은 이미 수령한 것으로 보입니다."
                    info = {"logged_in": True, "today_status": "수령 완료"}
                else:
                    state = "logged_in_unknown"
                    message = "로그인은 유지되어 있지만 오늘 출석 상태를 화면에서 확정하지 못했습니다."
                    info = {"logged_in": True, "today_status": "확인 불가"}
                parsed = extract_best_effort(body)
                info.update({
                    "coin_balance": parsed.get("coin_balance"),
                    "streak_days": parsed.get("streak_days"),
                    "today_reward": parsed.get("daily_reward"),
                })

            checked = now_local()
            save_status(
                status_checked_at=checked.isoformat(timespec="seconds"),
                login_state=state,
                login_message=message,
                **info,
            )
            log("INFO", f"Manual status check: {state} / {message}")
            return state, message, info
        except Exception as exc:
            message = str(exc)[:400]
            save_status(status_checked_at=now_local().isoformat(timespec="seconds"), login_state="browser_error", login_message=message)
            log("WARNING", f"Manual status check failed: {message}")
            return "browser_error", message, {}


def check_and_collect():
    with BROWSER_LOCK:
        driver = None
        try:
            driver = browser_driver()
            driver.get(COINS_URL)
            WebDriverWait(driver, 25).until(
                lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
            )
            time.sleep(5)

            current = driver.current_url.lower()
            before_body = page_text(driver)
            before_info = extract_best_effort(before_body)
            if "login" in current or "signin" in current or text_contains(driver, ["sign in to aliexpress", "로그인"]):
                return "login_required", "AliExpress 로그인이 필요합니다. 로그인 브라우저를 열어 로그인해 주세요."

            collect = find_collect(driver)
            if not collect:
                save_status(
                    coin_balance=before_info.get("coin_balance"),
                    streak_days=before_info.get("streak_days"),
                    today_reward=before_info.get("daily_reward"),
                    today_status="수령 완료" if text_contains(driver, ["collected", "checked in", "come back tomorrow", "already collected"]) else "확인 불가",
                )
                if text_contains(driver, ["collected", "checked in", "come back tomorrow", "already collected"]):
                    return "already_done", "오늘 코인은 이미 수령한 것으로 보입니다."
                return "collect_not_found", "Coins 페이지에서 Collect 버튼을 찾지 못했습니다."

            click_element(driver, collect)
            log("INFO", "Collect button clicked.")
            time.sleep(6)
            after_body = page_text(driver)
            after_info = extract_best_effort(after_body)

            current = driver.current_url.lower()
            if "login" in current or "signin" in current:
                return "login_required", "Collect 후 로그인 화면으로 이동했습니다. 세션을 갱신해 주세요."

            before_balance = parse_int(before_info.get("coin_balance"))
            after_balance = parse_int(after_info.get("coin_balance"))
            reward = None
            if before_balance is not None and after_balance is not None and after_balance >= before_balance:
                delta = after_balance - before_balance
                if 0 < delta <= 10000:
                    reward = delta
            if reward is None:
                reward = after_info.get("daily_reward") or before_info.get("daily_reward")

            merged_balance = after_balance if after_balance is not None else before_balance
            merged_streak = after_info.get("streak_days") if after_info.get("streak_days") is not None else before_info.get("streak_days")
            save_status(
                coin_balance=merged_balance,
                streak_days=merged_streak,
                today_reward=reward,
                today_status="수령 완료",
            )

            # Prefer explicit post-click signals, with UI-change fallback.
            if text_contains(driver, ["collected", "checked in", "come back tomorrow", "already collected"]):
                return "success", "Collect 후 오늘 수령 완료 상태가 확인되었습니다."
            if find_collect(driver) is None and after_body != before_body:
                return "success", "Collect 후 버튼이 사라지고 Coins 화면이 갱신되었습니다."
            if after_body != before_body:
                return "success", "Collect 요청 후 Coins 화면이 갱신되었습니다."

            return "uncertain", "Collect를 클릭했지만 성공 여부를 화면에서 확정하지 못했습니다."
        except WebDriverException as exc:
            return "browser_error", str(exc)[:400]
        except Exception as exc:
            return "error", str(exc)[:400]


def failure_instruction():
    return (
        "Home Assistant에서 AliExpress Coins 앱을 열고 로그인 상태 확인을 먼저 실행해 주세요. "
        "로그인이 풀린 경우에만 로그인 브라우저를 열어 AliExpress에 로그인하면 됩니다. "
        "브라우저 프로필은 /data/chromium-profile에 계속 보존됩니다."
    )


def record_collect_result(state, message, manual=False):
    checked = now_local()
    updates = {
        "last_run_at": checked.isoformat(timespec="seconds"),
        "last_result": state,
        "last_message": message,
    }
    if manual:
        updates["manual_run_at"] = checked.isoformat(timespec="seconds")
    if state in OK_STATES:
        updates.update({
            "last_run_date": checked.date().isoformat(),
            "unresolved": False,
            "failure_date": None,
            "mobile_notified": False,
        })
    save_status(**updates)


def manual_collect():
    log("INFO", "Manual Collect test requested from Ingress UI.")
    state, message = check_and_collect()
    record_collect_result(state, message, manual=True)
    if state in OK_STATES:
        dismiss_failure()
        log("INFO", f"Manual Collect OK: {state} / {message}")
    else:
        log("WARNING", f"Manual Collect failed: {state} / {message}")
    return state, message


def run_with_retries(options):
    r1 = int(options.get("retry_1_minutes", 5))
    r2 = int(options.get("retry_2_minutes", 15))
    delays = [0, r1 * 60, max(0, (r2 - r1) * 60)]
    last_state, last_message = None, ""

    for attempt, delay in enumerate(delays):
        if delay:
            log("WARNING", f"Attempt failed ({last_state}); retry {attempt} in {delay // 60} minutes.")
            time.sleep(delay)
        log("INFO", "Checking AliExpress daily coin check-in.")
        last_state, last_message = check_and_collect()
        record_collect_result(last_state, last_message)

        if last_state in OK_STATES:
            log("INFO", f"AliExpress coins OK: {last_state} / {last_message}")
            dismiss_failure()
            success_notification(options, last_state)
            return True

        log("WARNING", f"AliExpress coins failed: {last_state} / {last_message}")

    save_status(unresolved=True, failure_date=now_local(options).date().isoformat(), mobile_notified=False)
    if options.get("notify_on_failure", True):
        persistent_failure(f"{last_state}: {last_message}\n\n{failure_instruction()}")
    return False



def send_manual_reminder_if_needed(options, now):
    """At the daily deadline, remind the user if today's check-in has not been confirmed."""
    if not options.get("notify_manual_reminder", True):
        return
    today = now.date().isoformat()
    status = load_json(STATUS_PATH, {})
    if status.get("manual_reminder_date") == today:
        return
    if status.get("last_run_date") == today and status.get("last_result") in OK_STATES:
        save_status(manual_reminder_date=today)
        log("INFO", "21:00 manual reminder skipped: today's AliExpress check-in is already confirmed.")
        return

    last_result = status.get("last_result") or "기록 없음"
    last_message = status.get("last_message") or "오늘 성공 기록이 없습니다."
    mobile_push(
        options.get("mobile_notify_entity", "notify.ky17"),
        f"21:00까지 오늘 AliExpress 코인 출석 성공이 확인되지 않았습니다. 앱에서 직접 출석을 확인해 주세요.\n마지막 상태: {last_result} / {last_message}",
        title="AliExpress 출석 확인 필요",
    )
    save_status(manual_reminder_date=today)
    log("WARNING", "21:00 manual check-in reminder sent: no confirmed success for today.")


def at_time(now, hhmm):
    return now.strftime("%H:%M") == hhmm


def status_badge(status):
    login_state = status.get("login_state")
    if login_state in {"ready", "already_done", "logged_in_unknown"}:
        return "good", "로그인 유지됨"
    if login_state == "login_required":
        return "bad", "로그인 필요"
    return "neutral", "아직 확인 안 함"


def render_ui(message="", message_kind=""):
    status = load_json(STATUS_PATH, {})
    options = load_options()
    badge_class, badge_text = status_badge(status)
    today_status = status.get("today_status", "아직 확인 안 함")
    coin_balance = status.get("coin_balance") or "확인 불가"
    streak = status.get("streak_days")
    streak_text = f"{streak}일" if isinstance(streak, int) else "확인 불가"
    reward = parse_int(status.get("today_reward"))
    reward_text = f"+{reward} 코인" if reward is not None else "확인 불가"
    last_result = status.get("last_result", "아직 없음")
    last_message = status.get("last_message", "")
    alert = ""
    if message:
        cls = "okmsg" if message_kind == "ok" else "warnmsg"
        alert = f'<div class="{cls}">{html.escape(message)}</div>'

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AliExpress Coins Bot</title>
<style>
:root {{ color-scheme: light dark; font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
body {{ margin:0; background:#f4f5f7; color:#202124; }}
.wrap {{ max-width:720px; margin:0 auto; padding:20px; position:relative; }}
.card {{ background:white; border-radius:16px; padding:20px; box-shadow:0 2px 10px rgba(0,0,0,.08); margin-bottom:16px; }}
h1 {{ font-size:24px; margin:0 36px 6px 0; }}
p {{ line-height:1.55; }}
.close {{ position:absolute; right:25px; top:22px; border:0; background:transparent; font-size:28px; cursor:pointer; color:#666; }}
.badge {{ display:inline-block; padding:6px 10px; border-radius:999px; font-weight:700; font-size:13px; }}
.good {{ background:#e8f5e9; color:#1b5e20; }} .bad {{ background:#ffebee; color:#b71c1c; }} .neutral {{ background:#eceff1; color:#455a64; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:14px; }}
.item {{ border:1px solid #e5e7eb; border-radius:12px; padding:13px; }} .label {{ color:#6b7280; font-size:12px; }} .value {{ font-size:17px; font-weight:700; margin-top:4px; }}
.actions {{ display:grid; gap:10px; }}
button,.btn {{ width:100%; box-sizing:border-box; border:0; border-radius:11px; padding:13px 14px; font-size:15px; font-weight:700; cursor:pointer; text-align:center; text-decoration:none; display:block; }}
button:disabled {{ opacity:.65; cursor:wait; }}
.busy {{ display:none; margin:12px 0 0; border-radius:10px; padding:12px; background:#e3f2fd; color:#0d47a1; font-weight:700; }}
.spinner {{ display:inline-block; width:14px; height:14px; border:2px solid currentColor; border-right-color:transparent; border-radius:50%; vertical-align:-2px; margin-right:7px; animation:spin .8s linear infinite; }}
@keyframes spin {{ to {{ transform:rotate(360deg); }} }}
.primary {{ background:#e64a19; color:white; }} .secondary {{ background:#e8eaed; color:#202124; }} .danger {{ background:#fff3e0; color:#bf360c; }}
.note {{ color:#5f6368; font-size:13px; }} .okmsg,.warnmsg {{ border-radius:10px; padding:12px; margin:12px 0; }} .okmsg {{ background:#e8f5e9; }} .warnmsg {{ background:#fff3e0; }}
small {{ color:#6b7280; }}
@media (prefers-color-scheme:dark) {{ body{{background:#111827;color:#f3f4f6}} .card{{background:#1f2937}} .item{{border-color:#374151}} .secondary{{background:#374151;color:#f3f4f6}} .note,small,.label{{color:#9ca3af}} .close{{color:#d1d5db}} }}
</style></head><body><div class="wrap">
<button class="close" onclick="try{{window.parent.location.href='/'}}catch(e){{history.back()}}" aria-label="닫기">×</button>
<div class="card"><h1>AliExpress Coins Bot</h1>
<p>평소에는 이 화면에서 상태만 확인하면 됩니다. <b>느린 VNC 로그인 브라우저는 AliExpress 로그인이 풀렸을 때만</b> 열어 주세요.</p>
{alert}
<span class="badge {badge_class}">{badge_text}</span>
<div class="grid">
<div class="item"><div class="label">오늘 출석</div><div class="value">{html.escape(str(today_status))}</div></div>
<div class="item"><div class="label">오늘 획득</div><div class="value">{html.escape(reward_text)}</div></div>
<div class="item"><div class="label">현재 코인</div><div class="value">{html.escape(str(coin_balance))}</div></div>
<div class="item"><div class="label">연속 출석</div><div class="value">{html.escape(streak_text)}</div></div>
<div class="item"><div class="label">마지막 상태 확인</div><div class="value" style="font-size:13px">{html.escape(fmt_time(status.get('status_checked_at')))}</div></div>
</div></div>
<div class="card"><div class="actions">
<button id="checkBtn" class="primary" type="button" onclick="runAction('check', this)">지금 로그인 · 출석 상태 확인</button>
<button id="collectBtn" class="danger" type="button" onclick="if(confirm('오늘 미출석이면 실제 Collect를 실행합니다. 계속할까요?')) runAction('collect', this)">지금 출석 테스트</button>
<a id="vncBtn" class="btn secondary" href="vnc/vnc.html?autoconnect=1&amp;resize=scale&amp;path=vnc/websockify">로그인 브라우저 열기</a>
</div>
<div id="busy" class="busy"><span class="spinner"></span><span id="busyText">처리 중...</span></div>
<p class="note">상태 확인과 출석 테스트는 AliExpress 페이지를 실제로 확인하므로 10–20초 정도 걸릴 수 있습니다. 버튼을 누르면 즉시 진행 상태가 표시되고 완료될 때까지 중복 클릭은 막힙니다.</p>
<p class="note">로그인 브라우저에서 로그인을 마치면 그냥 닫아도 됩니다. Chromium 프로필은 /data/chromium-profile에 저장되어 앱 재시작 후에도 유지됩니다.</p></div>
<div class="card"><b>자동 실행</b><p class="note">매일 {html.escape(str(options.get('run_time','00:20')))} ({html.escape(str(options.get('timezone','Asia/Seoul')))}) · 재시도 +{options.get('retry_1_minutes',5)}분 / +{options.get('retry_2_minutes',15)}분 · 실패 확인 {html.escape(str(options.get('mobile_alert_time','09:10')))} · 수동 확인 알림 {html.escape(str(options.get('manual_reminder_time','21:00')))}</p>
<div class="label">마지막 출석 실행</div><div>{html.escape(fmt_time(status.get('last_run_at')))}</div>
<div class="label" style="margin-top:10px">마지막 결과</div><div><b>{html.escape(str(last_result))}</b> {html.escape(str(last_message))}</div></div>
</div>
<script>
async function runAction(action, btn) {{
  const checkBtn = document.getElementById('checkBtn');
  const collectBtn = document.getElementById('collectBtn');
  const vncBtn = document.getElementById('vncBtn');
  const busy = document.getElementById('busy');
  const busyText = document.getElementById('busyText');
  checkBtn.disabled = true; collectBtn.disabled = true;
  vncBtn.style.pointerEvents = 'none'; vncBtn.style.opacity = '.6';
  busy.style.display = 'block';
  busyText.textContent = action === 'collect' ? '출석 처리 중... 잠시 기다려 주세요.' : '로그인 · 출석 상태 확인 중... 잠시 기다려 주세요.';
  btn.dataset.oldText = btn.textContent;
  btn.textContent = action === 'collect' ? '출석 처리 중...' : '상태 확인 중...';
  try {{
    const body = new URLSearchParams(); body.set('do', action); body.set('ajax', '1');
    const res = await fetch('action', {{method:'POST', headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'fetch'}}, body}});
    const data = await res.json();
    busyText.textContent = data.message || '완료되었습니다. 화면을 갱신합니다.';
    setTimeout(() => window.location.reload(), 350);
  }} catch (e) {{
    busyText.textContent = '요청 처리 중 오류가 발생했습니다: ' + e;
    checkBtn.disabled = false; collectBtn.disabled = false;
    vncBtn.style.pointerEvents = ''; vncBtn.style.opacity = '';
    btn.textContent = btn.dataset.oldText || btn.textContent;
  }}
}}
</script>
</body></html>"""


class UIHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send_html(self, content, status=200):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.split("?", 1)[0] in ("/", ""):
            self._send_html(render_ui())
        else:
            self._send_html(render_ui("알 수 없는 경로입니다.", "warn"), 404)

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/action":
            self._send_html(render_ui("알 수 없는 요청입니다.", "warn"), 404)
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length).decode("utf-8", "replace")
        params = parse_qs(body)
        action = params.get("do", [""])[0]
        ajax = params.get("ajax", [""])[0] == "1" or self.headers.get("X-Requested-With") == "fetch"
        if action == "check":
            state, message, _ = inspect_coins_page()
            kind = "ok" if state in {"ready", "already_done", "logged_in_unknown"} else "warn"
            if ajax:
                self._send_json({"state": state, "message": message, "ok": kind == "ok"})
            else:
                self._send_html(render_ui(message, kind))
        elif action == "collect":
            state, message = manual_collect()
            # Refresh read-only status after manual collect so dashboard reflects the result.
            inspect_coins_page()
            kind = "ok" if state in OK_STATES else "warn"
            if ajax:
                self._send_json({"state": state, "message": message, "ok": kind == "ok"})
            else:
                self._send_html(render_ui(message, kind))
        else:
            if ajax:
                self._send_json({"state": "bad_request", "message": "지원하지 않는 작업입니다.", "ok": False}, 400)
            else:
                self._send_html(render_ui("지원하지 않는 작업입니다.", "warn"), 400)


def start_ui_server():
    server = ThreadingHTTPServer(("127.0.0.1", 8098), UIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log("INFO", "Ingress control UI listening behind nginx on port 8099.")
    return server


def main():
    options = load_options()
    log("INFO", "Starting AliExpress Coins Bot...")
    log("INFO", "Persistent Chromium profile: /data/chromium-profile")
    log("INFO", "Ingress opens the fast control/status UI. VNC is reserved for login renewal.")
    log("INFO", f"Daily collection: {options.get('run_time', '00:20')} ({options.get('timezone', 'Asia/Seoul')}); retries +{options.get('retry_1_minutes', 5)}m/+{options.get('retry_2_minutes', 15)}m; mobile alert check: {options.get('mobile_alert_time', '09:10')}; manual reminder: {options.get('manual_reminder_time', '21:00')}")
    start_ui_server()

    if options.get("run_on_start", False):
        run_with_retries(options)

    last_minute = None
    while True:
        options = load_options()
        now = now_local(options)
        minute_key = now.strftime("%Y-%m-%d %H:%M")
        if minute_key != last_minute:
            last_minute = minute_key
            status = load_json(STATUS_PATH, {})
            today = now.date().isoformat()

            if at_time(now, options.get("run_time", "00:20")) and status.get("last_run_date") != today:
                run_with_retries(options)

            status = load_json(STATUS_PATH, {})
            if at_time(now, options.get("mobile_alert_time", "09:10")) and status.get("unresolved") and status.get("failure_date") == today and not status.get("mobile_notified"):
                log("INFO", "Morning unresolved-failure recheck.")
                state, message = check_and_collect()
                record_collect_result(state, message)
                if state in OK_STATES:
                    log("INFO", f"Morning recheck recovered: {state} / {message}")
                    dismiss_failure()
                    success_notification(options, state)
                else:
                    mobile_push(options.get("mobile_notify_entity", "notify.ky17"), f"{state}: {message}\n{failure_instruction()}")
                    save_status(mobile_notified=True)

            status = load_json(STATUS_PATH, {})
            if at_time(now, options.get("manual_reminder_time", "21:00")) and status.get("manual_reminder_date") != today:
                send_manual_reminder_if_needed(options, now)
        time.sleep(5)


if __name__ == "__main__":
    main()
