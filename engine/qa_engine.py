import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pywinauto import Desktop
from pywinauto.keyboard import send_keys


# ============================================================
# PROJECT CONFIGURATION
# ============================================================

# here we tell the engine This is the application I'm testing.

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TEST_CASES_FILE = PROJECT_ROOT / "test_cases" / "tests.yaml"

REPORTS_DIR = PROJECT_ROOT / "reports"
SCREENSHOTS_DIR = REPORTS_DIR / "screenshots"

APP_PATH = Path(r"D:\SendipadPOS\SENDiPADPOS.exe")
APP_PROCESS = "SENDiPADPOS.exe"
APP_TITLE = "SENDiPAD POS"

DEFAULT_TIMEOUT = 15
UI_RETRIES = 3
RETRY_DELAY = 0.5

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env")


# ============================================================
# YAML LOADER
# ============================================================

def load_test_cases():
    """Load test cases from YAML."""

    if not TEST_CASES_FILE.exists():
        raise FileNotFoundError(
            f"Test cases file not found: {TEST_CASES_FILE}"
        )

    with open(TEST_CASES_FILE, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not data or "test_cases" not in data:
        raise ValueError(
            "tests.yaml must contain 'test_cases'."
        )

    return data["test_cases"]


# ============================================================
# VALUE RESOLUTION
# ============================================================

def resolve_value(value):
    """
    Resolve environment variables.

    Example:
        ${SENDIPAD_PIN}
    """

    if not isinstance(value, str):
        return value

    if value.startswith("${") and value.endswith("}"):

        variable_name = value[2:-1]

        result = os.getenv(variable_name)

        if result is None:
            raise ValueError(
                f"Environment variable '{variable_name}' "
                f"is not defined."
            )

        return result

    return value


# ============================================================
# APPLICATION CONTROL
# ============================================================


def stop_application():

    print("[APP] Stopping SENDiPAD...")

    subprocess.run(
        ["taskkill", "/F", "/IM", APP_PROCESS],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    time.sleep(2)


def start_application():

    print("[APP] Starting SENDiPAD...")

    if not APP_PATH.exists():
        raise FileNotFoundError(
            f"Application not found: {APP_PATH}"
        )

    subprocess.Popen(
        [str(APP_PATH)],
        cwd=str(APP_PATH.parent)
    )

    deadline = time.time() + 20

    while time.time() < deadline:

        try:

            app = Desktop(
                backend="uia"
            ).window(
                title=APP_TITLE
            )

            if app.exists() and app.is_visible():

                try:
                    app.set_focus()
                except Exception:
                    pass

                time.sleep(2)

                print("[APP] SENDiPAD is ready.")

                return app

        except Exception:
            pass

        time.sleep(0.5)

    raise TimeoutError(
        "SENDiPAD window did not appear within 20 seconds."
    )


def prepare_application(state):

    """
    Prepare SENDiPAD before every test.

    Supported states:
        fresh_start
        login_screen
        logged_in
    """

    print(f"[SETUP] Application state: {state}")

    stop_application()

    app = start_application()

    if state in ("fresh_start", "login_screen"):
        return app

    if state == "logged_in":

        login_if_needed(app)

        return app

    raise ValueError(
        f"Unsupported application state: {state}"
    )


# ============================================================
# ROBUST CONTROL FINDING
# ============================================================

def find_control(
    app,
    target,
    control_type=None,
    timeout=DEFAULT_TIMEOUT
):
    """
    Find a UI control using several retries.

    This is intentionally generic.
    It does not contain any TC-specific logic.
    """

    target = resolve_value(target)

    last_error = None

    for attempt in range(1, UI_RETRIES + 1):

        try:

            if control_type:

                control = app.child_window(
                    title=target,
                    control_type=control_type
                )

            else:

                control = app.child_window(
                    title=target
                )

            control.wait(
                "visible",
                timeout=timeout
            )

            return control

        except Exception as error:

            last_error = error

            print(
                f"[UI] Could not find '{target}' "
                f"(attempt {attempt}/{UI_RETRIES})"
            )

            time.sleep(RETRY_DELAY)

    raise RuntimeError(
        f"Unable to find UI control '{target}'. "
        f"Last error: {last_error}"
    )


def control_exists(
    app,
    target,
    control_type=None,
    timeout=3
):
    """
    Check whether a UI control exists.

    Returns:
        True  -> control exists
        False -> control was checked and is not present

    Important:
        This function distinguishes a normal "not found"
        result from an automation failure.
    """

    target = resolve_value(target)

    try:

        if control_type:
            control = app.child_window(
                title=target,
                control_type=control_type
            )
        else:
            control = app.child_window(
                title=target
            )

        return control.exists(
            timeout=timeout
        )

    except Exception as error:

        raise RuntimeError(
            f"Could not determine whether UI control "
            f"'{target}' exists: {error}"
        )

    try:

        control = find_control(
            app,
            target,
            control_type,
            timeout=3
        )

        return control.exists()

    except Exception:

        return False


# ============================================================
# ROBUST CLICK
# ============================================================

def click_control(control):

    last_error = None

    for attempt in range(1, UI_RETRIES + 1):

        try:

            try:
                control.set_focus()
            except Exception:
                pass

            time.sleep(0.2)

            control.click_input()

            return

        except Exception as error:

            last_error = error

            print(
                f"[UI] Click failed "
                f"(attempt {attempt}/{UI_RETRIES})"
            )

            time.sleep(RETRY_DELAY)

    raise RuntimeError(
        f"Unable to click control. "
        f"Last error: {last_error}"
    )


# ============================================================
# ROBUST TEXT ENTRY
# ============================================================

def enter_text(control, value):

    value = str(value)

    last_error = None

    for attempt in range(1, UI_RETRIES + 1):

        try:

            try:
                control.set_focus()
            except Exception:
                pass

            time.sleep(0.3)

            # First method: native edit control
            try:

                control.set_edit_text(value)

                time.sleep(0.3)

                return

            except Exception as first_error:

                last_error = first_error

            # Second method: keyboard fallback

            try:

                control.click_input()

                time.sleep(0.2)

                send_keys("^a")

                send_keys(value)

                time.sleep(0.3)

                return

            except Exception as second_error:

                last_error = second_error

        except Exception as error:

            last_error = error

        print(
            f"[UI] Text entry failed "
            f"(attempt {attempt}/{UI_RETRIES})"
        )

        time.sleep(RETRY_DELAY)

    raise RuntimeError(
        f"Unable to enter text. "
        f"Last error: {last_error}"
    )


# ============================================================
# GENERIC ACTIONS
# ============================================================

def action_start_application(app, step):

    return app


def action_stop_application(app, step):

    stop_application()

    return None


def action_click(app, step):

    target = step.get("target")

    if not target:
        raise ValueError(
            "click action requires 'target'."
        )

    control = find_control(
        app,
        target
    )

    click_control(control)

    return app


def action_enter(app, step):

    target = step.get("target")
    value = step.get("value")

    if not target:
        raise ValueError(
            "enter action requires 'target'."
        )

    if value is None:
        raise ValueError(
            "enter action requires 'value'."
        )

    value = resolve_value(value)

    control = find_control(
        app,
        target,
        control_type="Edit"
    )

    enter_text(
        control,
        value
    )

    return app


def action_wait(app, step):

    seconds = float(
        step.get("seconds", 1)
    )

    time.sleep(seconds)

    return app


def action_verify_window(app, step):

    expected_title = resolve_value(
        step.get("target")
    )

    if not expected_title:
        raise ValueError(
            "verify_window requires 'target'."
        )

    actual_title = app.window_text()

    if actual_title != expected_title:

        raise AssertionError(
            f"Expected window '{expected_title}', "
            f"found '{actual_title}'."
        )

    return app


def action_verify(app, step):

    target = step.get("target")

    condition = step.get(
        "condition",
        "visible"
    )

    if not target:
        raise ValueError(
            "verify action requires 'target'."
        )

    exists = control_exists(
        app,
        target
    )

    if condition == "visible":

        if not exists:
            raise AssertionError(
                f"Expected '{target}' to be visible."
            )

    elif condition == "not_visible":

        if exists:
            raise AssertionError(
                f"Expected '{target}' "
                f"not to be visible."
            )

    else:

        raise ValueError(
            f"Unsupported condition: {condition}"
        )

    return app


def action_screenshot(
    app,
    step,
    test_id
):

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    name = step.get(
        "name",
        "evidence"
    )

    filename = (
        f"{test_id}_{name}_{timestamp}.png"
    )

    screenshot_path = (
        SCREENSHOTS_DIR / filename
    )

    try:

        image = app.capture_as_image()

        image.save(
            screenshot_path
        )

        print(
            f"[EVIDENCE] {screenshot_path}"
        )

        return app, str(screenshot_path)

    except Exception as error:

        print(
            f"[WARNING] Screenshot failed: {error}"
        )

        return app, None


# ============================================================
# LOGIN HELPER
# ============================================================

def login_if_needed(app):

    pin_field = app.child_window(
        title="Enter PIN",
        control_type="Edit"
    )

    try:

        pin_field.wait(
            "visible",
            timeout=3
        )

    except Exception:

        # Already logged in.
        return app

    pin = os.getenv(
        "SENDIPAD_PIN"
    )

    if not pin:

        raise ValueError(
            "SENDIPAD_PIN is missing from .env"
        )

    print("[LOGIN] Entering valid PIN...")

    enter_text(
        pin_field,
        pin
    )

    login_button = find_control(
        app,
        "Login",
        control_type="Button"
    )

    click_control(
        login_button
    )

    deadline = time.time() + DEFAULT_TIMEOUT

    while time.time() < deadline:

        try:

            if not pin_field.exists():

                time.sleep(1)

                print(
                    "[LOGIN] Login successful."
                )

                return app

        except Exception:
            return app

        time.sleep(0.3)

    raise AssertionError(
        "Login did not complete successfully."
    )


# ============================================================
# ACTION REGISTRY
# ============================================================

ACTION_HANDLERS = {

    "start_application":
        action_start_application,

    "stop_application":
        action_stop_application,

    "click":
        action_click,

    "enter":
        action_enter,

    "wait":
        action_wait,

    "verify_window":
        action_verify_window,

    "verify":
        action_verify,
}


# ============================================================
# STEP EXECUTION
# ============================================================

def execute_step(
    app,
    step,
    test_id,
    evidence
):

    action = step.get("action")

    if not action:

        raise ValueError(
            "Every YAML step requires 'action'."
        )

    print(
        f"[STEP] {action}"
    )

    if action == "screenshot":

        app, screenshot = action_screenshot(
            app,
            step,
            test_id
        )

        if screenshot:
            evidence.append(
                screenshot
            )

        return app

    if action not in ACTION_HANDLERS:

        raise ValueError(
            f"Unsupported action '{action}'. "
            f"Available actions: "
            f"{', '.join(ACTION_HANDLERS.keys())}"
        )

    handler = ACTION_HANDLERS[action]

    return handler(
        app,
        step
    )


# ============================================================
# RUN ONE TEST CASE
# ============================================================

def run_test_case(test_case):

    test_id = test_case["id"]
    test_name = test_case["name"]

    print()
    print("=" * 60)
    print(
        f"TEST CASE: {test_id} - {test_name}"
    )
    print("=" * 60)

    started = time.perf_counter()

    status = "PASS"

    message = ""

    evidence = []

    app = None

    try:

        setup = test_case.get(
            "setup",
            {}
        )

        state = setup.get(
            "state",
            "fresh_start"
        )

        app = prepare_application(
            state
        )

        steps = test_case.get(
            "steps",
            []
        )

        for step in steps:

            app = execute_step(
                app,
                step,
                test_id,
                evidence
            )

        expected = test_case.get(
            "expected",
            {}
        )

        message = expected.get(
            "message",
            "All test steps completed successfully."
        )

    except Exception as error:

        status = "FAIL"

        message = (
            f"{type(error).__name__}: {error}"
        )

        print(
            f"[FAIL] {message}"
        )

        # Automatic failure evidence

        if app is not None:

            try:

                app, screenshot = action_screenshot(
                    app,
                    {
                        "name": "failure"
                    },
                    test_id
                )

                if screenshot:

                    evidence.append(
                        screenshot
                    )

            except Exception as screenshot_error:

                print(
                    "[WARNING] "
                    f"Could not save failure screenshot: "
                    f"{screenshot_error}"
                )

    duration = round(
        time.perf_counter() - started,
        3
    )

    report = {

        "project":
            "SENDiPAD POS",

        "test_case":
            test_id,

        "test_name":
            test_name,

        "status":
            status,

        "message":
            message,

        "timestamp":
            datetime.now().isoformat(),

        "duration_seconds":
            duration,

        "screenshots":
            evidence
    }

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    report_file = (
        REPORTS_DIR /
        f"{test_id}_{timestamp}.json"
    )

    with open(
        report_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(
        f"[{status}] "
        f"{test_id} - {test_name}"
    )

    print(
        f"Report: {report_file}"
    )

    return report


# ============================================================
# RUN ALL TEST CASES
# ============================================================

def run_all_tests():

    test_cases = load_test_cases()

    if not test_cases:

        raise ValueError(
            "No test cases found in tests.yaml."
        )

    results = []

    for test_case in test_cases:

        results.append(
            run_test_case(
                test_case
            )
        )

    return results


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    results = run_all_tests()

    print()
    print("=" * 60)
    print("QA TEST RUN COMPLETE")
    print("=" * 60)

    total = len(results)

    passed = sum(
        result["status"] == "PASS"
        for result in results
    )

    failed = sum(
        result["status"] == "FAIL"
        for result in results
    )

    print(f"Total : {total}")
    print(f"PASS  : {passed}")
    print(f"FAIL  : {failed}")

    print("=" * 60)