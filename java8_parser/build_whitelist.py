#!/usr/bin/env python3
"""
Build a whitelist of Java files suitable for parser testing.

Modes:
  isolated   - Each file must compile completely in isolation
  sourcepath - Files compile with source path for dependency resolution
  parse-only - Only reject files with parse/syntax errors (most permissive)
"""

import argparse
import subprocess
import sys
import os
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile


PARSE_ERROR_PATTERNS = [
    r"illegal start",
    r"expected",
    r"unclosed",
    r"reached end of file",
    r"malformed",
    r"not a statement",
    r"class, interface, or enum expected",
    r"illegal character",
    r"invalid escape sequence",
]

PARSE_ERROR_RE = re.compile("|".join(PARSE_ERROR_PATTERNS), re.IGNORECASE)


def is_parse_error(stderr: str) -> bool:
    """Check if the error is a parse/syntax error vs a semantic error."""
    if not stderr.strip():
        return False
    return PARSE_ERROR_RE.search(stderr) is not None


class WhitelistBuilder:
    def __init__(self, base_dir: Path, mode: str, java_version: str = "1.8"):
        self.base_dir = base_dir
        self.mode = mode
        self.java_version = java_version
        self.sourcepaths = self._find_sourcepaths()

    def _find_sourcepaths(self) -> list[Path]:
        """Find source directories for sourcepath mode."""
        paths = []
        src_classes = self.base_dir / "src" / "share" / "classes"
        if src_classes.exists():
            paths.append(src_classes)
        test_dir = self.base_dir / "test"
        if test_dir.exists():
            paths.append(test_dir)
        if self.base_dir.exists():
            paths.append(self.base_dir)
        return paths

    def test_file(self, java_file: Path) -> tuple[Path, bool, str]:
        """Test if a Java file passes based on current mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "javac",
                "-source", self.java_version,
                "-target", self.java_version,
                "-proc:none",
                "-d", tmpdir,
                "-nowarn",
                "-Xlint:none",
            ]

            if self.mode == "parse-only":
                cmd.extend(["-implicit:none", "-XDshouldStopPolicyIfNoError=FLOW"])
            elif self.mode == "sourcepath" and self.sourcepaths:
                cmd.extend(["-sourcepath", ":".join(str(p) for p in self.sourcepaths)])

            cmd.append(str(java_file))

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    return (java_file, True, "")

                stderr = result.stderr

                if self.mode == "parse-only":
                    if is_parse_error(stderr):
                        return (java_file, False, stderr[:500])
                    return (java_file, True, "")

                return (java_file, False, stderr[:500])

            except subprocess.TimeoutExpired:
                return (java_file, False, "timeout")
            except Exception as e:
                return (java_file, False, str(e))


def main():
    parser = argparse.ArgumentParser(
        description="Build a whitelist of Java files for parser testing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  isolated    Each file must compile completely in isolation.
              Most restrictive - only self-contained files pass.

  sourcepath  Files compile with source path for dependency resolution.
              Allows files that depend on other project files.

  parse-only  Only reject files with actual parse/syntax errors.
              Most permissive - semantic errors are ignored.
              Best for parser testing.

Examples:
  %(prog)s --mode parse-only --output whitelist_parse.txt
  %(prog)s --mode sourcepath -j 8
  %(prog)s ../jdk8u_langtools --mode isolated
"""
    )

    parser.add_argument(
        "base_dir",
        nargs="?",
        default=None,
        help="Base directory containing Java files (default: ../jdk8u_langtools)"
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["isolated", "sourcepath", "parse-only"],
        default="parse-only",
        help="Compilation mode (default: parse-only)"
    )
    parser.add_argument(
        "-o", "--output",
        default="whitelist.txt",
        help="Output file for whitelist (default: whitelist.txt)"
    )
    parser.add_argument(
        "-e", "--errors",
        default="compile_errors.txt",
        help="Output file for error details (default: compile_errors.txt)"
    )
    parser.add_argument(
        "-j", "--jobs",
        type=int,
        default=None,
        help="Number of parallel jobs (default: CPU count)"
    )
    parser.add_argument(
        "--java-version",
        default="1.8",
        help="Java source/target version (default: 1.8)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show progress every 100 files instead of 500"
    )

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    if args.base_dir:
        base_dir = Path(args.base_dir)
    else:
        base_dir = script_dir.parent / "jdk8u_langtools"

    if not base_dir.exists():
        print(f"Error: {base_dir} does not exist")
        sys.exit(1)

    output_file = script_dir / args.output
    errors_file = script_dir / args.errors
    num_workers = args.jobs or os.cpu_count() or 4
    progress_interval = 100 if args.verbose else 500

    print(f"Base directory: {base_dir}")
    print(f"Mode: {args.mode}")
    print(f"Java version: {args.java_version}")
    print(f"Output: {output_file}")

    builder = WhitelistBuilder(base_dir, args.mode, args.java_version)

    java_files = list(base_dir.rglob("*.java"))
    print(f"Found {len(java_files)} Java files")
    print(f"Testing with {num_workers} workers...")

    passed = []
    failed = []

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(builder.test_file, f): f for f in java_files}

        for i, future in enumerate(as_completed(futures)):
            java_file, success, error = future.result()
            if success:
                passed.append(java_file)
            else:
                failed.append((java_file, error))

            if (i + 1) % progress_interval == 0:
                print(f"Progress: {i + 1}/{len(java_files)} "
                      f"({len(passed)} passed, {len(failed)} failed)")

    with open(output_file, "w") as f:
        for java_file in sorted(passed):
            f.write(f"{java_file}\n")

    print(f"\nResults:")
    print(f"  Passed: {len(passed)}")
    print(f"  Failed: {len(failed)}")
    print(f"  Whitelist saved to: {output_file}")

    with open(errors_file, "w") as f:
        for java_file, error in sorted(failed, key=lambda x: str(x[0])):
            f.write(f"=== {java_file} ===\n{error}\n\n")
    print(f"  Errors saved to: {errors_file}")


if __name__ == "__main__":
    main()
