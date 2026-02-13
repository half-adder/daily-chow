# Macro Ratio Target Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a user-settable carb/protein/fat calorie ratio as a soft optimization objective, with a draggable stacked-bar UI component.

**Architecture:** Backend solver gets a new `macro_ratio` soft objective (minimax deviation) and protein changes from band constraint to floor. Frontend gets a new `MacroRatioBar.svelte` component with draggable dividers and inline text editing. The ratio target flows through the existing `/api/solve` endpoint.

**Tech Stack:** Python (ortools CP-SAT), SvelteKit (Svelte 5 runes), FastAPI, Pydantic

---

### Task 1: Solver — protein floor + macro ratio objective

**Files:**
- Modify: `src/daily_chow/solver.py`
- Test: `tests/test_solver.py`

**Step 1: Write failing tests for protein floor**

Add to `tests/test_solver.py`:

```python
from daily_chow.solver import (
    IngredientInput,
    PRIORITY_MICROS,
    PRIORITY_MACRO_RATIO,
    PRIORITY_TOTAL_WEIGHT,
    MacroRatio,
    Solution,
    Targets,
    solve,
)


class TestProteinFloor:
    def test_protein_floor_met(self):
        """Protein should meet or exceed the minimum."""
        targets = Targets(meal_protein_min_g=130)
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_protein_g >= 130 - 1  # 1g rounding tolerance

    def test_protein_can_exceed_floor(self):
        """Protein is allowed to go over the floor (no upper band)."""
        targets = Targets(meal_protein_min_g=80)
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_protein_g >= 80 - 1
```

**Step 2: Write failing tests for macro ratio objective**

Add to `tests/test_solver.py`:

```python
class TestMacroRatioObjective:
    def test_macro_ratio_feasible(self):
        """Solver should find a solution with macro ratio target."""
        ratio = MacroRatio(carb_pct=50, protein_pct=25, fat_pct=25)
        sol = solve(
            _default_ingredients(),
            macro_ratio=ratio,
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol.status in ("optimal", "feasible")

    def test_macro_ratio_steers_solution(self):
        """A high-fat ratio target should produce more fat than a low-fat one."""
        high_fat = MacroRatio(carb_pct=30, protein_pct=20, fat_pct=50)
        low_fat = MacroRatio(carb_pct=60, protein_pct=25, fat_pct=15)
        sol_hf = solve(
            _default_ingredients(),
            macro_ratio=high_fat,
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        sol_lf = solve(
            _default_ingredients(),
            macro_ratio=low_fat,
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol_hf.status in ("optimal", "feasible")
        assert sol_lf.status in ("optimal", "feasible")
        assert sol_hf.meal_fat_g > sol_lf.meal_fat_g

    def test_macro_ratio_priority_ordering(self):
        """macro_ratio should participate in lexicographic ordering."""
        ratio = MacroRatio(carb_pct=50, protein_pct=25, fat_pct=25)
        sol = solve(
            _default_ingredients(),
            macro_ratio=ratio,
            priorities=[PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
            micro_targets={"iron_mg": 4.9},
        )
        assert sol.status in ("optimal", "feasible")
```

**Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_solver.py -v`
Expected: ImportError for `PRIORITY_MACRO_RATIO` and `MacroRatio`

**Step 4: Implement solver changes**

In `src/daily_chow/solver.py`:

1. Add `MacroRatio` dataclass and `PRIORITY_MACRO_RATIO` constant:

```python
PRIORITY_MACRO_RATIO = "macro_ratio"
DEFAULT_PRIORITIES = [PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT]


@dataclass(frozen=True, slots=True)
class MacroRatio:
    carb_pct: int = 50   # % of calories from carbs
    protein_pct: int = 25 # % of calories from protein
    fat_pct: int = 25     # % of calories from fat
```

2. Change `Targets` — replace `meal_protein_g` + `protein_tolerance` with `meal_protein_min_g`:

```python
@dataclass(frozen=True, slots=True)
class Targets:
    meal_calories_kcal: int = 2780
    meal_protein_min_g: int = 130  # floor, was band
    meal_fiber_min_g: int = 26
    cal_tolerance: int = 50
