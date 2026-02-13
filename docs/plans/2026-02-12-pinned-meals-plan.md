# Pinned Meals Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the hardcoded smoothie with a generalized "pinned meals" system where users can add, edit, and import meals with full macro/micro data.

**Architecture:** Frontend aggregates all pinned meal nutrients and subtracts from daily targets before sending to solver. Backend receives pinned micro totals in the solve request instead of using hardcoded values. JSON schema validates import format.

**Tech Stack:** SvelteKit 5 (runes), Python/FastAPI/Pydantic, OR-Tools CP-SAT solver, JSON Schema, bun (JS), uv (Python)

---

### Task 1: Macro Field Rename — Python Backend

Mechanical rename of macro field names to include units across all Python files.

**Files:**
- Modify: `src/daily_chow/food_db.py` (lines 19-25, 42-46, 79-83)
- Modify: `src/daily_chow/solver.py` (lines 42-47, 58-66, 70-78, 82-89, 113-123, 133-135, 267-277, 287-307, 321-328)
- Modify: `src/daily_chow/api.py` (lines 39-44, 57-64, 67-73, 76-84, 87-99, 113-117, 137-143, 181-201)

**Step 1: Rename food_db.py**

In `_MACRO_USDA_IDS` (lines 19-25), rename dict keys:
```python
_MACRO_USDA_IDS: dict[str, list[int]] = {
    "calories_kcal": [2047, 1008],
    "protein_g": [1003],
    "fat_g": [1004],
    "carbs_g": [1005],
    "fiber_g": [1079],
}
```

In `Food` dataclass (lines 42-46), rename fields:
```python
    calories_kcal_per_100g: float
    protein_g_per_100g: float
    fat_g_per_100g: float
    carbs_g_per_100g: float
    fiber_g_per_100g: float
```

In `_build_food()` (lines 79-83), update kwargs:
```python
        calories_kcal_per_100g=_extract_macro(nutrients, _MACRO_USDA_IDS["calories_kcal"]),
        protein_g_per_100g=_extract_macro(nutrients, _MACRO_USDA_IDS["protein_g"]),
        fat_g_per_100g=_extract_macro(nutrients, _MACRO_USDA_IDS["fat_g"]),
        carbs_g_per_100g=_extract_macro(nutrients, _MACRO_USDA_IDS["carbs_g"]),
        fiber_g_per_100g=_extract_macro(nutrients, _MACRO_USDA_IDS["fiber_g"]),
```

**Step 2: Rename solver.py**

`Targets` dataclass (lines 43-47):
```python
    meal_calories_kcal: int = 2780
    meal_protein_g: int = 130
    meal_fiber_min_g: int = 26
    cal_tolerance: int = 50
    protein_tolerance: int = 5
```

`SolvedIngredient` dataclass (lines 62-66):
```python
    calories_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    fiber_g: float
```

`Solution` dataclass (lines 73-78):
```python
    meal_calories_kcal: float
    meal_protein_g: float
    meal_fat_g: float
    meal_carbs_g: float
    meal_fiber_g: float
```

Update ALL usages throughout solve() function:
- Line 133: `ing.food.calories_kcal_per_100g` (was `cal_per_100g`)
- Line 134: `ing.food.protein_g_per_100g` (was `protein_per_100g`)
- Line 135: `ing.food.fiber_g_per_100g` (was `fiber_per_100g`)
- Lines 143-144: `targets.meal_calories_kcal` and `targets.cal_tolerance`
- Lines 150-151: `targets.meal_protein_g` and `targets.protein_tolerance`
- Line 157: `targets.meal_fiber_min_g`
- Lines 289-293: `ing.food.calories_kcal_per_100g`, `protein_g_per_100g`, `fat_g_per_100g`, `carbs_g_per_100g`, `fiber_g_per_100g`
- Lines 299-307: `SolvedIngredient` field names `calories_kcal=`, `protein_g=`, `fat_g=`, `carbs_g=`, `fiber_g=`
- Lines 114-123, 268-277: infeasible Solution field names
- Lines 321-328: final Solution field names

**Step 3: Rename api.py**

`TargetsRequest` (lines 40-44):
```python
class TargetsRequest(BaseModel):
    meal_calories_kcal: int = 2780
    meal_protein_g: int = 130
    meal_fiber_min_g: int = 26
    cal_tolerance: int = 50
    protein_tolerance: int = 5
```

`SolvedIngredientResponse` (lines 57-64):
```python
class SolvedIngredientResponse(BaseModel):
    key: int
    grams: int
    calories_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    fiber_g: float
```

`SolveResponse` (lines 76-84):
```python
class SolveResponse(BaseModel):
    status: str
    ingredients: list[SolvedIngredientResponse]
    meal_calories_kcal: float
    meal_protein_g: float
    meal_fat_g: float
    meal_carbs_g: float
    meal_fiber_g: float
    micros: dict[str, MicroResult] = {}
```

`FoodResponse` (lines 87-99):
```python
class FoodResponse(BaseModel):
    fdc_id: int
    name: str
    subtitle: str
    usda_description: str
    calories_kcal_per_100g: float
    protein_g_per_100g: float
    fat_g_per_100g: float
    carbs_g_per_100g: float
    fiber_g_per_100g: float
    category: str
    micros: dict[str, float] = {}
```

Update all assignment lines in `get_foods()` (lines 113-117) and `post_solve()` (lines 137-199) to use new field names.

