# Testing Conventions

## Framework and Tools

- **pytest** for test runner
- **pytest-asyncio** with `asyncio_mode = "auto"` (no need for `@pytest.mark.asyncio` on individual tests within async test classes)
- **hypothesis** for property-based tests

## Directory Structure

```
tests/
├── property/     # Property-based tests (hypothesis)
├── unit/         # Unit tests (fast, isolated)
└── integration/  # Integration tests (may use real subprocesses)
```

## Running Tests

```bash
python -m pytest tests/ -v          # All tests
python -m pytest tests/unit/ -v     # Unit only
python -m pytest tests/property/ -v # Property tests only
```

## Conventions

- Test files mirror source: `src/config.py` → `tests/unit/test_config.py`
- Group tests in classes by behavior area (e.g., `TestWrapperConfigValidation`)
- Use `tmp_path` fixture for any file I/O tests
- Use `unittest.mock` and `AsyncMock` for isolating components — don't test through the full stack in unit tests
- Async tests: use `async def test_*` methods inside classes — pytest-asyncio handles the event loop
- Property tests use `@settings(max_examples=100)` minimum
- Each property test file includes a comment referencing the design property number

## What to Test

- All public methods of each component
- Error paths (file not found, connection refused, timeout, invalid input)
- Guard conditions in the state machine (start while running, stop while stopped)
- Edge cases: empty RCON responses, malformed INI files, port conflicts

## What NOT to Test

- Private methods directly (test through public API)
- Third-party library internals (mock at the boundary)
- Exact log message wording (test that logging occurs, not the exact string)
