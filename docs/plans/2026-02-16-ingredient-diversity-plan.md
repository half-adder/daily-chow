# Ingredient Diversity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add L2 regularization (sum-of-squares) to the solver to penalize one ingredient dominating by gram weight.

**Architecture:** New `PRIORITY_INGREDIENT_DIVERSITY` objective term in the lexicographic chain. Computes Σ(gram_i²) via CP-SAT's `add_multiplication_equality`, normalizes to `[0, PCT_SCALE]`, and slots between macro_ratio and total_weight priorities.

**Tech Stack:** Python (ortools CP-SAT), SvelteKit frontend, uv for Python, bun for JS.

---

### Task 1: Add diversity objective to solver (test first)

**Files:**
- Modify: `tests/test_solver.py`
- Modify: `src/daily_chow/solver.py`

**Step 1: Write the failing test**

Add to `tests/test_solver.py`:

```python
from daily_chow.solver import PRIORITY_INGREDIENT_DIVERSITY

class TestIngredientDiversity:
    def test_diversity_spreads_grams(self):
        """With diversity enabled, no single ingredient should dominate.

        Compare solutions with and without diversity priority.
        The diversity-enabled solution should have a lower max-ingredient
        gram count (more even spread).
        """
        ingredients = _default_ingredients()
        sol_no_div = solve(
            ingredients,
            priorities=[PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        sol_div = solve(
            ingredients,
            priorities=[PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_INGREDIENT_DIVERSITY, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol_no_div.status in ("optimal", "feasible")
        assert sol_div.status in ("optimal", "feasible")

        max_no_div = max(i.grams for i in sol_no_div.ingredients)
        max_div = max(i.grams for i in sol_div.ingredients)
        assert max_div <= max_no_div, (
            f"Diversity should reduce max ingredient: {max_div}g vs {max_no_div}g"
        )

    def test_diversity_does_not_degrade_micros(self):
        """Micros priority is above diversity — micro coverage should not suffer."""
        ingredients = _default_ingredients()
        micro_targets = {"iron_mg": 4.9, "calcium_mg": 500.0}

        sol_no_div = solve(
            ingredients,
            micro_targets=micro_targets,
            priorities=[PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        sol_div = solve(
            ingredients,
            micro_targets=micro_targets,
            priorities=[PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_INGREDIENT_DIVERSITY, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol_div.status in ("optimal", "feasible")

        # Micro coverage should be equal or better (within rounding)
        for key in micro_targets:
            no_div_val = sol_no_div.micro_totals.get(key, 0.0)
            div_val = sol_div.micro_totals.get(key, 0.0)
            assert div_val >= no_div_val - 0.5, (
                f"{key}: diversity degraded coverage {div_val:.1f} vs {no_div_val:.1f}"
            )

    def test_diversity_feasible_with_all_priorities(self):
        """Diversity should work alongside all other objective tiers without overflow."""
        ingredients = _default_ingredients()
        micro_targets = {
            "iron_mg": 10.0, "calcium_mg": 800.0, "magnesium_mg": 300.0,
            "zinc_mg": 8.0, "vitamin_c_mg": 60.0,
        }
        ratio = MacroRatio(carb_pct=50, protein_pct=25, fat_pct=25)
        constraints = [MacroConstraint("protein", "gte", 130, hard=False)]

        sol = solve(
            ingredients,
            micro_targets=micro_targets,
            macro_ratio=ratio,
            macro_constraints=constraints,
            priorities=[PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_INGREDIENT_DIVERSITY, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol.status in ("optimal", "feasible")
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_solver.py::TestIngredientDiversity -v`
Expected: ImportError on `PRIORITY_INGREDIENT_DIVERSITY`

**Step 3: Implement the solver changes**

In `src/daily_chow/solver.py`:

1. Add the new priority constant (after existing ones, ~line 31):
```python
PRIORITY_INGREDIENT_DIVERSITY = "ingredient_diversity"
DEFAULT_PRIORITIES = [PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_INGREDIENT_DIVERSITY, PRIORITY_TOTAL_WEIGHT]
```

