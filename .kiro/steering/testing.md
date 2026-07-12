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
- Feature-specific test files group related tests: `tests/unit/test_management_interface.py` for ManagementInterface behavior
- Group tests in classes by behavior area (e.g., `TestWrapperConfigValidation`, `TestTypeValidationErrors`, `TestAutoCorrectionFeedback`)
- Use `tmp_path` fixture for any file I/O tests
- Use `unittest.mock` and `AsyncMock` for isolating components — don't test through the full stack in unit tests
- Async tests: use `async def test_*` methods inside classes — pytest-asyncio handles the event loop
- Property tests use `@settings(max_examples=100)` minimum
- Each property test file includes a comment referencing the design property number
- For bugfixes: write exploration tests (expected to fail on unfixed code) and preservation tests (must pass before and after fix) — see `tests/property/test_bug_conditions.py` and `tests/property/test_preservation.py` for examples
- Use `deadline=None` in hypothesis settings for async tests that involve mocked `asyncio.sleep` or network I/O

## GUI Testing

- **Mock-based approach (preferred for unit tests):** Patch `tk.Tk` and related tkinter objects to test GUI logic without a display. See `tests/unit/test_gui_interface.py` and `tests/unit/test_control_panel.py` for examples.
- **Display-dependent tests:** Tests requiring a live display use `pytest.importorskip("tkinter")` and skip gracefully when `$DISPLAY` is unavailable. In CI, these run under `xvfb-run`.
- **Widget state assertions:** Use `.cget("state")` or `.instate(["disabled"])` to verify button enable/disable logic.
- **Async GUI tests:** Mock `root.update()` and test the async `run()` method's cooperative scheduling behavior with controlled iterations.

## What to Test

- All public methods of each component
- Error paths (file not found, connection refused, timeout, invalid input)
- Guard conditions in the state machine (start while running, stop while stopped)
- Edge cases: empty RCON responses, malformed INI files, port conflicts

## What NOT to Test

- Private methods directly (test through public API)
- Third-party library internals (mock at the boundary)
- Exact log message wording (test that logging occurs, not the exact string)
