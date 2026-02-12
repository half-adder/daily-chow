# Daily Chow — Svelte + FastAPI Redesign

**Date:** 2026-02-11
**Supersedes:** 2026-02-11-daily-chow-design.md (Textual TUI approach)

## Why the change

The Textual TUI approach had fundamental layout issues — range sliders were invisible due to CSS box model conflicts, Input widgets clipped numbers, and terminal rendering was unreliable. A web UI gives us native HTML range inputs, proper CSS layout, and a much better interactive experience.

## Architecture

```
┌─────────────────────────┐     fetch()      ┌──────────────────────┐
│  SvelteKit Frontend     │ ──────────────── │  FastAPI Backend     │
│  localhost:5173          │    JSON           │  localhost:8000      │
│                         │                   │                      │
│  Range sliders          │  POST /solve      │  solver.py (CP-SAT)  │
│  Checkboxes             │  ──────────────►  │  food_db.py          │
│  Target inputs          │                   │  ~10ms per solve     │
│  Macro display          │  ◄──────────────  │                      │
│                         │  Solution JSON    │                      │
└─────────────────────────┘                   └──────────────────────┘
```

- **Frontend**: SvelteKit (Svelte 5) — single page, no routing needed
- **Backend**: FastAPI wrapping existing solver.py and food_db.py
- **Communication**: JSON over HTTP on localhost
- **Two dev processes**: `uv run fastapi dev` + `npm run dev`

OR-Tools imports once at FastAPI startup. Each solve request is ~10ms.

## API Endpoints

### `GET /foods`
Returns the full food database for ingredient search.
```json
{
  "foods": {
    "white_rice_dry": {
      "name": "White rice",
      "unit_note": "dry",
      "cal_per_100g": 365,
      "protein_per_100g": 7.0,
      "fiber_per_100g": 1.0,
      "category": "grains",
      "default_min": 0,
      "default_max": 500
    }
  }
}
```

### `POST /solve`
Accepts ingredients + targets + objective, returns solution.

Request:
```json
{
  "ingredients": [
    {"key": "white_rice_dry", "min_g": 0, "max_g": 400},
    {"key": "broccoli_raw", "min_g": 200, "max_g": 400}
  ],
  "targets": {
    "meal_calories": 2780,
    "meal_protein": 130,
    "meal_fiber_min": 26,
    "cal_tolerance": 50,
    "protein_tolerance": 5
  },
  "objective": "minimize_oil"
}
```

Response:
```json
{
  "status": "optimal",
  "ingredients": [
    {"key": "white_rice_dry", "grams": 253, "calories": 923.5, "protein": 17.7, "fiber": 2.5},
    {"key": "broccoli_raw", "grams": 200, "calories": 68.0, "protein": 5.6, "fiber": 5.2}
  ],
  "meal_calories": 2780.1,
  "meal_protein": 130.2,
  "meal_fiber": 47.3
}
```

## UI Layout

### Top bar — editable targets
```
Daily Targets: [3500] kcal  [160]g protein  ≥[40]g fiber
Smoothie:      [720] kcal   [30]g protein   [14]g fiber
Tolerance:     ±[50] kcal   ±[5]g protein
Objective:     [Minimize oil ▾]
```

### Ingredient list — main interaction area
Each row:
```
☑ White rice (dry)  [0]──◀━━━━●━━━━━━━━▶──[400]g   253g   927 kcal / 18g pro
```
- Checkbox to enable/disable
- Name
- Dual range slider (two overlapping `<input type="range">`) — left = min, right = max
- Numeric min/max inputs flanking the slider (editable, synced with slider)
- Solved value marker (positioned overlay on the slider track)
- Solved grams (bold)
- Per-ingredient kcal/protein contribution

Bottom of list: `[+ Add ingredient]` button → search dropdown against food database.

### Totals bar — fixed at bottom
```
Meal:  2780 kcal │ 130g pro │ 47g fiber
Day:   3500 kcal │ 160g pro │ 61g fiber    ✓ OPTIMAL
```

## Interaction Model

Every change triggers a fetch to `/solve`:
1. **Drag slider handle** → update min or max → solve
2. **Type in min/max input** → sync slider → solve
3. **Toggle checkbox** → enable/disable ingredient → solve
4. **Add ingredient** → search food db, append with defaults → solve
5. **Remove ingredient** → delete row → solve
6. **Edit targets** → solve
7. **Change objective** → solve

## Persistence

**Client-side localStorage** for the ingredient list and settings. No server-side state. On page load, read from localStorage or fall back to defaults.

## Project Structure

```
daily-chow/
├── pyproject.toml              # uv project: ortools, fastapi, uvicorn
├── src/
│   └── daily_chow/
│       ├── __init__.py
│       ├── api.py              # FastAPI app with /foods and /solve endpoints
│       ├── solver.py           # CP-SAT model (existing, unchanged)
│       └── food_db.py          # Food database (existing, unchanged)
├── frontend/
│   ├── package.json
│   ├── svelte.config.js
│   ├── vite.config.ts
│   ├── src/
│   │   ├── app.html
│   │   ├── app.css
│   │   ├── routes/
│   │   │   └── +page.svelte    # Main (only) page
│   │   └── lib/
│   │       ├── components/
│   │       │   ├── IngredientRow.svelte
│   │       │   ├── DualRangeSlider.svelte
│   │       │   ├── TargetsBar.svelte
│   │       │   ├── TotalsBar.svelte
│   │       │   └── AddIngredientModal.svelte
│   │       ├── api.ts          # fetch wrappers for /solve and /foods
│   │       └── stores.ts       # Svelte stores for state + localStorage sync
│   └── static/
├── tests/
│   └── test_solver.py          # Existing solver tests (unchanged)
└── docs/
    └── plans/
```

## What to remove

- `src/daily_chow/app.py` (Textual app)
- `src/daily_chow/widgets.py` (Textual widgets)
- `src/daily_chow/state.py` (server-side persistence — replaced by localStorage)
- `textual` dependency from pyproject.toml
