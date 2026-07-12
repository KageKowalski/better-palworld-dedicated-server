---
inclusion: always
description: Directives for updating documentation at the completion of every spec project.
globs: "**/*"
---

# Documentation Updates

At the completion of every spec project (specifically during the final task), documentation must be updated to reflect the work performed during that spec. This applies to both the root README.md and the .kiro/ documentation.

## README.md (Root)

- **Audience:** Human operators of the application (not developers or bots)
- Update with any new usage instructions, configuration options, environment variables, or operational changes introduced by the spec
- Keep language accessible and focused on "how to run/use/configure" the application
- Do NOT include implementation details, architectural decisions, or developer-facing notes here

## .kiro/ Documentation

- **Audience:** Bots and developers
- Update with architectural decisions, new module descriptions, design patterns, technical constraints, and any context that would help a bot or developer understand and work with the codebase
- Reflect any new files, services, or structural changes introduced by the spec
