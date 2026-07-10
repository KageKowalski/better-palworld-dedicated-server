# Coding Standards

## Language and Runtime

- Python 3.11+ with type hints on all public functions and methods
- Use `asyncio` for all I/O-bound and concurrent operations — no threading unless wrapping a synchronous library
- Use `dataclasses` for data models — avoid Pydantic or attrs unless a compelling reason arises

## Style

- Module-level docstrings explaining purpose in 1–2 sentences
- Class and public method docstrings using Google-style (Args/Returns/Raises)
- Use `from __future__ import annotations` only if needed for forward refs
- Prefer `X | None` over `Optional[X]`
- Prefer `list[X]` over `List[X]` (use lowercase generics)
- Import order: stdlib → third-party → local (`src.*`)
- Use `logging.getLogger(__name__)` per module — never print for operational output except in ManagementInterface

## Architecture Patterns

- Each component lives in its own module under `src/`
- Components communicate through callbacks and result dataclasses — no shared mutable state
- The `WrapperCore` is the only class that holds references to all components
- Result types (`StartResult`, `StopResult`, etc.) are returned instead of raising exceptions for expected failures
- Unexpected exceptions are caught at component boundaries, logged, and the wrapper continues running

## Error Handling

- Never crash the wrapper process — catch and log at the top level
- Use result dataclasses for expected error paths (file not found, timeout, invalid input)
- Use exceptions only for truly unexpected/programmer errors
- RCON failures preserve the last known state — never reset player count on error

## Naming

- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private methods/attributes: single underscore prefix `_`
