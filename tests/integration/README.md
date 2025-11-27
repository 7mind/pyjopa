# Integration Tests

This directory contains integration tests that compile and run complete Java programs.

## Test Files

- **TestBoundedTypes.java** - Tests bounded type parameters (`T extends Number`)
- **TestBridge.java** - Tests bridge methods generated for generic class inheritance
- **TestWildcardsSimple.java** - Tests simple wildcard usage (`? extends Number`, `?`)
- **test_wildcards.java** - Tests comprehensive wildcard usage (extends, super, unbounded)
- **test_nested.java** - Tests static nested classes (`Outer.Inner`)

## Running Tests

Integration tests are automatically run by pytest via `test_integration.py`.

To run manually:
```bash
cd tests/integration
python -m pyjopa.cli compile <file>.java
java <MainClass>
```
