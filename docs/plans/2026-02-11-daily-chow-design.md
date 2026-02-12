# Daily Chow — Interactive Meal Macro Solver TUI

**Date:** 2026-02-11

## Problem

Given a set of whole-food ingredients and daily nutrition targets (calories, protein, fiber), find the grams of each ingredient that satisfy all constraints. Make it interactive: the user adjusts ingredient ranges with sliders, and the CP-SAT solver re-solves in real time.

## Stack

- **Python 3.13+**, managed with `uv`
- **Google OR-Tools CP-SAT** — constraint solver
- **Textual** — TUI framework (rich widgets, mouse support, CSS-like styling)
- Single project: `~/code/daily-chow/`

## Screen Layout

```
┌─ Daily Chow ──────────────────────────────────────────────────────────────┐
│ Targets: 3500 kcal │ 160g protein │ ≥40g fiber        [Minimize oil ▾]   │
│ Smoothie: 720 kcal │ 30g pro │ 14g fiber                                 │
├─ Ingredients ─────────────────────────────────────────────────────────────┤
│                                                                           │
│ [x] Rice (dry)         0 ├░░░░░░░░●━━━━━━━━━━━━━┤ 400g   287g  1048/20  │
│ [x] Broccoli         200 ├━━━━━━━━━●━━━━━━━━━━━━┤ 400g   300g   102/8   │
│ [x] Carrots          150 ├━━━━━━●━━━━━━━━━━━━━━━┤ 300g   200g    82/2   │
│ [x] Zucchini         250 ├━━━━━━━━●━━━━━━━━━━━━━┤ 500g   312g    53/4   │
│ [x] Avocado oil        0 ├●━━━━━━━━━━━━━━━━━━━━━┤ 100g    18g   159/0   │
│ [x] Black beans (ckd)150 ├━━━━━━●━━━━━━━━━━━━━━━┤ 400g   200g   264/18  │
│ [x] Split peas (dry)  60 ├━━●━━━━━━━━━━━━━━━━━━━┤ 150g    80g   282/19  │
│ [x] Ground beef        0 ├━━━━━●━━━━━━━━━━━━━━━━┤1000g   310g   787/53  │
│ [x] Chicken thigh      0 ├━━━━━━●━━━━━━━━━━━━━━━┤1000g   326g   681/85  │
│                                                       [+ Add ingredient] │
├─ Totals ──────────────────────────────────────────────────────────────────┤
│ Meal:  2780 kcal │ 130g pro │ 40g fiber              ✓ FEASIBLE          │
│ Day:   3500 kcal │ 160g pro │ 54g fiber                                  │
└───────────────────────────────────────────────────────────────────────────┘
```

### Ingredient row anatomy

Each row contains:
- **Checkbox** — toggle ingredient in/out of the solver model
- **Name** — from the built-in food database
- **Range bar** — visual slider where `├` and `┤` are draggable min/max endpoints, `●` marks the solved value. `░` = range below solved, `━` = range above solved
- **Min/max labels** — numeric, at the ends of the bar
- **Solved grams** — the solver's answer for this ingredient
- **kcal / protein** — this ingredient's macro contribution at the solved quantity

### Header

- **Targets** — editable daily totals for calories, protein, minimum fiber
- **Smoothie** — fixed contribution subtracted from targets to get meal targets. Editable.
- **Objective dropdown** — select optimization objective

### Totals panel

- **Meal totals** — sum of all ingredient contributions (what the solver optimizes)
- **Day totals** — meal + smoothie
- **Feasibility indicator** — green checkmark or red X with explanation of which constraint is violated

## Interaction Model

1. **Adjust slider range** — drag min or max endpoint of any ingredient's range bar. Solver re-runs instantly. All solved values update.
2. **Toggle ingredient** — uncheck to remove from model (grams fixed to 0). Solver re-runs.
3. **Add ingredient** — opens modal with fuzzy-search against built-in food database. Select one, it appears with default bounds (0..500g). Solver re-runs.
4. **Remove ingredient** — keybinding (e.g. `d` or `Delete`) on focused row removes it entirely.
5. **Edit targets** — click on target values in header to edit. Solver re-runs.
6. **Change objective** — dropdown cycles through objectives. Solver re-runs.

Every mutation triggers a solver re-run. CP-SAT solves this size problem (~9 variables, ~15 constraints) in <10ms, so it feels instant.

## Solver Design

### Scaling

CP-SAT requires integer variables and coefficients. Decision variables are already integer grams. Nutrition coefficients (per 100g, with decimals) are scaled:

