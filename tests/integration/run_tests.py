#!/usr/bin/env python3
"""Run all integration tests and generate a report."""

import subprocess
import tempfile
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import List
import sys

# Import test definitions
from generate_tests import TESTS


@dataclass
class TestResult:
    """Result of running a test."""
    filename: str
    main_class: str
    status: str  # "PASS", "COMPILE_FAIL", "RUNTIME_FAIL", "OUTPUT_MISMATCH"
    expected: List[str]
    actual: List[str]
    error: str


def run_test(filename: str, main_class: str, expected_output: List[str]) -> TestResult:
    """Run a single test and return the result."""
    integration_dir = Path(__file__).parent
    java_path = integration_dir / filename

    if not java_path.exists():
        return TestResult(
            filename=filename,
            main_class=main_class,
            status="FILE_NOT_FOUND",
            expected=expected_output,
            actual=[],
            error=f"File not found: {java_path}"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Copy Java file to temp directory
        test_file = tmpdir / filename
        shutil.copy(java_path, test_file)

        # Compile
        result = subprocess.run(
            ["python", "-m", "pyjopa.cli", "compile", "-q", filename],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return TestResult(
                filename=filename,
                main_class=main_class,
                status="COMPILE_FAIL",
                expected=expected_output,
                actual=[],
                error=result.stderr.strip()
            )

        # Run
        result = subprocess.run(
            ["java", main_class],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return TestResult(
                filename=filename,
                main_class=main_class,
                status="RUNTIME_FAIL",
                expected=expected_output,
                actual=[],
                error=result.stderr.strip()
            )

        # Check output
        actual_output = result.stdout.strip().split("\n") if result.stdout.strip() else []

        if actual_output == expected_output:
            return TestResult(
                filename=filename,
                main_class=main_class,
                status="PASS",
                expected=expected_output,
                actual=actual_output,
                error=""
            )
        else:
            return TestResult(
                filename=filename,
                main_class=main_class,
                status="OUTPUT_MISMATCH",
                expected=expected_output,
                actual=actual_output,
                error=f"Expected: {expected_output}\nActual: {actual_output}"
            )


def main():
    """Run all tests and generate report."""
    print("=" * 80)
    print("RUNNING COMPREHENSIVE JAVA 8 TEST SUITE")
    print("=" * 80)
    print()

    results = []

    for i, (filename, main_class, code, expected) in enumerate(TESTS, 1):
        print(f"[{i}/{len(TESTS)}] Testing {filename}...", end=" ", flush=True)

        try:
            result = run_test(filename, main_class, expected)
            results.append(result)

            if result.status == "PASS":
                print("✓ PASS")
            elif result.status == "COMPILE_FAIL":
                print("✗ COMPILE_FAIL")
            elif result.status == "RUNTIME_FAIL":
                print("✗ RUNTIME_FAIL")
            elif result.status == "OUTPUT_MISMATCH":
                print("✗ OUTPUT_MISMATCH")
            else:
                print(f"✗ {result.status}")

        except Exception as e:
            print(f"✗ ERROR: {e}")
            results.append(TestResult(
                filename=filename,
                main_class=main_class,
                status="ERROR",
                expected=expected,
                actual=[],
                error=str(e)
            ))

    # Generate summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()

    passed = [r for r in results if r.status == "PASS"]
    compile_fail = [r for r in results if r.status == "COMPILE_FAIL"]
    runtime_fail = [r for r in results if r.status == "RUNTIME_FAIL"]
    output_mismatch = [r for r in results if r.status == "OUTPUT_MISMATCH"]
    other = [r for r in results if r.status not in ["PASS", "COMPILE_FAIL", "RUNTIME_FAIL", "OUTPUT_MISMATCH"]]

    print(f"Total tests: {len(results)}")
    print(f"  ✓ Passed: {len(passed)} ({len(passed)*100//len(results)}%)")
    print(f"  ✗ Compile failures: {len(compile_fail)}")
    print(f"  ✗ Runtime failures: {len(runtime_fail)}")
    print(f"  ✗ Output mismatches: {len(output_mismatch)}")
    print(f"  ✗ Other errors: {len(other)}")
    print()

    # Categorize by category
    categories = {}
    for r in results:
        cat = r.filename.split("_")[0]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    print("BY CATEGORY:")
    for cat in sorted(categories.keys()):
        cat_results = categories[cat]
        cat_passed = [r for r in cat_results if r.status == "PASS"]
        print(f"  {cat}: {len(cat_passed)}/{len(cat_results)} passed")

    # Show failures
    if compile_fail:
        print()
        print("=" * 80)
        print("COMPILE FAILURES")
        print("=" * 80)
        for r in compile_fail:
            print(f"\n{r.filename}:")
            # Only show first line of error
            error_lines = r.error.split("\n")
            print(f"  {error_lines[0]}")

    if runtime_fail:
        print()
        print("=" * 80)
        print("RUNTIME FAILURES")
        print("=" * 80)
        for r in runtime_fail:
            print(f"\n{r.filename}:")
            # Only show first line of error
            error_lines = r.error.split("\n")
            print(f"  {error_lines[0]}")

    if output_mismatch:
        print()
        print("=" * 80)
        print("OUTPUT MISMATCHES")
        print("=" * 80)
        for r in output_mismatch:
            print(f"\n{r.filename}:")
            print(f"  Expected: {r.expected}")
            print(f"  Actual:   {r.actual}")

    print()
    print("=" * 80)

    # Return non-zero exit code if any tests failed
    if len(passed) < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
