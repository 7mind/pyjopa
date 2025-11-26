#!/usr/bin/env python3
"""
Build a whitelist of Java files that compile successfully with javac.
Tests files one by one using javac -proc:none to skip annotation processing.
"""

import subprocess
import sys
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile

def test_compile(java_file: Path) -> tuple[Path, bool, str]:
    """Test if a Java file compiles successfully."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    "javac",
                    "-proc:none",
                    "-source", "1.8",
                    "-target", "1.8",
                    "-d", tmpdir,
                    "-nowarn",
                    str(java_file)
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            return (java_file, result.returncode == 0, result.stderr)
    except subprocess.TimeoutExpired:
        return (java_file, False, "timeout")
    except Exception as e:
        return (java_file, False, str(e))


def main():
    base_dir = Path(__file__).parent.parent / "jdk7u-langtools"

    if not base_dir.exists():
        print(f"Error: {base_dir} does not exist")
        sys.exit(1)

    java_files = list(base_dir.rglob("*.java"))
    print(f"Found {len(java_files)} Java files")

    compilable = []
    failed = []

    num_workers = os.cpu_count() or 4
    print(f"Testing with {num_workers} workers...")

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(test_compile, f): f for f in java_files}

        for i, future in enumerate(as_completed(futures)):
            java_file, success, error = future.result()
            if success:
                compilable.append(java_file)
            else:
                failed.append((java_file, error))

            if (i + 1) % 100 == 0:
                print(f"Progress: {i + 1}/{len(java_files)} "
                      f"({len(compilable)} compilable, {len(failed)} failed)")

    output_file = Path(__file__).parent / "whitelist.txt"
    with open(output_file, "w") as f:
        for java_file in sorted(compilable):
            f.write(f"{java_file}\n")

    print(f"\nResults:")
    print(f"  Compilable: {len(compilable)}")
    print(f"  Failed: {len(failed)}")
    print(f"  Whitelist saved to: {output_file}")

    errors_file = Path(__file__).parent / "compile_errors.txt"
    with open(errors_file, "w") as f:
        for java_file, error in sorted(failed):
            f.write(f"=== {java_file} ===\n{error}\n\n")
    print(f"  Errors saved to: {errors_file}")


if __name__ == "__main__":
    main()