- **SCALE = 100**
- `coeff_scaled = round(nutrient_per_100g * SCALE / 100)` → integer per-gram coefficient
- `target_scaled = target * SCALE`
- Tolerance scaled the same way

Worst-case rounding error: ~0.5 units per gram per ingredient. Over realistic quantities and with tolerances of 50 kcal / 5g protein, this is negligible.

### Model (per solve)

**Variables:** One `IntVar` per enabled ingredient, domain = `[min_slider, max_slider]`.

**Constraints:**
- `|sum(cal_coeff[i] * x[i]) - meal_cal_target_scaled| <= cal_tolerance_scaled`
- `|sum(pro_coeff[i] * x[i]) - meal_pro_target_scaled| <= pro_tolerance_scaled`
- `sum(fib_coeff[i] * x[i]) >= meal_fiber_min_scaled`

Implemented via `AddAbsEquality` + auxiliary variables for the absolute-value constraints.

**Tolerances (defaults):**
- Calorie tolerance: 50 kcal
- Protein tolerance: 5 g

**Objectives (selectable):**
- **A: Minimize oil** — `Minimize(oil_grams)`. Default.
- **B: Minimize rice deviation** — `Minimize(|rice - preferred|)` where preferred = 200g dry.
- **C: Minimize cost** — `Minimize(sum(cost_per_g[i] * x[i]))`. Requires cost data.

### Infeasibility handling

If the solver returns INFEASIBLE, display a red status. No automatic relaxation — the user has direct control over all bounds and can widen ranges themselves. The TUI makes this obvious: "INFEASIBLE — try widening ranges or disabling an ingredient."

## Built-in Food Database

A Python dict of ~50-100 common whole foods, keyed by slug. Each entry:

```python
{
    "name": "White rice, dry",
    "unit_note": "dry, uncooked",
    "cal_per_100g": 365,
    "protein_per_100g": 7.0,
    "fiber_per_100g": 1.0,
    "default_min": 0,
    "default_max": 500,
}
```

Fuzzy search via simple substring/prefix matching (no external deps). Categories for browsing: grains, vegetables, legumes, meats, oils/fats, dairy, fruits, nuts/seeds.

## Persistence

Auto-save to `~/.config/daily-chow/state.json` on every change:

```json
{
    "targets": {"calories": 3500, "protein": 160, "fiber_min": 40},
    "smoothie": {"calories": 720, "protein": 30, "fiber": 14},
    "objective": "minimize_oil",
    "tolerances": {"calories": 50, "protein": 5},
    "ingredients": [
        {"key": "white_rice_dry", "enabled": true, "min": 0, "max": 400},
        {"key": "broccoli_raw", "enabled": true, "min": 200, "max": 400}
    ]
}
```

- On launch: load state if exists, else use defaults (the original spec's 9 ingredients with the spec's bounds).
- Nutrition coefficients come from the built-in database in code, not the state file.

## Project Structure

```
daily-chow/
├── pyproject.toml          # uv project, deps: ortools, textual
├── src/
│   └── daily_chow/
│       ├── __init__.py
│       ├── app.py          # Textual App, screen layout, event handling
│       ├── solver.py       # CP-SAT model build + solve
│       ├── food_db.py      # Built-in food database dict
│       ├── state.py        # Load/save state JSON
│       └── widgets.py      # Custom Textual widgets (range slider, ingredient row)
├── tests/
│   ├── test_solver.py      # Solver unit tests (feasibility, known solutions)
│   └── test_state.py       # State round-trip tests
└── docs/
    └── plans/
        └── 2026-02-11-daily-chow-design.md  # This file
```

Not a single flat script anymore — Textual apps benefit from separation between solver logic, UI, and data. Still a small project (~5 source files).

## Default Ingredients (from original spec)

| Ingredient | Unit | cal/100g | pro/100g | fib/100g | Default min | Default max |
|---|---|---|---|---|---|---|
| White rice | dry | 365 | 7.0 | 1.0 | 0 | 400 |
| Broccoli | raw | 34 | 2.8 | 2.6 | 200 | 400 |
| Carrots | raw | 41 | 0.9 | 2.8 | 150 | 300 |
| Zucchini | raw | 17 | 1.2 | 1.0 | 250 | 500 |
| Avocado oil | — | 884 | 0.0 | 0.0 | 0 | 100 |
| Black beans | cooked | 132 | 8.9 | 8.7 | 150 | 400 |
| Yellow split peas | dry | 352 | 24.0 | 25.0 | 60 | 150 |
| Ground beef 80/20 | raw | 254 | 17.0 | 0.0 | 0 | 1000 |
| Chicken thigh | raw | 209 | 26.0 | 0.0 | 0 | 1000 |
