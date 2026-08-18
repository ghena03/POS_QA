import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from pywinauto import Desktop


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

APP_PATH = Path(r"D:\SendipadPOS\SENDiPADPOS.exe")
APP_PROCESS = "SENDiPADPOS.exe"
APP_TITLE = "SENDiPAD POS"

REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


TESTS = [
    ("TC-01", "Application Startup", "tests/test_startup.py"),
    ("TC-02", "Valid Login", "tests/test_ValidLogin.py"),
    ("TC-03", "Invalid Login", "tests/test_invalid_login.py"),
]


# ============================================================
# Application Control
# ============================================================

def stop_application():
    """Close any existing SENDiPAD process."""

    print("[APP] Closing existing SENDiPAD POS...")

    subprocess.run(
        ["taskkill", "/F", "/IM", APP_PROCESS],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    time.sleep(2)


def start_application():
    """Start SENDiPAD POS and wait for its window."""

    print("[APP] Starting SENDiPAD POS...")

    if not APP_PATH.exists():
        raise FileNotFoundError(
            f"SENDiPAD executable not found: {APP_PATH}"
        )

    subprocess.Popen(
        [str(APP_PATH)],
        cwd=str(APP_PATH.parent)
    )

    print("[APP] Waiting for application window...")

    deadline = time.time() + 20

    while time.time() < deadline:

        try:
            app = Desktop(backend="uia").window(
                title=APP_TITLE
            )

            if app.exists() and app.is_visible():
                print("[APP] SENDiPAD POS is ready.")
                time.sleep(2)
                return

        except Exception:
            pass

        time.sleep(1)

    raise TimeoutError(
        "SENDiPAD POS window did not appear within 20 seconds."
    )


def prepare_application():
    """Reset SENDiPAD to a clean state."""

    stop_application()
    start_application()


# ============================================================
# Result Detection
# ============================================================

def detect_status(output, error_output):

    text = f"{output}\n{error_output}"

    # Explicit error indicators
    if "[ERROR]" in text:
        return "ERROR"

    # Explicit blocked indicators
    if "[BLOCKED]" in text or "Status    : BLOCKED" in text:
        return "BLOCKED"

    # Explicit fail indicators
    if "[FAIL]" in text or "Status    : FAIL" in text:
        return "FAIL"

    # PASS indicators
    if "[PASS]" in text or "Status    : PASS" in text:
        return "PASS"

    return "ERROR"


# ============================================================
# Run Individual Test
# ============================================================

def run_test(test_case, test_name, test_file):

    print()
    print("=" * 70)
    print(f"{test_case} - {test_name}")
    print("=" * 70)

    start_time = datetime.now()

    try:

        # ----------------------------------------------------
        # Start with a clean application state
        # ----------------------------------------------------

        prepare_application()

        # ----------------------------------------------------
        # Run test
        # ----------------------------------------------------

        process = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / test_file)
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )

        end_time = datetime.now()

        output = process.stdout.strip()
        error_output = process.stderr.strip()

        status = detect_status(
            output,
            error_output
        )

        return {
            "test_case": test_case,
            "test_name": test_name,
            "status": status,
            "duration_seconds": round(
                (end_time - start_time).total_seconds(),
                3
            ),
            "output": output,
            "error_output": error_output
        }

    except Exception as error:

        end_time = datetime.now()

        return {
            "test_case": test_case,
            "test_name": test_name,
            "status": "ERROR",
            "duration_seconds": round(
                (end_time - start_time).total_seconds(),
                3
            ),
            "output": "",
            "error_output": (
                f"{type(error).__name__}: {error}"
            )
        }


# ============================================================
# Run Full QA Suite
# ============================================================

def run_suite():

    suite_start = datetime.now()

    print()
    print("=" * 70)
    print("              SENDiPAD POS QA AUTOMATION")
    print("=" * 70)

    results = []

    for test_case, test_name, test_file in TESTS:

        result = run_test(
            test_case,
            test_name,
            test_file
        )

        results.append(result)

        print()
        print(
            f"[{result['status']}] "
            f"{test_case} - {test_name}"
        )

    suite_end = datetime.now()

    # ========================================================
    # Statistics
    # ========================================================

    total = len(results)

    passed = sum(
        result["status"] == "PASS"
        for result in results
    )

    failed = sum(
        result["status"] == "FAIL"
        for result in results
    )

    errors = sum(
        result["status"] == "ERROR"
        for result in results
    )

    blocked = sum(
        result["status"] == "BLOCKED"
        for result in results
    )

    summary = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "blocked": blocked
    }

    # ========================================================
    # Create Combined Report
    # ========================================================

    report = {
        "project": "SENDiPAD POS",
        "report_type": "Automated QA Test Run",
        "started_at": suite_start.isoformat(),
        "finished_at": suite_end.isoformat(),
        "duration_seconds": round(
            (suite_end - suite_start).total_seconds(),
            3
        ),
        "summary": summary,
        "tests": results
    }

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    report_file = (
        REPORTS_DIR /
        f"QA_Report_{timestamp}.json"
    )

    with report_file.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=4,
            ensure_ascii=False
        )

    # ========================================================
    # Display Summary
    # ========================================================

    print()
    print("=" * 70)
    print("                       QA SUMMARY")
    print("=" * 70)

    print(f"Total   : {total}")
    print(f"PASS    : {passed}")
    print(f"FAIL    : {failed}")
    print(f"ERROR   : {errors}")
    print(f"BLOCKED : {blocked}")

    print("-" * 70)
    print(f"Report saved: {report_file}")
    print("=" * 70)

    return report


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    run_suite()