```

3. Update `solve()` signature — add `macro_ratio` parameter:

```python
def solve(
    ingredients: list[IngredientInput],
    targets: Targets = Targets(),
    micro_targets: dict[str, float] | None = None,
    micro_uls: dict[str, float] | None = None,
    macro_ratio: MacroRatio | None = None,
    priorities: list[str] | None = None,
    solver_timeout_s: float = 5.0,
) -> Solution:
```

4. Replace protein band constraint with floor:

```python
# ── Protein constraint: total >= minimum ────────────────────────
pro_min_scaled = targets.meal_protein_min_g * SCALE
model.add(total_pro >= pro_min_scaled)
```

5. Add fat/carb coefficient computation (needed for ratio objective):

```python
fat_coeffs = {ing.key: _scaled_coeff(ing.food.fat_g_per_100g) for ing in ingredients}
carb_coeffs = {ing.key: _scaled_coeff(ing.food.carbs_g_per_100g) for ing in ingredients}
total_fat = sum(fat_coeffs[ing.key] * gram_vars[ing.key] for ing in ingredients)
total_carb = sum(carb_coeffs[ing.key] * gram_vars[ing.key] for ing in ingredients)
```

6. Add macro ratio minimax objective. The approach: compute calorie-weighted deviation for each macro and minimize the worst case.

```python
# ── Macro ratio minimax objective ─────────────────────────────
# Deviation of actual macro % from target %, minimized via minimax.
# actual_carb_cal = total_carb * 4 (in scaled units: total_carb * 4)
# actual_pct = actual_carb_cal / total_cal * 100
# We want to minimize |actual_pct - target_pct| for each macro.
#
# Cross-multiply to avoid division:
#   deviation = |actual_carb_cal * 100 - target_pct * total_cal|
# Since total_cal is constrained near a known target, we can bound the deviation.
# Use PCT_SCALE for precision.
macro_worst_var: cp_model.IntVar | None = None
max_macro_worst = 0

if macro_ratio is not None:
    # Calorie expressions (in SCALE units, *4 or *9 for macro->cal)
    carb_cal_expr = total_carb * 4   # scaled carb calories
    pro_cal_expr = total_pro * 4     # scaled protein calories
    fat_cal_expr = total_fat * 9     # scaled fat calories
    total_cal_expr = carb_cal_expr + pro_cal_expr + fat_cal_expr

    # Max possible total calories (scaled)
    max_cal = sum(
        (ing.max_g * _scaled_coeff(ing.food.carbs_g_per_100g) * 4
         + ing.max_g * _scaled_coeff(ing.food.protein_g_per_100g) * 4
         + ing.max_g * _scaled_coeff(ing.food.fat_g_per_100g) * 9)
        for ing in ingredients
    )

    macro_dev_vars: list[cp_model.IntVar] = []
    for name, cal_expr, target_pct in [
        ("carb", carb_cal_expr, macro_ratio.carb_pct),
        ("pro", pro_cal_expr, macro_ratio.protein_pct),
        ("fat", fat_cal_expr, macro_ratio.fat_pct),
    ]:
        # |cal_expr * 100 - target_pct * total_cal_expr| <= dev * total_cal_expr
        # Cross-multiplied: diff = cal_expr * 100 - target_pct * total_cal_expr
        diff_expr = cal_expr * 100 - total_cal_expr * target_pct
        # Bound: max abs value is max_cal * 100
        bound = max_cal * 100
        diff_var = model.new_int_var(-bound, bound, f"macro_{name}_diff")
        model.add(diff_var == diff_expr)

        abs_diff = model.new_int_var(0, bound, f"macro_{name}_abs")
        model.add_abs_equality(abs_diff, diff_var)

        # Normalize: pct_dev * total_cal_expr >= abs_diff * PCT_SCALE
        # This gives pct_dev in [0, PCT_SCALE] representing 0-100% deviation
        pct_dev = model.new_int_var(0, PCT_SCALE, f"macro_{name}_pctdev")
        model.add(pct_dev * total_cal_expr >= abs_diff * PCT_SCALE)
        macro_dev_vars.append(pct_dev)

    if macro_dev_vars:
        macro_worst_var = model.new_int_var(0, PCT_SCALE, "macro_worst")
        for dv in macro_dev_vars:
            model.add(macro_worst_var >= dv)
        max_macro_worst = PCT_SCALE
