#!/usr/bin/env python3
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results"

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _parse_junit(xml_path: Path) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        return {
            "tests": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "xfail": 0,
            "xpass": 0,
            "failures": [],
        }

    tests = int(suite.get("tests", 0))
    errors_n = int(suite.get("errors", 0))
    skipped_n = int(suite.get("skips", suite.get("skipped", 0)))

    xfail = 0
    xpass = 0
    failures = []

    for tc in suite.iter("testcase"):
        name = tc.get("name", "?")
        classname = tc.get("classname", "")

        skipped_el = tc.find("skipped")
        if skipped_el is not None:
            msg = skipped_el.get("message", "")
            if "xfail" in msg.lower() or "expected failure" in msg.lower():
                xfail += 1
                continue

        fail_el = tc.find("failure")
        err_el = tc.find("error")
        if fail_el is not None:
            msg = (fail_el.get("message") or fail_el.text or "").strip().split("\n")[0]
            if "xpass" in msg.lower():
                xpass += 1
            else:
                failures.append({"test": f"{classname}::{name}", "message": msg})
        elif err_el is not None:
            msg = (err_el.get("message") or err_el.text or "").strip().split("\n")[0]
            failures.append({"test": f"{classname}::{name}", "message": msg})

    passed = tests - len(failures) - errors_n - skipped_n - xfail - xpass

    return {
        "tests": tests,
        "passed": passed,
        "failed": len(failures),
        "errors": errors_n,
        "skipped": skipped_n - xfail,
        "xfail": xfail,
        "xpass": xpass,
        "failures": failures,
    }


def main() -> int:
    if not RESULTS_DIR.exists():
        print(f"No results directory found at {RESULTS_DIR}")
        return 1

    json_files = sorted(RESULTS_DIR.glob("*.json"))
    if not json_files:
        print("No result files found.")
        return 1

    rows = []
    all_failures = []

    for jf in json_files:
        summary = json.loads(jf.read_text())
        stem = jf.stem
        xml_path = RESULTS_DIR / f"{stem}.xml"
        junit = _parse_junit(xml_path) if xml_path.exists() else None

        rows.append({"summary": summary, "junit": junit})
        if junit:
            for f in junit["failures"]:
                all_failures.append(
                    {
                        "manifest": summary["manifest"],
                        "library": summary["library_id"],
                        **f,
                    }
                )

    print()
    print(
        f"{BOLD}{'Manifest':<35s} {'Library':<14s} {'Pass':>5s} {'XFail':>6s} "
        f"{'XPass':>6s} {'Fail':>5s} {'Err':>5s}  Status{RESET}"
    )
    print("─" * 110)

    total_pass = total_xfail = total_xpass = total_fail = total_err = 0
    for row in rows:
        s = row["summary"]
        j = row["junit"]
        name = s["manifest"]
        lib = s["library_id"]

        if j:
            p, xf, xp, f, e = (
                j["passed"],
                j["xfail"],
                j["xpass"],
                j["failed"],
                j["errors"],
            )
            total_pass += p
            total_xfail += xf
            total_xpass += xp
            total_fail += f
            total_err += e

            status = f"{GREEN}PASS{RESET}" if (f + e + xp) == 0 else f"{RED}FAIL{RESET}"

            xf_str = f"{CYAN}{xf:>6d}{RESET}" if xf > 0 else f"{xf:>6d}"
            xp_str = f"{RED}{xp:>6d}{RESET}" if xp > 0 else f"{xp:>6d}"

            print(
                f"  {name:<33s} {lib:<14s} {GREEN}{p:>5d}{RESET} {xf_str} {xp_str} "
                f"{RED}{f:>5d}{RESET} {RED}{e:>5d}{RESET}  {status}"
            )
        else:
            status = (
                f"{RED}NO XML{RESET}" if s["exit_code"] != 0 else f"{YELLOW}???{RESET}"
            )
            print(
                f"  {name:<33s} {lib:<14s} {'—':>5s} {'—':>6s} {'—':>6s} "
                f"{'—':>5s} {'—':>5s}  {status}"
            )

    print("─" * 110)
    print(
        f"  {'TOTAL':<33s} {'':14s} {total_pass:>5d} {total_xfail:>6d} "
        f"{total_xpass:>6d} {total_fail:>5d} {total_err:>5d}"
    )
    print()

    if all_failures:
        print(f"{BOLD}{RED}Failed tests ({len(all_failures)}):{RESET}")
        print()
        for i, f in enumerate(all_failures, 1):
            print(f"  {i}. {CYAN}[{f['library']}]{RESET} {f['test']}")
            print(f"     {DIM}{f['message']}{RESET}")
        print()
    else:
        print(f"{GREEN}{BOLD}All tests passed.{RESET}")
        print()

    log_files = sorted(RESULTS_DIR.glob("*.log"))
    if log_files:
        print(f"{DIM}Full pytest logs:{RESET}")
        for lf in log_files:
            print(f"  {DIM}{lf}{RESET}")
        print()

    return 1 if all_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
