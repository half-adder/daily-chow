# Daily Chow - Project Instructions

## JavaScript/Frontend Tooling

**Always use `bun` for JavaScript package management and script execution.** Never use npm, yarn, or npx. Use `bun run` for running scripts.

## Python Tooling

**Always use `uv` for Python package management and script execution.** Never use pip, pip3, or python directly. Use `uv run` for running scripts with dependencies.

## UI: Overflow Verification

After any UI change, take a screenshot and verify no content overflows its container. Common pitfalls:
- CSS grid children default to `min-width: auto` — add `min-width: 0` to prevent column blowout
- Fixed-width inputs inside flex/grid use `width: 100%` + `min-width: 0` rather than bare `px` widths
- Check at relevant viewport sizes (desktop and 390×844 mobile if the change affects both)