```

7. Add the macro ratio term to the objective builder:

```python
elif p == PRIORITY_MACRO_RATIO:
    if macro_worst_var is not None and max_macro_worst > 0:
        terms.append((macro_worst_var, max_macro_worst))
```

**Step 5: Update existing tests for new Targets shape**

The old tests reference `Targets()` which used `meal_protein_g` and `protein_tolerance`. Update:
- `TestSolverConstraints.test_protein_within_tolerance` → rename to `test_protein_meets_floor` and assert `>= meal_protein_min_g - 1`
- All `Targets()` calls still work since we're using defaults, just need to update the assertion.

**Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_solver.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add src/daily_chow/solver.py tests/test_solver.py
git commit -m "feat: add macro ratio soft objective and protein floor constraint"
```

---

### Task 2: API — accept macro ratio and protein floor

**Files:**
- Modify: `src/daily_chow/api.py`

**Step 1: Update request/response models**

In `src/daily_chow/api.py`:

1. Add `MacroRatioRequest` model:

```python
class MacroRatioRequest(BaseModel):
    carb_pct: int = 50
    protein_pct: int = 25
    fat_pct: int = 25
```

2. Update `TargetsRequest` — replace `meal_protein_g`/`protein_tolerance` with `meal_protein_min_g`:

```python
class TargetsRequest(BaseModel):
    meal_calories_kcal: int = 2780
    meal_protein_min_g: int = 130
    meal_fiber_min_g: int = 26
    cal_tolerance: int = 50
```

3. Add `macro_ratio` to `SolveRequest`:

```python
class SolveRequest(BaseModel):
    ingredients: list[IngredientRequest]
    targets: TargetsRequest = TargetsRequest()
    priorities: list[str] = list(DEFAULT_PRIORITIES)
    sex: str = "male"
    age_group: str = "19-30"
    optimize_nutrients: list[str] = []
    pinned_micros: dict[str, float] = {}
    macro_ratio: MacroRatioRequest | None = None
```

4. Update `post_solve` to pass new fields:

```python
targets = Targets(
    meal_calories_kcal=req.targets.meal_calories_kcal,
    meal_protein_min_g=req.targets.meal_protein_min_g,
    meal_fiber_min_g=req.targets.meal_fiber_min_g,
    cal_tolerance=req.targets.cal_tolerance,
)

macro_ratio_obj = None
if req.macro_ratio is not None:
    macro_ratio_obj = MacroRatio(
        carb_pct=req.macro_ratio.carb_pct,
        protein_pct=req.macro_ratio.protein_pct,
        fat_pct=req.macro_ratio.fat_pct,
    )

solution = solve(
    ingredient_inputs, targets,
    micro_targets=micro_targets, micro_uls=micro_uls,
    macro_ratio=macro_ratio_obj,
    priorities=req.priorities,
)
```

Update imports to include `MacroRatio`.

**Step 2: Run solver tests to verify nothing broke**

Run: `uv run pytest tests/test_solver.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add src/daily_chow/api.py
git commit -m "feat: API accepts macro_ratio and protein floor"
```

---

### Task 3: Frontend API types — update solve request

**Files:**
- Modify: `frontend/src/lib/api.ts`

**Step 1: Update types and solve function**

```typescript
export interface SolveTargets {
	meal_calories_kcal: number;
	meal_protein_min_g: number;
	meal_fiber_min_g: number;
	cal_tolerance: number;
}

export interface MacroRatio {
	carb_pct: number;
	protein_pct: number;
	fat_pct: number;
}

export async function solve(
	ingredients: SolveIngredient[],
	targets: SolveTargets,
	sex: string,
	age_group: string,
	optimize_nutrients: string[],
	priorities: string[],
	pinned_micros: Record<string, number> = {},
	macro_ratio: MacroRatio | null = null
): Promise<SolveResponse> {
	const res = await fetch('/api/solve', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ ingredients, targets, sex, age_group, optimize_nutrients, priorities, pinned_micros, macro_ratio })
	});
	return res.json();
}
```

**Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: frontend API types for macro ratio and protein floor"
```

---

### Task 4: MacroRatioBar.svelte component

**Files:**
- Create: `frontend/src/lib/components/MacroRatioBar.svelte`

**Step 1: Build the component**

The component needs:
- Three colored segments (carb=#f59e0b, protein=#3b82f6, fat=#a855f7 — matching existing macro bar)
- Each segment shows editable text: `Carb: 50%`
- Two draggable grip dividers between segments
- `onchange` callback fires with new percentages
- All values integers, clamped >= 5%, sum to 100%

```svelte
<script lang="ts">
	interface Props {
		carbPct: number;
		proteinPct: number;
		fatPct: number;
		onchange: (carb: number, protein: number, fat: number) => void;
	}

	let { carbPct, proteinPct, fatPct, onchange }: Props = $props();

	let barEl = $state<HTMLDivElement | null>(null);
	let dragging = $state<'cp' | 'pf' | null>(null);
	let editingSegment = $state<'carb' | 'protein' | 'fat' | null>(null);
	let editValue = $state('');

	const MIN_PCT = 5;

	function clamp(v: number, min: number, max: number) {
		return Math.max(min, Math.min(max, v));
	}

	function startDrag(handle: 'cp' | 'pf', e: PointerEvent) {
		dragging = handle;
		(e.target as HTMLElement).setPointerCapture(e.pointerId);
		e.preventDefault();
	}

	function onPointerMove(e: PointerEvent) {
		if (!dragging || !barEl) return;
		const rect = barEl.getBoundingClientRect();
		const pct = clamp(((e.clientX - rect.left) / rect.width) * 100, 0, 100);

		if (dragging === 'cp') {
			// carb/protein divider: carb = pct, protein = (100 - fat) - carb
			const newCarb = clamp(Math.round(pct), MIN_PCT, 100 - fatPct - MIN_PCT);
			const newProtein = 100 - newCarb - fatPct;
			if (newProtein >= MIN_PCT) {
				onchange(newCarb, newProtein, fatPct);
			}
		} else {
			// protein/fat divider: fat = 100 - pct, protein = pct - carb
			const newFat = clamp(Math.round(100 - pct), MIN_PCT, 100 - carbPct - MIN_PCT);
			const newProtein = 100 - carbPct - newFat;
			if (newProtein >= MIN_PCT) {
				onchange(carbPct, newProtein, newFat);
			}
		}
	}

	function onPointerUp() {
		dragging = null;
	}

	function startEdit(segment: 'carb' | 'protein' | 'fat') {
		editingSegment = segment;
		if (segment === 'carb') editValue = String(carbPct);
		else if (segment === 'protein') editValue = String(proteinPct);
		else editValue = String(fatPct);
	}

	function commitEdit() {
		if (!editingSegment) return;
		const val = parseInt(editValue);
		if (isNaN(val) || val < MIN_PCT) { editingSegment = null; return; }

		if (editingSegment === 'carb') {
			const newCarb = clamp(val, MIN_PCT, 100 - MIN_PCT * 2);
			// Adjust protein (right neighbor), fat stays
			const newProtein = clamp(100 - newCarb - fatPct, MIN_PCT, 100 - newCarb - MIN_PCT);
			const newFat = 100 - newCarb - newProtein;
			onchange(newCarb, newProtein, newFat);
		} else if (editingSegment === 'protein') {
			const newProtein = clamp(val, MIN_PCT, 100 - MIN_PCT * 2);
			// Adjust fat (right neighbor), carb stays
			const newFat = clamp(100 - carbPct - newProtein, MIN_PCT, 100 - carbPct - MIN_PCT);
			const newCarb = 100 - newProtein - newFat;
			onchange(newCarb, newProtein, newFat);
		} else {
			const newFat = clamp(val, MIN_PCT, 100 - MIN_PCT * 2);
			// Adjust protein (left neighbor), carb stays
			const newProtein = clamp(100 - carbPct - newFat, MIN_PCT, 100 - carbPct - MIN_PCT);
			const newCarb = 100 - newProtein - newFat;
			onchange(newCarb, newProtein, newFat);
		}
		editingSegment = null;
	}

	function onEditKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') commitEdit();
		if (e.key === 'Escape') editingSegment = null;
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="ratio-bar"
	bind:this={barEl}
	onpointermove={onPointerMove}
	onpointerup={onPointerUp}
