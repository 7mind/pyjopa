"""Integration tests that compile and run complete Java programs."""
import subprocess
import tempfile
from pathlib import Path
import shutil
import pytest


class TestIntegration:
    """Integration tests for complete Java programs."""

    def run_java_test(self, java_file: str, main_class: str, expected_output: list[str]):
        """Helper to compile and run a Java file, checking output."""
        integration_dir = Path(__file__).parent / "integration"
        java_path = integration_dir / java_file

        assert java_path.exists(), f"Test file not found: {java_file}"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Copy Java file to temp directory
            test_file = tmpdir / java_file
            shutil.copy(java_path, test_file)

            # Compile
            result = subprocess.run(
                ["python", "-m", "pyjopa.cli", "compile", "-q", java_file],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Compilation failed: {result.stderr}"

            # Run
            result = subprocess.run(
                ["java", main_class],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Execution failed: {result.stderr}"

            # Check output
            output_lines = result.stdout.strip().split("\n")
            assert output_lines == expected_output, \
                f"Output mismatch.\nExpected: {expected_output}\nGot: {output_lines}"

    def test_bounded_types(self):
        """Test bounded type parameters (T extends Number)."""
        self.run_java_test("TestBoundedTypes.java", "TestBoundedTypes", ["10", "20"])

    def test_bridge_methods(self):
        """Test bridge methods for generic inheritance."""
        self.run_java_test("TestBridge.java", "TestBridge", ["hello", "world"])

    def test_wildcards_simple(self):
        """Test simple wildcard usage."""
        self.run_java_test("TestWildcardsSimple.java", "TestWildcardsSimple", ["42", "42"])

    def test_wildcards_comprehensive(self):
        """Test comprehensive wildcard usage (extends, super, unbounded)."""
        self.run_java_test("test_wildcards.java", "TestWildcards", ["1", "1", "2"])

    def test_nested_classes(self):
        """Test static nested classes."""
        self.run_java_test("test_nested.java", "Outer", ["42"])
