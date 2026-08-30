import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from selenium import webdriver
from selenium.common.exceptions import JavascriptException, NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

OPTIONS_PATH = Path("/data/options.json")
STATUS_PATH = Path("/data/status.json")
COINS_URL = "https://www.aliexpress.com/p/coin-pc-index/index.html"
PERSISTENT_NOTIFICATION_ID = "aliexpress_coins_failure"
OK_STATES = {"success", "already_done"}


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


def mobile_push(entity_id, message):
    if ha_service("notify", "send_message", {
        "entity_id": entity_id,
        "title": "AliExpress 코인 출석 실패",
        "message": message,
    }):
        log("INFO", f"Mobile notification sent to {entity_id}.")


def browser_driver():
    opts = Options()
    opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    opts.add_argument("--no-sandbox")
    return webdriver.Chrome(options=opts)


def text_contains(driver, needles):
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        return False
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


def check_and_collect():
    driver = None
    try:
        driver = browser_driver()
        driver.get(COINS_URL)
        WebDriverWait(driver, 25).until(lambda d: d.execute_script("return document.readyState") in ("interactive", "complete"))
        time.sleep(5)

        current = driver.current_url.lower()
        if "login" in current or "signin" in current or text_contains(driver, ["sign in to aliexpress", "로그인"]):
            return "login_required", "AliExpress 로그인이 필요합니다. 앱의 OPEN WEB UI에서 로그인해 주세요."

        collect = find_collect(driver)
        if not collect:
            if text_contains(driver, ["collected", "checked in", "come back tomorrow"]):
                return "already_done", "오늘 코인은 이미 수령한 것으로 보입니다."
            return "collect_not_found", "Coins 페이지에서 Collect 버튼을 찾지 못했습니다."

        before = driver.find_element(By.TAG_NAME, "body").text
        click_element(driver, collect)
        log("INFO", "Collect button clicked.")
        time.sleep(6)
        after = driver.find_element(By.TAG_NAME, "body").text

        # The exact AliExpress UI wording can change. Confirm using several signals.
        if "Collect" not in after or after != before:
            # Re-check page to distinguish a successful UI transition from a login redirect.
            current = driver.current_url.lower()
            if "login" in current or "signin" in current:
                return "login_required", "Collect 후 로그인 화면으로 이동했습니다. 세션을 갱신해 주세요."
            return "success", "Collect 요청 후 Coins 화면이 갱신되었습니다."

        return "uncertain", "Collect를 클릭했지만 성공 여부를 화면에서 확정하지 못했습니다."
    except WebDriverException as exc:
        return "browser_error", str(exc)[:400]
    except Exception as exc:
        return "error", str(exc)[:400]
    finally:
        # Do not quit: driver is attached to the persistent interactive Chromium.
        try:
            if driver:
                driver.close() if False else None
        except Exception:
            pass


def failure_instruction():
    return (
        "Home Assistant에서 AliExpress Coins 앱의 OPEN WEB UI를 열어 "
        "AliExpress에 로그인한 뒤 Coins 화면이 보이는지 확인해 주세요. "
        "브라우저 프로필은 /data/chromium-profile에 계속 보존됩니다."
    )


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
        checked = now_local(options)
        save_status(last_run_at=checked.isoformat(timespec="seconds"), last_result=last_state, last_message=last_message)

        if last_state in OK_STATES:
            log("INFO", f"AliExpress coins OK: {last_state} / {last_message}")
            dismiss_failure()
            save_status(last_run_date=checked.date().isoformat(), unresolved=False, failure_date=None, mobile_notified=False)
            return True

        log("WARNING", f"AliExpress coins failed: {last_state} / {last_message}")

    save_status(unresolved=True, failure_date=now_local(options).date().isoformat(), mobile_notified=False)
    if options.get("notify_on_failure", True):
        persistent_failure(f"{last_state}: {last_message}\n\n{failure_instruction()}")
    return False


def at_time(now, hhmm):
    return now.strftime("%H:%M") == hhmm


def main():
    options = load_options()
    log("INFO", "Starting AliExpress Coins Bot...")
    log("INFO", "Persistent Chromium profile: /data/chromium-profile")
    log("INFO", "Interactive login browser is available through Home Assistant Ingress.")
    log("INFO", f"Daily collection: {options.get('run_time', '00:20')} ({options.get('timezone', 'Asia/Seoul')}); retries +{options.get('retry_1_minutes', 5)}m/+{options.get('retry_2_minutes', 15)}m; mobile alert check: {options.get('mobile_alert_time', '09:10')}")

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
                # One final attempt before bothering the user.
                log("INFO", "Morning unresolved-failure recheck.")
                state, message = check_and_collect()
                save_status(last_result=state, last_message=message)
                if state in OK_STATES:
                    log("INFO", f"Morning recheck recovered: {state} / {message}")
                    dismiss_failure()
                    save_status(last_run_date=today, unresolved=False, failure_date=None, mobile_notified=False)
                else:
                    mobile_push(options.get("mobile_notify_entity", "notify.ky17"), f"{state}: {message}\n{failure_instruction()}")
                    save_status(mobile_notified=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