2. After the `total_grams` computation (~line 400), add the diversity objective:
```python
# ── Ingredient diversity (L2 regularization) ─────────────────────
# Minimize sum of squared grams to encourage even distribution.
# sum(gram_i^2) is minimized when grams are spread evenly.
sum_sq: cp_model.LinearExprT = 0
max_sum_sq = 0
for ing in ingredients:
    sq_var = model.new_int_var(0, ing.max_g ** 2, f"sq_{ing.key}")
    model.add_multiplication_equality(sq_var, [gram_vars[ing.key], gram_vars[ing.key]])
    sum_sq = sum_sq + sq_var
    max_sum_sq += ing.max_g ** 2

# Normalize to [0, PCT_SCALE]
diversity_var: cp_model.IntVar | None = None
max_diversity = 0
if max_sum_sq > 0:
    diversity_var = model.new_int_var(0, PCT_SCALE, "diversity_pct")
    model.add(diversity_var * max_sum_sq >= sum_sq * PCT_SCALE)
    max_diversity = PCT_SCALE
```

3. In the priority loop (~line 426), add the new case:
```python
elif p == PRIORITY_INGREDIENT_DIVERSITY:
    if diversity_var is not None and max_diversity > 0:
        terms.append((diversity_var, max_diversity))
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_solver.py -v`
Expected: All tests PASS (including existing tests — no regressions)

**Step 5: Commit**

```bash
git add src/daily_chow/solver.py tests/test_solver.py
git commit -m "feat: add ingredient diversity via L2 regularization in solver"
```

---

### Task 2: Update frontend priorities

**Files:**
- Modify: `frontend/src/routes/+page.svelte`

**Step 1: Update default priorities array**

At line 70, change:
```javascript
let priorities = $state<string[]>(['micros', 'macro_ratio', 'total_weight']);
```
to:
```javascript
let priorities = $state<string[]>(['micros', 'macro_ratio', 'ingredient_diversity', 'total_weight']);
```

**Step 2: Add migration logic for saved states**

After the `macro_ratio` backfill block (~line 392), add:
```javascript
// Backfill ingredient_diversity into old priority lists
if (!priorities.includes('ingredient_diversity')) {
    const idx = priorities.indexOf('total_weight');
    if (idx >= 0) priorities.splice(idx, 0, 'ingredient_diversity');
    else priorities.push('ingredient_diversity');
}
```

**Step 3: Update fallback default**

At line 394, update the fallback:
```javascript
priorities = ['micros', 'macro_ratio', 'ingredient_diversity', 'total_weight'];
```

**Step 4: Add label mapping in priority display**

At line 601, the label ternary chain. Change:
```javascript
<span class="priority-label">{p === 'micros' ? 'Micronutrient coverage' : p === 'macro_ratio' ? 'Macro ratio target' : 'Minimize total weight'}</span>
```
to:
```javascript
<span class="priority-label">{p === 'micros' ? 'Micronutrient coverage' : p === 'macro_ratio' ? 'Macro ratio target' : p === 'ingredient_diversity' ? 'Ingredient diversity' : 'Minimize total weight'}</span>
```

**Step 5: Verify in browser**

Open the app, check that:
1. "Ingredient diversity" appears as priority #3 in the list
2. It's reorderable with up/down arrows
3. Solving produces a result (no errors in console)

**Step 6: Commit**

```bash
git add frontend/src/routes/+page.svelte
git commit -m "feat: add ingredient diversity to frontend priority list"
```

---

### Task 3: Manual verification & cleanup

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

**Step 2: Test in browser with real data**

Open the app with the dev server, enable several ingredients, and verify:
- With diversity enabled (default position), grams are more evenly spread
- Reordering diversity above/below other priorities changes the solution
- No console errors

**Step 3: Final commit if any fixups needed**