>
	<!-- Carb segment -->
	<div class="ratio-segment carb" style="width: {carbPct}%">
		{#if editingSegment === 'carb'}
			<!-- svelte-ignore a11y_autofocus -->
			<input
				class="ratio-edit"
				type="number"
				bind:value={editValue}
				onblur={commitEdit}
				onkeydown={onEditKeydown}
				autofocus
			/>
		{:else if carbPct >= 15}
			<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
			<span class="ratio-label" onclick={() => startEdit('carb')}>Carb: {carbPct}%</span>
		{/if}
	</div>

	<!-- Carb/Protein divider -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="ratio-grip" onpointerdown={(e) => startDrag('cp', e)}>
		<div class="grip-lines"><div></div><div></div></div>
	</div>

	<!-- Protein segment -->
	<div class="ratio-segment protein" style="width: {proteinPct}%">
		{#if editingSegment === 'protein'}
			<!-- svelte-ignore a11y_autofocus -->
			<input
				class="ratio-edit"
				type="number"
				bind:value={editValue}
				onblur={commitEdit}
				onkeydown={onEditKeydown}
				autofocus
			/>
		{:else if proteinPct >= 15}
			<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
			<span class="ratio-label" onclick={() => startEdit('protein')}>Pro: {proteinPct}%</span>
		{/if}
	</div>

	<!-- Protein/Fat divider -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="ratio-grip" onpointerdown={(e) => startDrag('pf', e)}>
		<div class="grip-lines"><div></div><div></div></div>
	</div>

	<!-- Fat segment -->
	<div class="ratio-segment fat" style="width: {fatPct}%">
		{#if editingSegment === 'fat'}
			<!-- svelte-ignore a11y_autofocus -->
			<input
				class="ratio-edit"
				type="number"
				bind:value={editValue}
				onblur={commitEdit}
				onkeydown={onEditKeydown}
				autofocus
			/>
		{:else if fatPct >= 15}
			<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
			<span class="ratio-label" onclick={() => startEdit('fat')}>Fat: {fatPct}%</span>
		{/if}
	</div>
</div>

<style>
	.ratio-bar {
		display: flex;
		align-items: center;
		height: 32px;
		border-radius: 6px;
		overflow: visible;
		width: 100%;
		position: relative;
		user-select: none;
		touch-action: none;
	}

	.ratio-segment {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
		min-width: 0;
		transition: width 0.1s ease;
		position: relative;
	}

	.ratio-segment.carb {
		background: #f59e0b;
		border-radius: 6px 0 0 6px;
	}

	.ratio-segment.protein {
		background: #3b82f6;
	}

	.ratio-segment.fat {
		background: #a855f7;
		border-radius: 0 6px 6px 0;
	}

	.ratio-label {
		font-size: 12px;
		font-weight: 600;
		color: #fff;
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
		cursor: text;
		white-space: nowrap;
		padding: 0 4px;
	}

	.ratio-edit {
		width: 40px;
		font-size: 12px;
		font-weight: 600;
		text-align: center;
		border: 1px solid rgba(255, 255, 255, 0.5);
		border-radius: 3px;
		background: rgba(0, 0, 0, 0.2);
		color: #fff;
		outline: none;
		padding: 1px 2px;
		/* Hide number input arrows */
		-moz-appearance: textfield;
	}

	.ratio-edit::-webkit-outer-spin-button,
	.ratio-edit::-webkit-inner-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}

	.ratio-grip {
		width: 12px;
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: col-resize;
		z-index: 2;
		flex-shrink: 0;
		margin: 0 -6px;
		position: relative;
	}

	.grip-lines {
		display: flex;
		gap: 2px;
		pointer-events: none;
	}

	.grip-lines div {
		width: 2px;
		height: 16px;
		background: rgba(255, 255, 255, 0.7);
		border-radius: 1px;
	}
</style>
```

**Step 2: Commit**

```bash
git add frontend/src/lib/components/MacroRatioBar.svelte
git commit -m "feat: MacroRatioBar draggable stacked bar component"
```

---

### Task 5: Wire up page — state, UI, solve call

**Files:**
- Modify: `frontend/src/routes/+page.svelte`

**Step 1: Add state and imports**

At the top of `<script>`, add import:

```typescript
import MacroRatioBar from '$lib/components/MacroRatioBar.svelte';
```

Add state variables (near line 61, after `proTol`):

```typescript
let carbPct = $state(50);
let proteinPct = $state(25);
let fatPct = $state(25);
```

Update `priorities` default to include `macro_ratio`:

```typescript
let priorities = $state<string[]>(['micros', 'macro_ratio', 'total_weight']);
```

**Step 2: Update doSolve to send new fields**

In `doSolve()` (around line 261), update the solve call:

```typescript
solution = await solve(
    enabled.map((i) => ({ key: i.key, min_g: i.minG, max_g: i.maxG })),
    {
        meal_calories_kcal: mealCal,
        meal_protein_min_g: mealPro,
        meal_fiber_min_g: mealFiberMin,
        cal_tolerance: calTol
    },
    sex,
    ageGroup,
    Array.from(optimizeNutrients),
    priorities,
    pinnedMicros,
    { carb_pct: carbPct, protein_pct: proteinPct, fat_pct: fatPct }
);
```

**Step 3: Remove protein tolerance state and UI**

Remove `proTol` state variable (line 60).

Remove the "Pro tol ±" target-group block from the HTML (lines 533-539).

**Step 4: Add MacroRatioBar to the settings area**

After the targets-row div (line 583), before the closing `</section>` of `targets-section`:

```svelte
<div class="ratio-target">
    <label>Macro target</label>
    <MacroRatioBar
        {carbPct}
        {proteinPct}
        {fatPct}
        onchange={(c, p, f) => { carbPct = c; proteinPct = p; fatPct = f; triggerSolve(); }}
    />
</div>
```

Add CSS:

```css
.ratio-target {
    padding: 8px 16px 12px;
}

.ratio-target label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
    display: block;
}
```

**Step 5: Update priority label display**

In the priority-label span (line 548), add a case for `macro_ratio`:

```svelte
<span class="priority-label">{p === 'micros' ? 'Micronutrient coverage' : p === 'macro_ratio' ? 'Macro ratio target' : 'Minimize total weight'}</span>
```

**Step 6: Update persistence (saveState/loadState)**

In `saveState()` (line 301), add `carbPct, proteinPct, fatPct` to the state object.

In `loadState()` (around line 312), add:

```typescript
if (s.carbPct !== undefined) carbPct = s.carbPct;
if (s.proteinPct !== undefined) proteinPct = s.proteinPct;
if (s.fatPct !== undefined) fatPct = s.fatPct;
```

Remove `proTol` from both save and load.

**Step 7: Commit**

```bash
git add frontend/src/routes/+page.svelte
git commit -m "feat: wire macro ratio bar into page with solve integration"
```

---

### Task 6: Manual smoke test

**Step 1: Start the dev servers**

Run: `cd /Users/sean/code/daily-chow && bash dev.sh`

**Step 2: Verify in browser**

1. Check the macro ratio bar appears in settings area
2. Drag the dividers — segments should resize, solve should re-trigger
3. Click a percentage label, type a new value, press Enter — verify it updates
4. Change ratio to high-fat (e.g., 20/20/60) and verify fat grams increase in solution
5. Verify protein floor works: solution protein should always be >= the minimum
6. Reorder priorities — macro_ratio should appear in the list
7. Refresh page — verify ratio persists (localStorage)

**Step 3: Commit any fixes if needed**
