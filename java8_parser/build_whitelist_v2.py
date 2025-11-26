#!/usr/bin/env python3
"""
Build a whitelist of Java files that compile successfully with javac.
This version compiles with proper source paths so dependencies resolve.
"""

import subprocess
import sys
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile

BASE_DIR = Path(__file__).parent.parent / "jdk7u-langtools"
SRC_DIR = BASE_DIR / "src" / "share" / "classes"
TEST_DIR = BASE_DIR / "test"


def compile_batch(java_files: list[Path], sourcepaths: list[Path]) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Compile a batch of files together with source paths."""
    if not java_files:
        return [], []

    sourcepath = ":".join(str(p) for p in sourcepaths)

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "javac",
            "-proc:none",
            "-source", "1.8",
            "-target", "1.8",
            "-d", tmpdir,
            "-nowarn",
            "-Xlint:none",
            "-sourcepath", sourcepath,
        ] + [str(f) for f in java_files]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                return java_files, []
            else:
                return [], [(f, result.stderr[:500]) for f in java_files]
        except subprocess.TimeoutExpired:
            return [], [(f, "timeout") for f in java_files]
        except Exception as e:
            return [], [(f, str(e)) for f in java_files]


SOURCEPATHS = []

def test_file_individually(java_file: Path) -> tuple[Path, bool, str]:
    """Test a single file with source paths."""
    sourcepath = ":".join(str(p) for p in SOURCEPATHS)

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "javac",
            "-proc:none",
            "-source", "1.8",
            "-target", "1.8",
            "-d", tmpdir,
            "-nowarn",
            "-Xlint:none",
            "-sourcepath", sourcepath,
            str(java_file)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            return (java_file, result.returncode == 0, result.stderr[:500] if result.stderr else "")
        except subprocess.TimeoutExpired:
            return (java_file, False, "timeout")
        except Exception as e:
            return (java_file, False, str(e))


def main():
    if not BASE_DIR.exists():
        print(f"Error: {BASE_DIR} does not exist")
        sys.exit(1)

    # Collect all Java files
    src_files = list(SRC_DIR.rglob("*.java")) if SRC_DIR.exists() else []
    test_files = list(TEST_DIR.rglob("*.java")) if TEST_DIR.exists() else []
    all_files = src_files + test_files

    print(f"Found {len(src_files)} source files and {len(test_files)} test files")
    print(f"Total: {len(all_files)} Java files")

    # Source paths for dependency resolution
    global SOURCEPATHS
    SOURCEPATHS = [SRC_DIR, TEST_DIR, BASE_DIR]

    # First, try to compile all source files together
    print("\n=== Compiling source files together ===")
    passed_src, failed_src = compile_batch(src_files, SOURCEPATHS)
    if passed_src:
        print(f"All {len(passed_src)} source files compiled together successfully!")
    else:
        print(f"Batch compilation failed, testing individually...")
        passed_src = []
        failed_src = []

    # Test files individually (they often have intentional errors for testing)
    print("\n=== Testing files individually with sourcepath ===")

    compilable = list(passed_src)
    failed = list(failed_src)

    # Files to test individually
    files_to_test = test_files if passed_src else all_files

    num_workers = os.cpu_count() or 4
    print(f"Testing {len(files_to_test)} files with {num_workers} workers...")

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(test_file_individually, f): f for f in files_to_test}

        for i, future in enumerate(as_completed(futures)):
            java_file, success, error = future.result()
            if success:
                compilable.append(java_file)
            else:
                failed.append((java_file, error))

            if (i + 1) % 100 == 0:
                print(f"Progress: {i + 1}/{len(files_to_test)} "
                      f"({len(compilable)} compilable, {len(failed)} failed)")

    # Save results
    output_file = Path(__file__).parent / "whitelist.txt"
    with open(output_file, "w") as f:
        for java_file in sorted(set(compilable)):
            f.write(f"{java_file}\n")

    print(f"\nResults:")
    print(f"  Compilable: {len(set(compilable))}")
    print(f"  Failed: {len(failed)}")
    print(f"  Whitelist saved to: {output_file}")

    errors_file = Path(__file__).parent / "compile_errors.txt"
    with open(errors_file, "w") as f:
        for java_file, error in sorted(failed, key=lambda x: str(x[0])):
            f.write(f"=== {java_file} ===\n{error}\n\n")
    print(f"  Errors saved to: {errors_file}")


if __name__ == "__main__":
    main()