**Step 4: Verify backend compiles**

Run: `uv run python -c "from daily_chow.api import app; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add src/daily_chow/food_db.py src/daily_chow/solver.py src/daily_chow/api.py
git commit -m "refactor: rename macro fields to include units (backend)"
```

---

### Task 2: Macro Field Rename — Frontend

Mechanical rename matching backend changes.

**Files:**
- Modify: `frontend/src/lib/api.ts` (lines 1-57, 64-79)
- Modify: `frontend/src/lib/contributions.ts` (lines 56-71, 113, 135)
- Modify: `frontend/src/routes/+page.svelte` (lines 121-123, 140-151, 210-212, 220-225, 247-249, 269-274, 338-356, 374-378, 547-555)
- Modify: `frontend/src/lib/components/IngredientRow.svelte` (lines 161, 163)
- Modify: `frontend/src/lib/components/AddIngredientModal.svelte` (line 78)

**Step 1: Rename api.ts**

```typescript
export interface Food {
	fdc_id: number;
	name: string;
	subtitle: string;
	usda_description: string;
	calories_kcal_per_100g: number;
	protein_g_per_100g: number;
	fat_g_per_100g: number;
	carbs_g_per_100g: number;
	fiber_g_per_100g: number;
	category: string;
	micros: Record<string, number>;
}

export interface SolveTargets {
	meal_calories_kcal: number;
	meal_protein_g: number;
	meal_fiber_min_g: number;
	cal_tolerance: number;
	protein_tolerance: number;
}

export interface SolvedIngredient {
	key: number;
	grams: number;
	calories_kcal: number;
	protein_g: number;
	fat_g: number;
	carbs_g: number;
	fiber_g: number;
}

export interface SolveResponse {
	status: string;
	ingredients: SolvedIngredient[];
	meal_calories_kcal: number;
	meal_protein_g: number;
	meal_fat_g: number;
	meal_carbs_g: number;
	meal_fiber_g: number;
	micros: Record<string, MicroResult>;
}
```

**Step 2: Rename contributions.ts**

Lines 56-71 — update property access:
```typescript
	const totalCal = solution.meal_calories_kcal || 1;
	const totalPro = solution.meal_protein_g || 1;
	const totalFat = solution.meal_fat_g || 1;
	const totalCarb = solution.meal_carbs_g || 1;
	const totalFiber = solution.meal_fiber_g || 1;

	for (const ing of solution.ingredients) {
		const food = foods[ing.key];
		if (!food) continue;

		const macroPcts: MacroPcts = {
			cal: (ing.calories_kcal / totalCal) * 100,
			pro: (ing.protein_g / totalPro) * 100,
			fat: (ing.fat_g / totalFat) * 100,
			carb: (ing.carbs_g / totalCarb) * 100,
			fiber: (ing.fiber_g / totalFiber) * 100,
		};
```

Lines 113, 135 — update `mr.smoothie` references (rename to `mr.pinned` happens in Task 5, leave as `smoothie` for now).

**Step 3: Rename +page.svelte**

Update all `solution.meal_calories` → `solution.meal_calories_kcal`, `solution.meal_protein` → `solution.meal_protein_g`, etc. throughout. Key locations:

- Lines 140-151 (macroPcts): `solution.meal_carbs_g`, `solution.meal_protein_g`, `solution.meal_fat_g`
- Lines 210-212 (infeasible default): `meal_calories_kcal: 0, meal_protein_g: 0, meal_fat_g: 0, meal_carbs_g: 0, meal_fiber_g: 0`
- Lines 220-225 (solve call targets): `meal_calories_kcal: mealCal, meal_protein_g: mealPro, meal_fiber_min_g: mealFiberMin`
- Lines 338-356 (macroStackedSegments): `ing.calories_kcal`, `ing.protein_g`, `ing.fat_g`, `ing.carbs_g`, `ing.fiber_g`
- Lines 547-555 (totals display): `solution.meal_calories_kcal`, `solution.meal_protein_g`, `solution.meal_fiber_g`

**Step 4: Rename IngredientRow.svelte**

Line 161: `solved.calories_kcal` (was `solved.calories`)
Line 163: `solved.protein_g` (was `solved.protein`)

**Step 5: Rename AddIngredientModal.svelte**

Line 78: `food.calories_kcal_per_100g`, `food.protein_g_per_100g`, `food.fiber_g_per_100g`

**Step 6: Verify frontend compiles**

Run: `cd frontend && bun run check`
Expected: No errors

**Step 7: Verify app works end-to-end**

Run backend: `uv run uvicorn daily_chow.api:app --port 8000`
Run frontend: `cd frontend && bun run dev`
Navigate to http://localhost:5173 — app should load and solve normally.

