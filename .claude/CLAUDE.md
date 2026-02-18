# Daily Chow - Project Instructions

## JavaScript/Frontend Tooling

**Always use `bun` for JavaScript package management and script execution.** Never use npm, yarn, or npx. Use `bun run` for running scripts.

## Python Tooling

**Always use `uv` for Python package management and script execution.** Never use pip, pip3, or python directly. Use `uv run` for running scripts with dependencies.

## Mobile UI: Overflow Verification

After any mobile UI change, take a screenshot at 390×844 and verify:
- No content overflows its parent container (check all edges)
- CSS grid children have `min-width: 0` to prevent blowout
- Fixed-width inputs inside flex/grid layouts use `width: 100%` + `min-width: 0` (not bare fixed px) unless the parent has a known constrained width
- The Playwright browser can be used for quick visual checks
