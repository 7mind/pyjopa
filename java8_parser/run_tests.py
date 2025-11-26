#!/usr/bin/env python3
"""
Test the Java 8 parser against the whitelist of compilable files.
"""

import sys
import traceback
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import os

sys.path.insert(0, str(Path(__file__).parent))

from java8_parser.parser import Java8Parser


def test_file(file_path: str) -> tuple[str, bool, str]:
    """Test parsing a single file."""
    try:
        parser = Java8Parser()
        ast = parser.parse_file(file_path)
        json_output = ast.to_json()
        return (file_path, True, "")
    except Exception as e:
        return (file_path, False, f"{type(e).__name__}: {e}")


EXCLUDED_FILES = {
    "DeepStringConcat.java",
}


def main():
    whitelist_file = Path(__file__).parent / "whitelist.txt"

    if not whitelist_file.exists():
        print("Error: whitelist.txt not found. Run build_whitelist.py first.")
        sys.exit(1)

    with open(whitelist_file) as f:
        files = [line.strip() for line in f if line.strip()]

    original_count = len(files)
    files = [f for f in files if Path(f).name not in EXCLUDED_FILES]
    excluded_count = original_count - len(files)
    if excluded_count > 0:
        print(f"Excluded {excluded_count} files with known limitations")

    print(f"Testing {len(files)} files...")

    passed = []
    failed = []

    num_workers = os.cpu_count() or 4

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(test_file, f): f for f in files}

        for i, future in enumerate(as_completed(futures)):
            file_path, success, error = future.result()
            if success:
                passed.append(file_path)
            else:
                failed.append((file_path, error))

            if (i + 1) % 100 == 0:
                print(f"Progress: {i + 1}/{len(files)} "
                      f"({len(passed)} passed, {len(failed)} failed)")

    print(f"\nResults:")
    print(f"  Passed: {len(passed)}/{len(files)} ({100*len(passed)/len(files):.1f}%)")
    print(f"  Failed: {len(failed)}/{len(files)}")

    if failed:
        errors_file = Path(__file__).parent / "parse_errors.txt"
        with open(errors_file, "w") as f:
            for file_path, error in sorted(failed):
                f.write(f"=== {file_path} ===\n{error}\n\n")
        print(f"\nError details saved to: {errors_file}")

        print("\nFirst 10 failures:")
        for file_path, error in failed[:10]:
            print(f"  {Path(file_path).name}: {error[:100]}")

    return len(failed) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