**Step 8: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/contributions.ts frontend/src/routes/+page.svelte frontend/src/lib/components/IngredientRow.svelte frontend/src/lib/components/AddIngredientModal.svelte
git commit -m "refactor: rename macro fields to include units (frontend)"
```

---

### Task 3: Fix Tests

The test file is broken — imports from deleted `daily_chow.usda` module and uses string-based food keys from pre-FDC era. Rewrite for current architecture.

**Files:**
- Modify: `tests/test_solver.py`

**Step 1: Rewrite test_solver.py**

Replace the entire file. Key changes:
- Import `load_foods` from `daily_chow.food_db` (not `daily_chow.usda`)
- Use FDC integer IDs instead of string slugs
- Use renamed field names (`meal_calories_kcal`, etc.)
- Remove the `MINIMIZE_RICE_DEVIATION` test (objective was removed)
- Remove `remaining_targets` import (will be deleted in Task 5)

Look up FDC IDs for test ingredients from the running app or foods.json. The default ingredients in the frontend are:
- White Rice: look up FDC ID from foods.json
- Broccoli, Carrots, Zucchini, Avocado Oil, Black Beans, Split Peas, Ground Beef, Chicken Thigh

Write a helper to find foods by name substring, since FDC IDs may change if the database is rebuilt.

```python
"""Tests for the CP-SAT meal solver."""

from daily_chow.food_db import load_foods
from daily_chow.solver import (
    IngredientInput,
    Objective,
    Solution,
    Targets,
    solve,
)

FOODS = load_foods()


def _find_food(name_substr: str) -> int:
    """Find a food FDC ID by name substring."""
    for fdc_id, food in FOODS.items():
        if name_substr.lower() in food.name.lower():
            return fdc_id
    raise KeyError(f"No food matching '{name_substr}'")


def _default_ingredients() -> list[IngredientInput]:
    """A representative set of ingredients for testing."""
    specs = [
        ("White Rice", 0, 400),
        ("Broccoli", 200, 400),
        ("Carrots", 150, 300),
        ("Zucchini", 250, 500),
        ("Avocado Oil", 0, 100),
        ("Black Beans", 150, 400),
        ("Split Peas", 60, 150),
        ("Ground Beef", 0, 1000),
        ("Chicken Thigh", 0, 1000),
    ]
    return [
        IngredientInput(_find_food(name), FOODS[_find_food(name)], min_g, max_g)
        for name, min_g, max_g in specs
    ]


def _grams_for(sol: Solution, name_substr: str) -> int:
    fdc_id = _find_food(name_substr)
    for ing in sol.ingredients:
        if ing.key == fdc_id:
            return ing.grams
    raise KeyError(f"Ingredient {name_substr} (FDC {fdc_id}) not in solution")


class TestSolverFeasibility:
    def test_default_ingredients_feasible(self):
        sol = solve(_default_ingredients())
        assert sol.status in ("optimal", "feasible")

    def test_empty_ingredients_infeasible(self):
        sol = solve([])
        assert sol.status == "infeasible"


class TestSolverConstraints:
    def test_calories_within_tolerance(self):
        targets = Targets()
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        assert abs(sol.meal_calories_kcal - targets.meal_calories_kcal) <= targets.cal_tolerance + 1

    def test_protein_within_tolerance(self):
        targets = Targets()
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        assert abs(sol.meal_protein_g - targets.meal_protein_g) <= targets.protein_tolerance + 3

    def test_fiber_meets_minimum(self):
        targets = Targets()
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_fiber_g >= targets.meal_fiber_min_g - 1


class TestSolverObjectives:
    def test_minimize_oil_produces_less_oil(self):
        ingredients = _default_ingredients()
        sol_oil = solve(ingredients, objective=Objective.MINIMIZE_OIL)
        sol_grams = solve(ingredients, objective=Objective.MINIMIZE_TOTAL_GRAMS)
        assert sol_oil.status in ("optimal", "feasible")
        assert sol_grams.status in ("optimal", "feasible")
        oil_min = _grams_for(sol_oil, "Avocado Oil")
        oil_other = _grams_for(sol_grams, "Avocado Oil")
        assert oil_min <= oil_other


class TestMicroOptimization:
    def test_micro_targets_feasible(self):
        sol = solve(_default_ingredients(), micro_targets={"iron_mg": 4.9})
        assert sol.status in ("optimal", "feasible")

    def test_micro_totals_populated(self):
        sol = solve(_default_ingredients())
        assert sol.status in ("optimal", "feasible")
        assert len(sol.micro_totals) > 0
        assert "calcium_mg" in sol.micro_totals
```

**Step 2: Run tests**

Run: `uv run pytest tests/test_solver.py -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add tests/test_solver.py
git commit -m "fix: rewrite solver tests for FDC-based food DB and renamed fields"
```

---

### Task 4: JSON Schema

Create the pinned meal validation schema.

**Files:**
- Create: `src/daily_chow/data/schemas/pinned-meal.schema.json`

**Step 1: Create schema directory and file**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "pinned-meal.schema.json",
  "title": "Pinned Meal",
  "description": "A meal with fixed nutritional values that the solver works around.",
  "oneOf": [
    { "$ref": "#/$defs/meal" },
    { "type": "array", "items": { "$ref": "#/$defs/meal" }, "minItems": 1 }
  ],
  "$defs": {
    "meal": {
      "type": "object",
      "required": ["name", "nutrients"],
      "additionalProperties": false,
      "properties": {
        "name": {
          "type": "string",
          "minLength": 1
        },
        "nutrients": {
          "type": "object",
          "required": [
            "calories_kcal",
            "protein_g",
            "fat_g",
            "carbs_g",
            "fiber_g"
          ],
          "additionalProperties": false,
          "properties": {
            "calories_kcal": { "type": "number", "minimum": 0 },
            "protein_g": { "type": "number", "minimum": 0 },
            "fat_g": { "type": "number", "minimum": 0 },
            "carbs_g": { "type": "number", "minimum": 0 },
            "fiber_g": { "type": "number", "minimum": 0 },
            "calcium_mg": { "type": "number", "minimum": 0 },
            "iron_mg": { "type": "number", "minimum": 0 },
            "magnesium_mg": { "type": "number", "minimum": 0 },
            "phosphorus_mg": { "type": "number", "minimum": 0 },
            "potassium_mg": { "type": "number", "minimum": 0 },
            "zinc_mg": { "type": "number", "minimum": 0 },
            "copper_mg": { "type": "number", "minimum": 0 },
            "manganese_mg": { "type": "number", "minimum": 0 },
            "selenium_mcg": { "type": "number", "minimum": 0 },
            "vitamin_c_mg": { "type": "number", "minimum": 0 },
            "thiamin_mg": { "type": "number", "minimum": 0 },
            "riboflavin_mg": { "type": "number", "minimum": 0 },
            "niacin_mg": { "type": "number", "minimum": 0 },
            "vitamin_b6_mg": { "type": "number", "minimum": 0 },
            "folate_mcg": { "type": "number", "minimum": 0 },
            "vitamin_b12_mcg": { "type": "number", "minimum": 0 },
            "vitamin_a_mcg": { "type": "number", "minimum": 0 },
            "vitamin_d_mcg": { "type": "number", "minimum": 0 },
            "vitamin_e_mg": { "type": "number", "minimum": 0 },
            "vitamin_k_mcg": { "type": "number", "minimum": 0 }
          }
        }
      }
    }
  }
}
```

