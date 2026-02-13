# Macro Ratio Target Design

## Goal

Add a user-settable carb/protein/fat calorie ratio as a soft optimization target. The solver tries to match the desired ratio but can deviate when other hard constraints (calorie band, protein floor, fiber floor) take priority.

## UI: Macro Ratio Target Bar

New component in the left-column settings area, below existing calorie/fiber targets.

- Horizontal stacked bar with three colored segments: carb, protein, fat
- Each segment contains an editable text label: `Carb: 50%`, `Pro: 25%`, `Fat: 25%`
- Two draggable vertical dividers at segment boundaries with grip visual (two vertical lines)
- **Drag behavior**: neighbors-only. Dragging the carb/protein divider trades space between carb and protein; fat unchanged. Vice versa for protein/fat divider.
- **Text input**: clicking percentage makes it editable. New value adjusts that segment and its right neighbor (left if fat). Values clamped to >= 5% minimum, sum to 100%.
- **Default ratio**: 50% carb / 25% protein / 25% fat

## Solver Changes

### Protein constraint: band -> floor

Current: `protein_target ± tolerance` (hard band constraint)
New: `protein >= minimum` (hard floor constraint). Protein tolerance removed.

### Macro ratio: new soft objective

Added to the priority list alongside "micros" and "total_weight". Default order: **micros > macro_ratio > total_weight**.

The solver:
1. Computes actual calorie split: `carbCal = carbs_g * 4`, `proCal = protein_g * 4`, `fatCal = fat_g * 9`
2. Computes deviation from target percentages for each macro
3. Minimizes worst-case deviation (minimax approach, consistent with micro shortfall optimization)

### Hard constraints (unchanged except protein)

- Calories: target ± tolerance (band)
- Protein: >= minimum (floor, was band)
- Fiber: >= minimum (floor)
- Ingredient bounds: per-ingredient min/max grams
- Micro ULs: hard upper limits when applicable

## Data Flow

Frontend sends new fields in `/api/solve`:
- `macro_ratio: { carb_pct: 50, protein_pct: 25, fat_pct: 25 }`
- `meal_protein_min_g` replaces `meal_protein_g` + `protein_tolerance`
- `priorities` list gains `"macro_ratio"` option

Response unchanged — already returns `meal_carbs_g`, `meal_protein_g`, `meal_fat_g`.

## Files to Change

- **`frontend/src/lib/components/MacroRatioBar.svelte`** (new) — Draggable stacked bar with inline text inputs
- **`frontend/src/routes/+page.svelte`** — Add ratio bar, wire state, update solve request, replace protein tolerance with floor, add "macro_ratio" to priority list
- **`frontend/src/lib/api.ts`** — Update request type
- **`src/daily_chow/solver.py`** — Protein floor, macro ratio soft objective
- **`src/daily_chow/api.py`** — Update request model
- **`tests/`** — Solver tests for ratio objective and protein floor

## Not in Scope

No changes to food DB, DRI tables, contributions, or the results macro bar.
