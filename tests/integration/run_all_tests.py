#!/usr/bin/env python3
"""Run all integration tests by auto-discovering cat*.java files."""

import subprocess
import tempfile
import shutil
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import sys


@dataclass
class TestResult:
    """Result of running a test."""
    filename: str
    main_class: str
    status: str  # "PASS", "COMPILE_FAIL", "RUNTIME_FAIL", "OUTPUT_MISMATCH"
    expected: Optional[List[str]]
    actual: List[str]
    error: str


def extract_expected_output(java_file: Path) -> Optional[List[str]]:
    """Extract expected output from test file comments or run with javac."""
    # Try to compile and run with javac to get expected output
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        test_file = tmpdir / java_file.name
        shutil.copy(java_file, test_file)

        # Compile with javac
        result = subprocess.run(
            ["javac", java_file.name],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return None  # Can't get reference output

        # Extract main class name
        main_class = extract_main_class(java_file)
        if not main_class:
            return None

        # Run with java
        result = subprocess.run(
            ["java", main_class],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            return result.stdout.strip().split("\n") if result.stdout.strip() else []
        return None


def extract_main_class(java_file: Path) -> Optional[str]:
    """Extract the main class name from a Java file."""
    content = java_file.read_text()
    # Look for "public class ClassName"
    match = re.search(r'public\s+class\s+(\w+)', content)
    if match:
        return match.group(1)
    # Fallback: look for any class with main method
    match = re.search(r'class\s+(\w+)\s*\{[^}]*public\s+static\s+void\s+main', content, re.DOTALL)
    if match:
        return match.group(1)
    return None


def run_test(java_file: Path, main_class: str, expected_output: Optional[List[str]]) -> TestResult:
    """Run a single test and return the result."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Copy Java file to temp directory
        test_file = tmpdir / java_file.name
        shutil.copy(java_file, test_file)

        # Compile with pyjopa
        result = subprocess.run(
            ["python", "-m", "pyjopa.cli", "compile", "-q", java_file.name],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return TestResult(
                filename=java_file.name,
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
                filename=java_file.name,
                main_class=main_class,
                status="RUNTIME_FAIL",
                expected=expected_output,
                actual=[],
                error=result.stderr.strip()
            )

        # Check output
        actual_output = result.stdout.strip().split("\n") if result.stdout.strip() else []

        if expected_output is None:
            # No reference output available
            return TestResult(
                filename=java_file.name,
                main_class=main_class,
                status="NO_REFERENCE",
                expected=None,
                actual=actual_output,
                error="No reference output from javac"
            )
        elif actual_output == expected_output:
            return TestResult(
                filename=java_file.name,
                main_class=main_class,
                status="PASS",
                expected=expected_output,
                actual=actual_output,
                error=""
            )
        else:
            return TestResult(
                filename=java_file.name,
                main_class=main_class,
                status="OUTPUT_MISMATCH",
                expected=expected_output,
                actual=actual_output,
                error=f"Expected: {expected_output}\nActual: {actual_output}"
            )


def main():
    """Run all tests and generate report."""
    integration_dir = Path(__file__).parent

    # Find all cat*.java files
    test_files = sorted(integration_dir.glob("cat*.java"))

    print("=" * 80)
    print("RUNNING COMPREHENSIVE JAVA 8 TEST SUITE")
    print("=" * 80)
    print()

    results = []

    for i, java_file in enumerate(test_files, 1):
        print(f"[{i}/{len(test_files)}] Testing {java_file.name}...", end=" ", flush=True)

        try:
            # Extract main class
            main_class = extract_main_class(java_file)
            if not main_class:
                print("✗ NO_MAIN_CLASS")
                results.append(TestResult(
                    filename=java_file.name,
                    main_class="",
                    status="NO_MAIN_CLASS",
                    expected=None,
                    actual=[],
                    error="Could not find main class"
                ))
                continue

            # Get expected output from javac
            expected_output = extract_expected_output(java_file)

            # Run test
            result = run_test(java_file, main_class, expected_output)
            results.append(result)

            if result.status == "PASS":
                print("✓ PASS")
            elif result.status == "COMPILE_FAIL":
                print("✗ COMPILE_FAIL")
            elif result.status == "RUNTIME_FAIL":
                print("✗ RUNTIME_FAIL")
            elif result.status == "OUTPUT_MISMATCH":
                print("✗ OUTPUT_MISMATCH")
            elif result.status == "NO_REFERENCE":
                print("⚠ NO_REFERENCE (compiled & ran, but javac failed)")
            else:
                print(f"✗ {result.status}")

        except Exception as e:
            print(f"✗ ERROR: {e}")
            results.append(TestResult(
                filename=java_file.name,
                main_class="",
                status="ERROR",
                expected=None,
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
    no_reference = [r for r in results if r.status == "NO_REFERENCE"]
    other = [r for r in results if r.status not in ["PASS", "COMPILE_FAIL", "RUNTIME_FAIL", "OUTPUT_MISMATCH", "NO_REFERENCE"]]

    print(f"Total tests: {len(results)}")
    print(f"  ✓ Passed: {len(passed)} ({len(passed)*100//len(results) if results else 0}%)")
    print(f"  ✗ Compile failures: {len(compile_fail)}")
    print(f"  ✗ Runtime failures: {len(runtime_fail)}")
    print(f"  ✗ Output mismatches: {len(output_mismatch)}")
    print(f"  ⚠ No reference output: {len(no_reference)}")
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
            print(f"  {error_lines[0] if error_lines else ''}")

    if runtime_fail:
        print()
        print("=" * 80)
        print("RUNTIME FAILURES")
        print("=" * 80)
        for r in runtime_fail:
            print(f"\n{r.filename}:")
            # Only show first line of error
            error_lines = r.error.split("\n")
            print(f"  {error_lines[0] if error_lines else ''}")

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