**Step 2: Commit**

```bash
git add src/daily_chow/data/schemas/pinned-meal.schema.json
git commit -m "feat: add JSON schema for pinned meal import validation"
```

---

### Task 5: Backend — Remove Smoothie, Add Pinned Micros

Remove hardcoded smoothie and accept pinned micro totals from frontend.

**Files:**
- Modify: `src/daily_chow/dri.py` (delete lines 149-187)
- Modify: `src/daily_chow/api.py` (lines 9-16, 47-54, 67-73, 148, 162-179)

**Step 1: Clean up dri.py**

Delete `SMOOTHIE_MICROS` dict (lines 153-174) and `remaining_targets()` function (lines 181-187). Also delete the section comment headers. Keep everything else (Sex, AgeGroup, MicroInfo, MICRO_INFO, DRI_TARGETS).

**Step 2: Update api.py imports**

Remove `SMOOTHIE_MICROS` and `remaining_targets` from the dri import:
```python
from daily_chow.dri import (
    DRI_TARGETS,
    MICRO_INFO,
    AgeGroup,
    Sex,
)
```

**Step 3: Add pinned_micros to SolveRequest**

```python
class SolveRequest(BaseModel):
    ingredients: list[IngredientRequest]
    targets: TargetsRequest = TargetsRequest()
    objective: str = "minimize_oil"
    micro_strategy: str = "blended"
    sex: str = "male"
    age_group: str = "19-30"
    optimize_nutrients: list[str] = []
    pinned_micros: dict[str, float] = {}
```

**Step 4: Rename MicroResult.smoothie to .pinned**

```python
class MicroResult(BaseModel):
    total: float
    pinned: float       # was: smoothie
    dri: float
    remaining: float
    pct: float
    optimized: bool
```

**Step 5: Update post_solve() to use pinned_micros**

Replace the micro target computation (currently lines 148-156) — compute remaining from pinned_micros instead of SMOOTHIE_MICROS:
```python
    # Build micro targets for checked nutrients
    sex = Sex(req.sex)
    age_group = AgeGroup(req.age_group)
    dri = DRI_TARGETS[(sex, age_group)]

    micro_targets: dict[str, float] | None = None
    if req.optimize_nutrients:
        micro_targets = {}
        for k in req.optimize_nutrients:
            dri_val = dri.get(k, 0.0)
            pinned_val = req.pinned_micros.get(k, 0.0)
            remaining = max(0.0, dri_val - pinned_val)
            if remaining > 0 and k in dri:
                micro_targets[k] = remaining
```

Replace the micro results loop (currently lines 162-179):
```python
    # Build micro results for all 20 tracked nutrients
    optimized_set = set(req.optimize_nutrients)
    micros: dict[str, MicroResult] = {}
    for key in MICRO_INFO:
        dri_val = dri.get(key, 0.0)
        pinned_val = req.pinned_micros.get(key, 0.0)
        remaining_val = max(0.0, dri_val - pinned_val)
        meal_total = solution.micro_totals.get(key, 0.0)
        pct = (meal_total + pinned_val) / dri_val * 100 if dri_val > 0 else 0.0
        micros[key] = MicroResult(
            total=round(meal_total, 2),
            pinned=round(pinned_val, 2),
            dri=round(dri_val, 2),
            remaining=round(remaining_val, 2),
            pct=round(pct, 1),
            optimized=key in optimized_set,
        )
```

**Step 6: Verify backend**

Run: `uv run python -c "from daily_chow.api import app; print('OK')"`
Expected: `OK`

**Step 7: Commit**

```bash
git add src/daily_chow/dri.py src/daily_chow/api.py
git commit -m "feat: replace hardcoded smoothie with pinned_micros in solve request"
```

---

### Task 6: Frontend — PinnedMeal Type, State, and Solve Integration

Add the PinnedMeal data model, replace smoothie state, wire up to solver.

