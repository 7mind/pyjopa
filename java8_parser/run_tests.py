#!/usr/bin/env python3
"""
Test the Java 8 parser against a whitelist of files.
"""

import argparse
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import os

sys.path.insert(0, str(Path(__file__).parent))

from java8_parser.parser import Java8Parser


EXCLUDED_FILES = {
    "DeepStringConcat.java",  # 32000+ nested expressions exceed recursion limit
    "IgnoreIgnorableCharactersInInput.java",  # Uses NUL chars in identifiers
    "UncommonParamNames.java",  # Uses NUL chars in parameter names
}


def test_file(file_path: str) -> tuple[str, bool, str]:
    """Test parsing a single file."""
    try:
        parser = Java8Parser()
        ast = parser.parse_file(file_path)
        json_output = ast.to_json()
        return (file_path, True, "")
    except Exception as e:
        return (file_path, False, f"{type(e).__name__}: {e}")


def main():
    arg_parser = argparse.ArgumentParser(
        description="Test the Java 8 parser against a whitelist of files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Use default whitelist.txt
  %(prog)s -w whitelist_parse.txt             # Use custom whitelist
  %(prog)s -w whitelist.txt -o results.txt    # Save errors to custom file
  %(prog)s -j 8 -v                            # Use 8 workers, verbose output
"""
    )

    arg_parser.add_argument(
        "-w", "--whitelist",
        default="whitelist.txt",
        help="Whitelist file to test against (default: whitelist.txt)"
    )
    arg_parser.add_argument(
        "-o", "--output",
        default="parse_errors.txt",
        help="Output file for error details (default: parse_errors.txt)"
    )
    arg_parser.add_argument(
        "-j", "--jobs",
        type=int,
        default=None,
        help="Number of parallel jobs (default: CPU count)"
    )
    arg_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show progress every 50 files instead of 100"
    )
    arg_parser.add_argument(
        "--no-exclude",
        action="store_true",
        help="Don't exclude known problematic files"
    )

    args = arg_parser.parse_args()

    script_dir = Path(__file__).parent
    whitelist_file = script_dir / args.whitelist
    errors_file = script_dir / args.output
    num_workers = args.jobs or os.cpu_count() or 4
    progress_interval = 50 if args.verbose else 100

    if not whitelist_file.exists():
        print(f"Error: {whitelist_file} not found.")
        print("Run build_whitelist.py first to generate it.")
        sys.exit(1)

    with open(whitelist_file) as f:
        files = [line.strip() for line in f if line.strip()]

    original_count = len(files)

    if not args.no_exclude:
        files = [f for f in files if Path(f).name not in EXCLUDED_FILES]
        excluded_count = original_count - len(files)
        if excluded_count > 0:
            print(f"Excluded {excluded_count} files with known limitations")

    print(f"Testing {len(files)} files from {whitelist_file.name}...")
    print(f"Using {num_workers} workers")

    passed = []
    failed = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(test_file, f): f for f in files}

        for i, future in enumerate(as_completed(futures)):
            file_path, success, error = future.result()
            if success:
                passed.append(file_path)
            else:
                failed.append((file_path, error))

            if (i + 1) % progress_interval == 0:
                pct = 100 * len(passed) / (len(passed) + len(failed))
                print(f"Progress: {i + 1}/{len(files)} "
                      f"({len(passed)} passed, {len(failed)} failed, {pct:.1f}%)")

    total = len(passed) + len(failed)
    pct = 100 * len(passed) / total if total > 0 else 0

    print(f"\nResults:")
    print(f"  Passed: {len(passed)}/{total} ({pct:.1f}%)")
    print(f"  Failed: {len(failed)}/{total}")

    if failed:
        with open(errors_file, "w") as f:
            for file_path, error in sorted(failed):
                f.write(f"=== {file_path} ===\n{error}\n\n")
        print(f"\nError details saved to: {errors_file}")

        print("\nFirst 10 failures:")
        for file_path, error in failed[:10]:
            name = Path(file_path).name
            error_preview = error[:80].replace('\n', ' ')
            print(f"  {name}: {error_preview}")

    return len(failed) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