**Files:**
- Modify: `frontend/src/lib/api.ts` (MicroResult interface, solve function signature)
- Modify: `frontend/src/lib/contributions.ts` (smoothie → pinned references)
- Modify: `frontend/src/routes/+page.svelte` (state, derived, solve call, persistence)

**Step 1: Update api.ts**

Rename `MicroResult.smoothie` to `pinned`:
```typescript
export interface MicroResult {
	total: number;
	pinned: number;    // was: smoothie
	dri: number;
	remaining: number;
	pct: number;
	optimized: boolean;
}
```

Add `PinnedMeal` interface:
```typescript
export interface PinnedMeal {
	id: string;
	name: string;
	nutrients: Record<string, number>;
}
```

Add `pinned_micros` to the solve function:
```typescript
export async function solve(
	ingredients: SolveIngredient[],
	targets: SolveTargets,
	objective: string,
	sex: string,
	age_group: string,
	optimize_nutrients: string[],
	micro_strategy: string,
	pinned_micros: Record<string, number> = {}
): Promise<SolveResponse> {
	const res = await fetch('/api/solve', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ ingredients, targets, objective, sex, age_group, optimize_nutrients, micro_strategy, pinned_micros })
	});
	return res.json();
}
```

**Step 2: Update contributions.ts**

Replace all `mr.smoothie` with `mr.pinned` (lines 113 and 135):
```typescript
// Line 113
		const gap = mr.dri - (mr.total + mr.pinned);
// Line 135
		const gap = mr.dri - (mr.total + mr.pinned);
```

**Step 3: Update +page.svelte state**

Replace smoothie state (lines 57-59) with:
```typescript
	let pinnedMeals = $state<PinnedMeal[]>([]);
```

Add import for `PinnedMeal`:
```typescript
	import { fetchFoods, solve, type Food, type SolveResponse, type SolvedIngredient, type MicroResult, type PinnedMeal } from '$lib/api';
```

Add derived totals (after the imports, near line 120):
```typescript
	// Macro keys used to identify pinned macro nutrients
	const MACRO_KEYS = new Set(['calories_kcal', 'protein_g', 'fat_g', 'carbs_g', 'fiber_g']);

	let pinnedTotals = $derived.by(() => {
		const totals: Record<string, number> = {};
		for (const meal of pinnedMeals) {
			for (const [key, val] of Object.entries(meal.nutrients)) {
				totals[key] = (totals[key] ?? 0) + val;
			}
		}
		return totals;
	});

	let pinnedMicros = $derived.by(() => {
		const micros: Record<string, number> = {};
		for (const [key, val] of Object.entries(pinnedTotals)) {
			if (!MACRO_KEYS.has(key)) {
				micros[key] = val;
			}
		}
		return micros;
	});

	let mealCal = $derived(dailyCal - (pinnedTotals.calories_kcal ?? 0));
	let mealPro = $derived(dailyPro - (pinnedTotals.protein_g ?? 0));
	let mealFiberMin = $derived(dailyFiberMin - (pinnedTotals.fiber_g ?? 0));
```

Remove the old `smoothieCal`, `smoothiePro`, `smoothieFiber` state variables and old `mealCal`/`mealPro`/`mealFiberMin` derived values.

**Step 4: Update doSolve() call**

Pass `pinnedMicros` to solve (around line 218):
```typescript
			solution = await solve(
				enabled.map((i) => ({ key: i.key, min_g: i.minG, max_g: i.maxG })),
				{
					meal_calories_kcal: mealCal,
					meal_protein_g: mealPro,
					meal_fiber_min_g: mealFiberMin,
					cal_tolerance: calTol,
					protein_tolerance: proTol
				},
				objective,
				sex,
				ageGroup,
				Array.from(optimizeNutrients),
				microStrategy,
				pinnedMicros
			);
```

**Step 5: Update persistence**

In `saveState()`, replace `smoothieCal, smoothiePro, smoothieFiber` with `pinnedMeals`:
```typescript
		const state = {
			dailyCal, dailyPro, dailyFiberMin,
			pinnedMeals,
			calTol, proTol, objective, microStrategy, theme, ingredients,
			sex, ageGroup,
			optimizeNutrients: Array.from(optimizeNutrients),
			microsOpen, sliderAbsMax
		};
```

In `loadState()`, replace smoothie loading with:
```typescript
			if (s.pinnedMeals) pinnedMeals = s.pinnedMeals;
```

Remove old `smoothieCal/Pro/Fiber` loading lines. Ignore old smoothie keys gracefully (they just won't be read).

**Step 6: Update "Day" totals display**

Lines 553-555, replace `smoothieCal/Pro/Fiber` with `pinnedTotals`:
```svelte
				<div class="total-item">
					<span class="total-label">Day</span>
					<span class="total-cal">{Math.round(solution.meal_calories_kcal + (pinnedTotals.calories_kcal ?? 0))} kcal</span>
					<span class="total-pro">{Math.round(solution.meal_protein_g + (pinnedTotals.protein_g ?? 0))}g pro</span>
					<span class="total-fib">{Math.round(solution.meal_fiber_g + (pinnedTotals.fiber_g ?? 0))}g fiber</span>
				</div>
```

**Step 7: Update microStackedSegments**

Replace `mr.smoothie` with `mr.pinned` and label "Smoothie" → "Pinned" (lines 374-378):
```typescript
		if (mr.pinned > 0) {
			const pinnedPct = (mr.pinned / mr.dri) * 100;
			if (pinnedPct > 0.5) {
				segments.push({ key: '_pinned', label: 'Pinned', value: `${fmtMicro(mr.pinned, info?.unit ?? '')} ${info?.unit ?? ''}`, pct: pinnedPct, color: '#94a3b8' });
			}
		}
```

**Step 8: Remove smoothie row from template**

Delete the smoothie row (lines 498-503):
```svelte
		<div class="smoothie-row">
			Smoothie:
			<input type="number" bind:value={smoothieCal} onchange={triggerSolve} class="sm-input" /> kcal ·
			<input type="number" bind:value={smoothiePro} onchange={triggerSolve} class="sm-input" />g pro ·
			<input type="number" bind:value={smoothieFiber} onchange={triggerSolve} class="sm-input" />g fiber
		</div>
```

Also delete the `.smoothie-row` and `.sm-input` CSS rules.

**Step 9: Verify frontend compiles**

Run: `cd frontend && bun run check`
Expected: No errors (may have warnings)

**Step 10: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/contributions.ts frontend/src/routes/+page.svelte
git commit -m "feat: replace smoothie state with pinnedMeals data model and aggregation"
```

---

### Task 7: PinnedMealModal Component

New modal for adding/editing pinned meals with JSON import.

**Files:**
- Create: `frontend/src/lib/components/PinnedMealModal.svelte`

**Step 1: Create the component**

The modal should:
- Accept optional `meal: PinnedMeal` prop (edit mode) or null (add mode)
- Have a name text input
- 5 required macro number inputs in a compact row
- Collapsible micros section grouped by category (reuse MICRO_TIERS/MICRO_NAMES pattern from +page.svelte)
- "Import JSON" button with file picker
- Validate JSON against schema (check required fields, numeric values >= 0)
- Save/Cancel buttons
- Emit `onsave(meal: PinnedMeal)` and `onclose()`

Use the same modal overlay pattern as `AddIngredientModal.svelte` for visual consistency.

The micro groups should match the existing `MICRO_TIERS` structure:
- Major Minerals: calcium_mg through selenium_mcg
- B-Vitamins + C: vitamin_c_mg through vitamin_b12_mcg
- Fat-Soluble Vitamins: vitamin_a_mcg through vitamin_k_mcg

For JSON import: read file, parse, validate required macro keys exist and all values are numbers >= 0. If valid, fill form fields. If array, import first item and warn. Show error message for invalid JSON.

**Step 2: Verify it compiles**

Run: `cd frontend && bun run check`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/lib/components/PinnedMealModal.svelte
git commit -m "feat: add PinnedMealModal component with JSON import"
```

---

### Task 8: Pinned Meals Section on Main Page

Add collapsible section between config panel and ingredients table.

**Files:**
- Modify: `frontend/src/routes/+page.svelte`

**Step 1: Add pinned meals UI state**

```typescript
	let pinnedMealsOpen = $state(true);
	let showPinnedModal = $state(false);
	let editingPinnedMeal = $state<PinnedMeal | null>(null);
```

Import the modal:
```typescript
	import PinnedMealModal from '$lib/components/PinnedMealModal.svelte';
```

**Step 2: Add pinned meal CRUD functions**

```typescript
	function addPinnedMeal(meal: PinnedMeal) {
		pinnedMeals = [...pinnedMeals, meal];
		showPinnedModal = false;
		editingPinnedMeal = null;
		triggerSolve();
	}

	function updatePinnedMeal(updated: PinnedMeal) {
		pinnedMeals = pinnedMeals.map((m) => m.id === updated.id ? updated : m);
		showPinnedModal = false;
		editingPinnedMeal = null;
		triggerSolve();
	}

	function removePinnedMeal(id: string) {
		pinnedMeals = pinnedMeals.filter((m) => m.id !== id);
		triggerSolve();
	}

	function exportPinnedMeal(meal: PinnedMeal) {
		const data = { name: meal.name, nutrients: meal.nutrients };
		const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `${meal.name.toLowerCase().replace(/\s+/g, '-')}.json`;
		a.click();
		URL.revokeObjectURL(url);
	}
```

**Step 3: Add template section**

Insert between the config `</section>` and the ingredients `<section>` (around line 504):

```svelte
	<section class="pinned-section">
		<div class="pinned-header">
			<button class="pinned-toggle" onclick={() => { pinnedMealsOpen = !pinnedMealsOpen; }}>
				<span class="pinned-arrow" class:open={pinnedMealsOpen}>▸</span>
				Pinned Meals
				{#if pinnedMeals.length > 0}
					<span class="pinned-badge">{pinnedMeals.length}</span>
				{/if}
			</button>
			<button class="add-pinned-btn" onclick={() => { editingPinnedMeal = null; showPinnedModal = true; }}>+ Add</button>
		</div>
		{#if pinnedMealsOpen}
			{#if pinnedMeals.length === 0}
				<div class="pinned-empty">No pinned meals. Add one to subtract from daily targets.</div>
			{:else}
				{#each pinnedMeals as meal (meal.id)}
					<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
					<div class="pinned-row" onclick={() => { editingPinnedMeal = meal; showPinnedModal = true; }}>
						<span class="pinned-name">{meal.name}</span>
						<span class="pinned-macros">
							{meal.nutrients.calories_kcal ?? 0} kcal ·
							{meal.nutrients.protein_g ?? 0}g pro ·
							{meal.nutrients.fat_g ?? 0}g fat ·
							{meal.nutrients.carbs_g ?? 0}g carb ·
							{meal.nutrients.fiber_g ?? 0}g fib
						</span>
						<button class="pinned-export" onclick|stopPropagation={() => exportPinnedMeal(meal)} title="Export JSON">↓</button>
						<button class="pinned-remove" onclick|stopPropagation={() => removePinnedMeal(meal.id)} title="Remove">×</button>
					</div>
				{/each}
			{/if}
		{/if}
	</section>
```

Note: Svelte 5 uses `onclick` not `on:click`. For stopPropagation, use inline: `onclick={(e) => { e.stopPropagation(); exportPinnedMeal(meal); }}`

**Step 4: Add modal at end of template**

Near the existing `AddIngredientModal` usage:
```svelte
	{#if showPinnedModal}
		<PinnedMealModal
			meal={editingPinnedMeal}
			onsave={(meal) => {
				if (editingPinnedMeal) updatePinnedMeal(meal);
				else addPinnedMeal(meal);
			}}
			onclose={() => { showPinnedModal = false; editingPinnedMeal = null; }}
		/>
	{/if}
```

**Step 5: Add CSS**

Style the pinned section to match the existing app aesthetic (collapsible header with arrow, rows with hover, badge count).

**Step 6: Update persistence**

Add `pinnedMealsOpen` to `saveState()`/`loadState()`.

**Step 7: Verify frontend compiles**

Run: `cd frontend && bun run check`

**Step 8: Test in browser**

- Add a pinned meal, verify it appears in the list
- Edit it, verify changes persist
- Delete it, verify it's removed
- Export to JSON, verify file downloads
- Import JSON via modal, verify form fills
- Verify solver re-runs after add/edit/delete

**Step 9: Commit**

```bash
git add frontend/src/routes/+page.svelte
git commit -m "feat: add pinned meals section with add/edit/delete/export"
```

---

### Task 9: Update Macro Displays with Pinned Segments

Add pinned meal contributions to macro percentage bar and breakdown.

**Files:**
- Modify: `frontend/src/routes/+page.svelte`

**Step 1: Update macroPcts to include pinned macros**

Replace the macroPcts derivation to include pinned meals in the day-level percentage:
```typescript
	let macroPcts = $derived.by(() => {
		if (!solution || solution.status === 'infeasible') return null;
		const carbCal = (solution.meal_carbs_g + (pinnedTotals.carbs_g ?? 0)) * 4;
		const proCal = (solution.meal_protein_g + (pinnedTotals.protein_g ?? 0)) * 4;
		const fatCal = (solution.meal_fat_g + (pinnedTotals.fat_g ?? 0)) * 9;
		const total = carbCal + proCal + fatCal;
		if (total <= 0) return null;
		const carb = Math.round((carbCal / total) * 100);
		const pro = Math.round((proCal / total) * 100);
		const fat = 100 - carb - pro;
		return { carb, pro, fat };
	});
```

**Step 2: Add pinned segment to macroStackedSegments**

After the ingredient filter, add pinned meal contribution:
```typescript
	function macroStackedSegments(macro: 'cal' | 'pro' | 'fat' | 'carb' | 'fiber') {
		if (!solution || solution.status === 'infeasible') return [];
		const segments = solution.ingredients
			.map((ing) => {
				const contrib = contributions.get(ing.key);
				const color = ingredientColorMap.get(ing.key) ?? '#666';
				const food = foods[ing.key];
				const name = food?.name ?? String(ing.key);
				const pct = contrib?.macroPcts[macro] ?? 0;
				let val = 0;
				if (macro === 'cal') val = ing.calories_kcal;
				else if (macro === 'pro') val = ing.protein_g;
				else if (macro === 'fat') val = ing.fat_g;
				else if (macro === 'carb') val = ing.carbs_g;
				else val = ing.fiber_g;
				return { key: String(ing.key), label: name, value: `${Math.round(val)}${macro === 'cal' ? ' kcal' : 'g'}`, pct, color };
			})
			.filter((s) => s.pct > 0.5);

		// Add pinned meals contribution
		const pinnedKeyMap: Record<string, string> = {
			cal: 'calories_kcal', pro: 'protein_g', fat: 'fat_g', carb: 'carbs_g', fiber: 'fiber_g'
		};
		const mealTotalMap: Record<string, number> = {
			cal: solution.meal_calories_kcal,
			pro: solution.meal_protein_g,
			fat: solution.meal_fat_g,
			carb: solution.meal_carbs_g,
			fiber: solution.meal_fiber_g,
		};
		const pinnedVal = pinnedTotals[pinnedKeyMap[macro]] ?? 0;
		const dayTotal = mealTotalMap[macro] + pinnedVal;
		if (pinnedVal > 0 && dayTotal > 0) {
			const pinnedPct = (pinnedVal / dayTotal) * 100;
			if (pinnedPct > 0.5) {
				segments.push({
					key: '_pinned',
					label: 'Pinned',
					value: `${Math.round(pinnedVal)}${macro === 'cal' ? ' kcal' : 'g'}`,
					pct: pinnedPct,
					color: '#94a3b8'
				});
			}
		}

		return segments;
	}
```

Note: The ingredient `pct` values from `contributions.ts` are relative to meal total, but now we need them relative to day total (meal + pinned). Update `computeContributions` in contributions.ts to accept optional pinned totals, OR recalculate pct inline. The simpler approach: recalculate pct in `macroStackedSegments` using day total instead of relying on `contrib.macroPcts`. This avoids changing the contributions module.

Actually, the cleaner fix: change the pct calculation to be relative to day total:
```typescript
	function macroStackedSegments(macro: 'cal' | 'pro' | 'fat' | 'carb' | 'fiber') {
		if (!solution || solution.status === 'infeasible') return [];

		const pinnedKeyMap: Record<string, string> = {
			cal: 'calories_kcal', pro: 'protein_g', fat: 'fat_g', carb: 'carbs_g', fiber: 'fiber_g'
		};
		const mealTotalMap: Record<string, number> = {
			cal: solution.meal_calories_kcal,
			pro: solution.meal_protein_g,
			fat: solution.meal_fat_g,
			carb: solution.meal_carbs_g,
			fiber: solution.meal_fiber_g,
		};
		const pinnedVal = pinnedTotals[pinnedKeyMap[macro]] ?? 0;
		const dayTotal = mealTotalMap[macro] + pinnedVal;
		if (dayTotal <= 0) return [];

		const segments = solution.ingredients
			.map((ing) => {
				const color = ingredientColorMap.get(ing.key) ?? '#666';
				const food = foods[ing.key];
				const name = food?.name ?? String(ing.key);
				let val = 0;
				if (macro === 'cal') val = ing.calories_kcal;
				else if (macro === 'pro') val = ing.protein_g;
				else if (macro === 'fat') val = ing.fat_g;
				else if (macro === 'carb') val = ing.carbs_g;
				else val = ing.fiber_g;
				const pct = (val / dayTotal) * 100;
				return { key: String(ing.key), label: name, value: `${Math.round(val)}${macro === 'cal' ? ' kcal' : 'g'}`, pct, color };
			})
			.filter((s) => s.pct > 0.5);

		if (pinnedVal > 0) {
			const pinnedPct = (pinnedVal / dayTotal) * 100;
			if (pinnedPct > 0.5) {
				segments.push({
					key: '_pinned',
					label: 'Pinned',
					value: `${Math.round(pinnedVal)}${macro === 'cal' ? ' kcal' : 'g'}`,
					pct: pinnedPct,
					color: '#94a3b8'
				});
			}
		}

		return segments;
	}
```

**Step 3: Verify and test in browser**

- Add a pinned meal with macros
- Expand macro breakdown — should show "Pinned" gray segment
- Remove all pinned meals — segments should only show ingredients (no empty pinned segment)

**Step 4: Commit**

```bash
git add frontend/src/routes/+page.svelte
git commit -m "feat: show pinned meal segments in macro percentage bar and breakdown"
```

---

### Task 10: Smoothie Export and Final Verification

Export current smoothie data and verify the zero-pinned-meals state.

**Files:**
- Create: `docs/smoothie-default.json`

**Step 1: Create smoothie export file**

Using values from the deleted `SMOOTHIE_MICROS` in dri.py plus known macro values:

```json
{
  "name": "Morning Smoothie",
  "nutrients": {
    "calories_kcal": 720,
    "protein_g": 30,
    "fiber_g": 14,
    "calcium_mg": 659,
    "iron_mg": 3.1,
    "magnesium_mg": 151.6,
    "phosphorus_mg": 696.4,
    "potassium_mg": 1160.7,
    "zinc_mg": 3.4,
    "copper_mg": 0.6,
    "manganese_mg": 1.9,
    "selenium_mcg": 40.9,
    "vitamin_c_mg": 149.6,
    "thiamin_mg": 0.4,
    "riboflavin_mg": 1.0,
    "niacin_mg": 3.3,
    "vitamin_b6_mg": 0.4,
    "folate_mcg": 97.7,
    "vitamin_b12_mcg": 1.9,
    "vitamin_a_mcg": 292,
    "vitamin_d_mcg": 3.2,
    "vitamin_e_mg": 2.4,
    "vitamin_k_mcg": 46.3
  }
}
```

Note: `fat_g` and `carbs_g` are omitted because they were unknown for the original smoothie. This file is intentionally NOT valid against the schema (missing required macros) — the user will need to fill in fat and carbs before importing. Add a comment in the design doc about this, or add placeholder zeros:

```json
    "fat_g": 0,
    "carbs_g": 0,
```

Use zeros so the file validates against the schema. User can update later.

**Step 2: Verify zero-pinned-meals state**

Clear localStorage (`localStorage.removeItem('daily-chow')`) and reload. Verify:
- No pinned meals section shows "No pinned meals" message
- Solver targets are full daily values (3500 kcal, 160g pro, 40g fiber)
- "Day" row matches "Meal" row
- Macro % bar shows only meal ingredients
- Micro breakdown shows no pinned segments
- Everything works normally

**Step 3: Verify with pinned meal**

Import the smoothie JSON file. Verify:
- Solver targets adjust (3500 - 720 = 2780 kcal, etc.)
- "Day" row adds pinned totals
- Micro breakdown shows "Pinned" gray segments
- Macro breakdown shows "Pinned" gray segments

**Step 4: Run all checks**

```bash
uv run pytest tests/test_solver.py -v
cd frontend && bun run check
```

**Step 5: Commit**

```bash
git add docs/smoothie-default.json
git commit -m "feat: export smoothie defaults as importable pinned meal JSON"
```
