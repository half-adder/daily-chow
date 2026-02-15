# Macro Constraint Modes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace protein-min / fiber-min with a unified constraint system (≥/≤/=/—, hard/loose) for carbs, protein, fat, and fiber.

**Architecture:** Backend-first approach. Add `MacroConstraint` dataclass to the solver, update the API layer, then build the frontend component and wire it in. The solver handles hard constraints as `model.Add(...)` and loose constraints as penalty terms in the existing minimax objective at the `macro_ratio` priority level.

**Tech Stack:** Python (ortools CP-SAT solver), FastAPI, SvelteKit (Svelte 5 runes), TypeScript

---

### Task 1: Solver — MacroConstraint dataclass and hard constraint logic

**Files:**
- Modify: `src/daily_chow/solver.py:35-41` (Targets dataclass), `src/daily_chow/solver.py:97-171` (solve function signature + constraints)
- Test: `tests/test_solver.py`

**Step 1: Write failing tests for hard constraints**

Add to `tests/test_solver.py`:

```python
from daily_chow.solver import MacroConstraint

class TestMacroConstraints:
    def test_hard_gte_protein(self):
        """Hard >= should enforce minimum protein."""
        constraints = [
            MacroConstraint("protein", "gte", 130, hard=True),
        ]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_protein_g >= 130 - 1

    def test_hard_lte_protein(self):
        """Hard <= should cap protein."""
        constraints = [
            MacroConstraint("protein", "gte", 50, hard=True),
            MacroConstraint("protein", "lte", 80, hard=True),
        ]
        sol = solve(_default_ingredients(), Targets(meal_calories_kcal=2780), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_protein_g <= 80 + 1

    def test_hard_eq_fat(self):
        """Hard = should fix fat within ±1g."""
        constraints = [
            MacroConstraint("fat", "eq", 80, hard=True),
        ]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")
        assert abs(sol.meal_fat_g - 80) <= 1

    def test_hard_lte_fiber(self):
        """Hard <= should cap fiber."""
        constraints = [
            MacroConstraint("fiber", "lte", 30, hard=True),
        ]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_fiber_g <= 30 + 1

    def test_none_mode_no_constraint(self):
        """Mode 'none' should not add any constraint."""
        constraints = [
            MacroConstraint("protein", "none", 0, hard=True),
        ]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")

    def test_backward_compat_no_constraints(self):
        """Solve still works with empty macro_constraints (uses Targets defaults)."""
        sol = solve(_default_ingredients())
        assert sol.status in ("optimal", "feasible")
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_solver.py::TestMacroConstraints -v`
Expected: ImportError or TypeError — `MacroConstraint` doesn't exist yet, `solve()` doesn't accept `macro_constraints`.

**Step 3: Add MacroConstraint dataclass and update solve() signature**

In `src/daily_chow/solver.py`:

1. Add the dataclass after `MacroRatio`:

```python
@dataclass(frozen=True, slots=True)
class MacroConstraint:
    nutrient: str   # 'carbs', 'protein', 'fat', 'fiber'
    mode: str       # 'gte', 'lte', 'eq', 'none'
    grams: int      # target gram value (ignored when mode='none')
    hard: bool = True  # True = hard constraint, False = soft objective
```

2. Update `Targets` — remove `meal_protein_min_g` and `meal_fiber_min_g`:

```python
@dataclass(frozen=True, slots=True)
class Targets:
    meal_calories_kcal: int = 2780
    cal_tolerance: int = 50
```

3. Update `solve()` signature — add `macro_constraints` parameter:

```python
def solve(
    ingredients: list[IngredientInput],
    targets: Targets = Targets(),
    micro_targets: dict[str, float] | None = None,
    micro_uls: dict[str, float] | None = None,
    macro_ratio: MacroRatio | None = None,
    priorities: list[str] | None = None,
    macro_constraints: list[MacroConstraint] | None = None,
    solver_timeout_s: float = 5.0,
) -> Solution:
```

4. Replace the hardcoded protein/fiber constraints (lines 165-171) with a loop over `macro_constraints`:

```python
    # ── Macro constraints ──────────────────────────────────────────────
    macro_exprs = {
        "carbs": total_carb,
        "protein": total_pro,
        "fat": total_fat,
        "fiber": total_fib,
    }

    if macro_constraints:
        for mc in macro_constraints:
            if mc.mode == "none":
                continue
            expr = macro_exprs[mc.nutrient]
            target_scaled = mc.grams * SCALE
            if mc.hard:
                if mc.mode == "gte":
                    model.add(expr >= target_scaled)
                elif mc.mode == "lte":
                    model.add(expr <= target_scaled)
                elif mc.mode == "eq":
                    model.add(expr >= target_scaled)
                    model.add(expr <= target_scaled)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_solver.py::TestMacroConstraints -v`
Expected: All PASS.

**Step 5: Update existing tests that use old Targets fields**

The existing `TestSolverConstraints` and `TestProteinFloor` tests use `Targets(meal_protein_min_g=...)`. Update them to use `macro_constraints`:

- `test_calories_within_tolerance`: just uses `Targets()` — now only has calories fields, still works
- `test_protein_meets_floor`: change to pass `macro_constraints=[MacroConstraint("protein", "gte", 130, hard=True)]`
- `test_fiber_meets_minimum`: change to pass `macro_constraints=[MacroConstraint("fiber", "gte", 26, hard=True)]`
- `TestProteinFloor.test_protein_floor_met`: change to `macro_constraints=[MacroConstraint("protein", "gte", 130, hard=True)]`
- `TestProteinFloor.test_protein_can_exceed_floor`: change to `macro_constraints=[MacroConstraint("protein", "gte", 80, hard=True)]`

**Step 6: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS.

**Step 7: Commit**

```bash
git add src/daily_chow/solver.py tests/test_solver.py
git commit -m "feat(solver): add MacroConstraint with hard gte/lte/eq/none modes"
```

---

### Task 2: Solver — Loose constraint logic

**Files:**
- Modify: `src/daily_chow/solver.py:238-297` (objective section)
- Test: `tests/test_solver.py`

**Step 1: Write failing tests for loose constraints**

Add to `tests/test_solver.py`:

```python
class TestLooseConstraints:
    def test_loose_lte_prefers_lower(self):
        """Loose <= should prefer lower values but not enforce strictly."""
        constraints_loose = [
            MacroConstraint("protein", "lte", 100, hard=False),
        ]
        constraints_none = []
        sol_loose = solve(
            _default_ingredients(),
            macro_constraints=constraints_loose,
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        sol_none = solve(
            _default_ingredients(),
            macro_constraints=constraints_none,
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol_loose.status in ("optimal", "feasible")
        assert sol_none.status in ("optimal", "feasible")
        # Loose cap should push protein lower (or equal) vs unconstrained
        assert sol_loose.meal_protein_g <= sol_none.meal_protein_g + 1

    def test_loose_gte_prefers_higher(self):
        """Loose >= should prefer higher values but not enforce strictly."""
        constraints_loose = [
            MacroConstraint("fiber", "gte", 50, hard=False),
        ]
        constraints_low = [
            MacroConstraint("fiber", "gte", 20, hard=True),
        ]
        sol_loose = solve(
            _default_ingredients(),
            macro_constraints=constraints_loose,
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        sol_low = solve(
            _default_ingredients(),
            macro_constraints=constraints_low,
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol_loose.status in ("optimal", "feasible")
        assert sol_low.status in ("optimal", "feasible")
        # Loose floor should push fiber higher vs low hard floor
        assert sol_loose.meal_fiber_g >= sol_low.meal_fiber_g - 1

    def test_loose_does_not_cause_infeasibility(self):
        """Loose constraint with impossible value should still find a solution."""
        constraints = [
            MacroConstraint("protein", "lte", 1, hard=False),  # impossibly low
        ]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_solver.py::TestLooseConstraints -v`
Expected: FAIL — loose constraints not yet implemented (they're silently ignored).

**Step 3: Implement loose constraints as soft objectives**

In `src/daily_chow/solver.py`, after the hard constraint loop in the macro constraints section, add loose constraint handling. Loose constraint deviations should be collected and fed into the objective alongside macro ratio deviations.

In the macro constraints section:

```python
    # Collect loose constraint deviation vars for the objective
    loose_dev_vars: list[cp_model.IntVar] = []
    max_loose_dev = 0

    if macro_constraints:
        for mc in macro_constraints:
            if mc.mode == "none":
                continue
            expr = macro_exprs[mc.nutrient]
            target_scaled = mc.grams * SCALE
            if mc.hard:
                # ... (existing hard constraint code)
            else:
                # Loose: add deviation variable as soft objective
                # Max possible deviation bounded by ingredient maxes
                max_macro = sum(
                    ing.max_g * _scaled_coeff(getattr(ing.food, f"{mc.nutrient}_g_per_100g", 0))
                    for ing in ingredients
                ) if mc.nutrient != "fiber" else sum(
                    ing.max_g * _scaled_coeff(ing.food.fiber_g_per_100g)
                    for ing in ingredients
                )
                if mc.mode == "gte":
                    # deviation = max(0, target - actual)
                    dev = model.new_int_var(0, max(target_scaled, 1), f"loose_{mc.nutrient}_gte_dev")
                    model.add(dev >= target_scaled - expr)
                    loose_dev_vars.append(dev)
                elif mc.mode == "lte":
                    # deviation = max(0, actual - target)
                    dev = model.new_int_var(0, max(max_macro, 1), f"loose_{mc.nutrient}_lte_dev")
                    model.add(dev >= expr - target_scaled)
                    loose_dev_vars.append(dev)
                elif mc.mode == "eq":
                    # deviation = |actual - target|
                    diff = model.new_int_var(-max(max_macro, 1), max(max_macro, 1), f"loose_{mc.nutrient}_eq_diff")
                    model.add(diff == expr - target_scaled)
                    dev = model.new_int_var(0, max(max_macro, 1), f"loose_{mc.nutrient}_eq_dev")
                    model.add_abs_equality(dev, diff)
                    loose_dev_vars.append(dev)
                max_loose_dev = max(max_loose_dev, max_macro)
```

Then update the objective section to include `loose_dev_vars`. Add a `worst_loose_var` using minimax alongside `macro_worst_var` at the `PRIORITY_MACRO_RATIO` level:

```python
    # ── Loose constraint minimax ─────────────────────────────────────
    worst_loose_var: cp_model.IntVar | None = None
    max_worst_loose = 0

    if loose_dev_vars:
        worst_loose_var = model.new_int_var(0, max_loose_dev, "worst_loose")
        for dv in loose_dev_vars:
            model.add(worst_loose_var >= dv)
        max_worst_loose = max_loose_dev
```

In the objective terms section, add `worst_loose_var` alongside `macro_worst_var` under `PRIORITY_MACRO_RATIO`:

```python
        elif p == PRIORITY_MACRO_RATIO:
            if macro_worst_var is not None and max_macro_worst > 0:
                terms.append((macro_worst_var, max_macro_worst))
            if worst_loose_var is not None and max_worst_loose > 0:
                terms.append((worst_loose_var, max_worst_loose))
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_solver.py::TestLooseConstraints -v`
Expected: All PASS.

**Step 5: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS.

**Step 6: Commit**

```bash
git add src/daily_chow/solver.py tests/test_solver.py
git commit -m "feat(solver): add loose constraints as soft objectives at macro_ratio priority"
```

---

### Task 3: Solver — Exclude hard `=` macros from ratio optimization

**Files:**
- Modify: `src/daily_chow/solver.py:238-297` (macro ratio section)
- Test: `tests/test_solver.py`

**Step 1: Write failing test**

```python
class TestRatioExclusion:
    def test_hard_eq_excluded_from_ratio(self):
        """Hard = macro should not participate in ratio optimization."""
        # Fix fat at 80g, set ratio to 50/25/25
        constraints = [
            MacroConstraint("fat", "eq", 80, hard=True),
        ]
        ratio = MacroRatio(carb_pct=50, protein_pct=25, fat_pct=25)
        sol = solve(
            _default_ingredients(),
            macro_ratio=ratio,
            macro_constraints=constraints,
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol.status in ("optimal", "feasible")
        # Fat should be ~80g regardless of what the ratio says
        assert abs(sol.meal_fat_g - 80) <= 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_solver.py::TestRatioExclusion -v`
Expected: Likely passes already (hard constraint wins over soft ratio). If so, this test documents existing behavior — still valuable. Move on.

**Step 3: Filter hard `=` macros from the ratio loop**

In the macro ratio section (around line 269), build a set of excluded nutrients:

```python
    # Determine which macros are excluded from ratio optimization (hard eq)
    ratio_excluded: set[str] = set()
    if macro_constraints:
        for mc in macro_constraints:
            if mc.mode == "eq" and mc.hard:
                ratio_excluded.add(mc.nutrient)
```

Then filter the ratio loop:

```python
        ratio_macros = [
            ("carb", day_carb_cal, macro_ratio.carb_pct),
            ("pro", day_pro_cal, macro_ratio.protein_pct),
            ("fat", day_fat_cal, macro_ratio.fat_pct),
        ]
        # Map ratio names to constraint nutrient names
        ratio_to_nutrient = {"carb": "carbs", "pro": "protein", "fat": "fat"}

        macro_dev_vars: list[cp_model.IntVar] = []
        for name, cal_expr, target_pct in ratio_macros:
            if ratio_to_nutrient[name] in ratio_excluded:
                continue
            # ... existing deviation calculation ...
```

**Step 4: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add src/daily_chow/solver.py tests/test_solver.py
git commit -m "feat(solver): exclude hard = macros from ratio optimization"
```

---

### Task 4: API — Update request/response models

**Files:**
- Modify: `src/daily_chow/api.py:20-67` (imports, models), `src/daily_chow/api.py:145-206` (endpoint)
- Test: `tests/test_api_health.py` (quick sanity check)

**Step 1: Update API models**

In `src/daily_chow/api.py`:

1. Update import to include `MacroConstraint`:

```python
from daily_chow.solver import DEFAULT_PRIORITIES, IngredientInput, MacroConstraint, MacroRatio, Targets, solve
```

2. Add `MacroConstraintRequest` model:

```python
class MacroConstraintRequest(BaseModel):
    nutrient: str = "protein"  # 'carbs', 'protein', 'fat', 'fiber'
    mode: str = "none"         # 'gte', 'lte', 'eq', 'none'
    grams: int = 0
    hard: bool = True
```

3. Update `TargetsRequest` — remove protein/fiber fields:

```python
class TargetsRequest(BaseModel):
    meal_calories_kcal: int = 2780
    cal_tolerance: int = 50
```

4. Add `macro_constraints` to `SolveRequest`:

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
    macro_constraints: list[MacroConstraintRequest] = []
    # Backward compat — old clients may still send these
    meal_protein_min_g: int | None = None
    meal_fiber_min_g: int | None = None
```

Wait — `meal_protein_min_g` and `meal_fiber_min_g` are nested inside `targets`, not top-level. We need backward compat inside `TargetsRequest`:

```python
class TargetsRequest(BaseModel):
    meal_calories_kcal: int = 2780
    cal_tolerance: int = 50
    # Backward compat — old clients may still send these
    meal_protein_min_g: int | None = None
    meal_fiber_min_g: int | None = None
```

5. Update the endpoint to convert constraints:

```python
    targets = Targets(
        meal_calories_kcal=req.targets.meal_calories_kcal,
        cal_tolerance=req.targets.cal_tolerance,
    )

    # Build macro constraints
    macro_constraints: list[MacroConstraint] = []
    if req.macro_constraints:
        macro_constraints = [
            MacroConstraint(
                nutrient=mc.nutrient,
                mode=mc.mode,
                grams=mc.grams,
                hard=mc.hard,
            )
            for mc in req.macro_constraints
        ]
    else:
        # Backward compat: convert old protein/fiber fields
        pro_min = req.targets.meal_protein_min_g
        fib_min = req.targets.meal_fiber_min_g
        if pro_min is not None:
            macro_constraints.append(MacroConstraint("protein", "gte", pro_min, hard=True))
        if fib_min is not None:
            macro_constraints.append(MacroConstraint("fiber", "gte", fib_min, hard=True))

    solution = solve(
        ingredient_inputs, targets,
        micro_targets=micro_targets, micro_uls=micro_uls,
        macro_ratio=macro_ratio,
        priorities=req.priorities,
        macro_constraints=macro_constraints or None,
    )
```

**Step 2: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS.

**Step 3: Commit**

```bash
git add src/daily_chow/api.py
git commit -m "feat(api): add MacroConstraintRequest, backward compat for old targets"
```

---

### Task 5: Frontend — API types and solve() update

**Files:**
- Modify: `frontend/src/lib/api.ts`

**Step 1: Update TypeScript types**

In `frontend/src/lib/api.ts`:

1. Add `MacroConstraint` interface:

```typescript
export interface MacroConstraint {
	nutrient: 'carbs' | 'protein' | 'fat' | 'fiber';
	mode: 'gte' | 'lte' | 'eq' | 'none';
	grams: number;
	hard: boolean;
}
```

2. Update `SolveTargets` — remove protein/fiber:

```typescript
export interface SolveTargets {
	meal_calories_kcal: number;
	cal_tolerance: number;
}
```

3. Update `solve()` function signature:

```typescript
export async function solve(
	ingredients: SolveIngredient[],
	targets: SolveTargets,
	sex: string,
	age_group: string,
	optimize_nutrients: string[],
	priorities: string[],
	pinned_micros: Record<string, number> = {},
	macro_ratio: MacroRatio | null = null,
	macro_constraints: MacroConstraint[] = []
): Promise<SolveResponse> {
	const res = await fetch('/api/solve', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			ingredients, targets, sex, age_group,
			optimize_nutrients, priorities, pinned_micros,
			macro_ratio, macro_constraints
		})
	});
	return res.json();
}
```

**Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(frontend): update API types for macro constraints"
```

---

### Task 6: Frontend — MacroConstraintWheel component

**Files:**
- Create: `frontend/src/lib/components/MacroConstraintWheel.svelte`

**Step 1: Create the component**

Create `frontend/src/lib/components/MacroConstraintWheel.svelte`. The component renders:

1. **Label** — macro name (Carbs, Protein, Fat, Fiber)
2. **Wheel** — vertical cycling through modes: ≥ → ≤ → = → — → ≥
3. **Lock icon** — toggles hard/loose
4. **Gram input** — numeric input

Props:

```typescript
interface Props {
    label: string;
    mode: 'gte' | 'lte' | 'eq' | 'none';
    grams: number;
    hard: boolean;
    onchange: (mode: string, grams: number, hard: boolean) => void;
}
```

The wheel display logic:
- `MODES` array: `['gte', 'lte', 'eq', 'none']`
- `SYMBOLS` map: `{ gte: '≥', lte: '≤', eq: '=', none: '—' }`
- Current mode index → prev/next indices (wrapping) shown above/below at 60% scale, 30% opacity
- Click cycles to next mode with CSS transition (translateY animation)

When mode is `none`, grey out and disable the lock icon and gram input.

The lock icon should be an inline SVG — a simple padlock shape. Locked = filled, unlocked = outlined/open.

```svelte
<script lang="ts">
    interface Props {
        label: string;
        mode: 'gte' | 'lte' | 'eq' | 'none';
        grams: number;
        hard: boolean;
        onchange: (mode: string, grams: number, hard: boolean) => void;
    }

    let { label, mode, grams, hard, onchange }: Props = $props();

    const MODES = ['gte', 'lte', 'eq', 'none'] as const;
    const SYMBOLS: Record<string, string> = { gte: '≥', lte: '≤', eq: '=', none: '—' };

    let animating = $state(false);
    let direction = $state(1); // 1 = forward, -1 = backward

    function currentIndex() {
        return MODES.indexOf(mode);
    }

    function prevMode() {
        return MODES[(currentIndex() - 1 + MODES.length) % MODES.length];
    }

    function nextMode() {
        return MODES[(currentIndex() + 1) % MODES.length];
    }

    function cycleMode() {
        direction = 1;
        animating = true;
        setTimeout(() => {
            const next = nextMode();
            animating = false;
            onchange(next, grams, hard);
        }, 200);
    }

    function toggleHard() {
        if (mode === 'none') return;
        onchange(mode, grams, !hard);
    }

    function onGramsChange(e: Event) {
        const val = parseInt((e.target as HTMLInputElement).value);
        if (!isNaN(val) && val >= 0) {
            onchange(mode, val, hard);
        }
    }
</script>

<div class="macro-constraint" class:disabled={mode === 'none'}>
    <span class="mc-label">{label}</span>
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div class="wheel" onclick={cycleMode}>
        <span class="wheel-item adjacent">{SYMBOLS[prevMode()]}</span>
        <span class="wheel-item active" class:animating>{SYMBOLS[mode]}</span>
        <span class="wheel-item adjacent">{SYMBOLS[nextMode()]}</span>
    </div>
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <span class="lock" class:locked={hard} class:disabled={mode === 'none'} onclick={toggleHard} title={hard ? 'Hard (click for loose)' : 'Loose (click for hard)'}>
        {#if hard}
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
        {:else}
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 9.9-1"/>
            </svg>
        {/if}
    </span>
    <input
        class="mc-input"
        type="number"
        value={grams}
        disabled={mode === 'none'}
        onchange={onGramsChange}
    />
    <span class="mc-unit">g</span>
</div>
```

Style the wheel with `overflow: hidden`, fixed height, vertical layout, CSS transitions on `transform: translateY(...)` for the rotation animation. Adjacent items at `transform: scale(0.6)`, `opacity: 0.3`.

**Step 2: Verify it renders**

Check the dev server (should already be running). Temporarily import and render the component in `+page.svelte` with test props. Visually confirm the wheel cycles, lock toggles, and input works.

**Step 3: Commit**

```bash
git add frontend/src/lib/components/MacroConstraintWheel.svelte
git commit -m "feat(frontend): add MacroConstraintWheel component with wheel + lock"
```

---

### Task 7: Frontend — Wire up MacroConstraintWheel in +page.svelte

**Files:**
- Modify: `frontend/src/routes/+page.svelte`

**Step 1: Update state declarations**

Replace the old protein/fiber state variables (lines 58-59):

```typescript
// Old:
// let dailyPro = $state(160);
// let dailyFiberMin = $state(40);

// New:
interface MacroConstraintState {
    nutrient: 'carbs' | 'protein' | 'fat' | 'fiber';
    mode: 'gte' | 'lte' | 'eq' | 'none';
    grams: number;
    hard: boolean;
}

let macroConstraints = $state<MacroConstraintState[]>([
    { nutrient: 'carbs',   mode: 'none', grams: 0,   hard: true },
    { nutrient: 'protein', mode: 'gte',  grams: 160, hard: true },
    { nutrient: 'fat',     mode: 'none', grams: 0,   hard: true },
    { nutrient: 'fiber',   mode: 'gte',  grams: 40,  hard: true },
]);
```

**Step 2: Update derived meal-level values**

Replace `mealPro` and `mealFiberMin` derivations (lines 152-153). These are no longer simple subtractions — they need to derive from `macroConstraints` and subtract pinned totals:

```typescript
let mealConstraints = $derived(macroConstraints.map(mc => {
    if (mc.mode === 'none') return mc;
    const pinnedKey = mc.nutrient === 'carbs' ? 'carbs_g' :
                      mc.nutrient === 'protein' ? 'protein_g' :
                      mc.nutrient === 'fat' ? 'fat_g' : 'fiber_g';
    const pinned = pinnedTotals[pinnedKey] ?? 0;
    return { ...mc, grams: Math.max(0, mc.grams - pinned) };
}));
```

**Step 3: Update doSolve() to use new API**

Replace the solve call (lines 251-270):

```typescript
solution = await solve(
    enabled.map((i) => ({ key: i.key, min_g: i.minG, max_g: i.maxG })),
    {
        meal_calories_kcal: mealCal,
        cal_tolerance: calTol
    },
    sex,
    ageGroup,
    ALL_MICRO_KEYS,
    priorities,
    pinnedMicros,
    {
        carb_pct: carbPct, protein_pct: proteinPct, fat_pct: fatPct,
        pinned_carb_g: pinnedTotals.carbs_g ?? 0,
        pinned_protein_g: pinnedTotals.protein_g ?? 0,
        pinned_fat_g: pinnedTotals.fat_g ?? 0
    },
    mealConstraints.filter(mc => mc.mode !== 'none').map(mc => ({
        nutrient: mc.nutrient,
        mode: mc.mode,
        grams: mc.grams,
        hard: mc.hard
    }))
);
```

**Step 4: Update the template — replace protein/fiber inputs**

Replace the protein target group (lines 509-515) and fiber target group (lines 516-522) with four `MacroConstraintWheel` components:

```svelte
{#each macroConstraints as mc, i}
    <MacroConstraintWheel
        label={mc.nutrient === 'carbs' ? 'Carbs' :
               mc.nutrient === 'protein' ? 'Protein' :
               mc.nutrient === 'fat' ? 'Fat' : 'Fiber'}
        mode={mc.mode}
        grams={mc.grams}
        hard={mc.hard}
        onchange={(mode, grams, hard) => {
            macroConstraints[i] = { ...mc, mode, grams, hard };
            macroConstraints = [...macroConstraints];
            triggerSolve();
        }}
    />
{/each}
```

Import the component at the top:

```typescript
import MacroConstraintWheel from '$lib/components/MacroConstraintWheel.svelte';
```

**Step 5: Update persistence — saveState and loadState**

In `saveState()` — replace `dailyPro, dailyFiberMin` with `macroConstraints`:

```typescript
function saveState() {
    const state = {
        dailyCal,
        macroConstraints,
        pinnedMeals, pinnedMealsOpen,
        calTol, carbPct, proteinPct, fatPct,
        priorities, theme, ingredients,
        sex, ageGroup,
        microsOpen, sliderAbsMax, hasSeenWelcome: true
    };
    localStorage.setItem('daily-chow', JSON.stringify(state));
}
```

In `loadState()` — add migration from old format:

```typescript
// Migration: old dailyPro/dailyFiberMin → macroConstraints
if (s.macroConstraints) {
    macroConstraints = s.macroConstraints;
} else {
    // Migrate from old format
    const pro = s.dailyPro ?? 160;
    const fib = s.dailyFiberMin ?? 40;
    macroConstraints = [
        { nutrient: 'carbs',   mode: 'none', grams: 0,   hard: true },
        { nutrient: 'protein', mode: 'gte',  grams: pro, hard: true },
        { nutrient: 'fat',     mode: 'none', grams: 0,   hard: true },
        { nutrient: 'fiber',   mode: 'gte',  grams: fib, hard: true },
    ];
}
```

**Step 6: Verify end-to-end**

Open the app in the browser. Confirm:
- Four macro constraint wheels render
- Cycling modes works with animation
- Lock toggle works
- Changing gram values triggers solve
- Solution updates correctly
- Clamping protein with `≤` actually caps the result

**Step 7: Commit**

```bash
git add frontend/src/routes/+page.svelte
git commit -m "feat(frontend): wire MacroConstraintWheel into main page, replace old protein/fiber inputs"
```

---

### Task 8: Frontend — MacroRatioBar updates for greyed-out segments

**Files:**
- Modify: `frontend/src/lib/components/MacroRatioBar.svelte`
- Modify: `frontend/src/routes/+page.svelte` (pass new prop)

**Step 1: Add `disabledSegments` prop to MacroRatioBar**

In `MacroRatioBar.svelte`, update Props:

```typescript
interface Props {
    carbPct: number;
    proteinPct: number;
    fatPct: number;
    disabledSegments?: Set<string>;  // e.g. Set(['protein']) — greyed out
    onchange: (carb: number, protein: number, fat: number) => void;
}

let { carbPct, proteinPct, fatPct, disabledSegments = new Set(), onchange }: Props = $props();
```

**Step 2: Apply greyed-out styling**

For each segment, add a `disabled` class when it's in `disabledSegments`:

```svelte
<div class="ratio-segment carb" class:segment-disabled={disabledSegments.has('carbs')} style="width: {carbPct}%">
```

Similarly for protein and fat segments. Add CSS:

```css
.ratio-segment.segment-disabled {
    opacity: 0.35;
    filter: grayscale(0.8);
}
```

**Step 3: Disable drag handles adjacent to disabled segments**

In the `startDrag` function, check if both adjacent segments are disabled. If the 'cp' handle connects carb and protein and either is disabled, skip. Same for 'pf' handle:

```typescript
function startDrag(handle: 'cp' | 'pf', e: PointerEvent) {
    if (handle === 'cp' && (disabledSegments.has('carbs') || disabledSegments.has('protein'))) return;
    if (handle === 'pf' && (disabledSegments.has('protein') || disabledSegments.has('fat'))) return;
    dragging = handle;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    e.preventDefault();
}
```

Also disable click-to-edit for disabled segments:

```typescript
function startEdit(segment: 'carb' | 'protein' | 'fat') {
    const nutrientName = segment === 'carb' ? 'carbs' : segment;
    if (disabledSegments.has(nutrientName)) return;
    // ... existing code
}
```

**Step 4: Pass `disabledSegments` from +page.svelte**

Compute which segments are disabled (hard `=` macros):

```typescript
let ratioDisabled = $derived(
    new Set(
        macroConstraints
            .filter(mc => mc.mode === 'eq' && mc.hard && mc.nutrient !== 'fiber')
            .map(mc => mc.nutrient)
    )
);
```

Pass to the component:

```svelte
<MacroRatioBar
    {carbPct}
    {proteinPct}
    {fatPct}
    disabledSegments={ratioDisabled}
    onchange={(c, p, f) => { carbPct = c; proteinPct = p; fatPct = f; triggerSolve(); }}
/>
```

**Step 5: Verify visually**

Set a macro to hard `=` and confirm its ratio bar segment greys out and handles are disabled.

**Step 6: Commit**

```bash
git add frontend/src/lib/components/MacroRatioBar.svelte frontend/src/routes/+page.svelte
git commit -m "feat(frontend): grey out ratio bar segments for hard = macros"
```

---

### Task 9: Frontend — Pre-solve conflict detection

**Files:**
- Modify: `frontend/src/routes/+page.svelte`

**Step 1: Add conflict detection function**

Add a function that checks for arithmetic conflicts before solving. Place it near `doSolve()`:

```typescript
function detectConflicts(): string | null {
    const cal = dailyCal;

    // Only check hard constraints against ratio
    const hardConstraints = macroConstraints.filter(mc => mc.hard && mc.mode !== 'none' && mc.nutrient !== 'fiber');

    // Check: hard constraints vs calorie budget
    // Sum minimum calories from hard >= and hard = constraints
    let minCal = 0;
    let maxCal = Infinity;
    for (const mc of hardConstraints) {
        const calPerG = mc.nutrient === 'fat' ? 9 : 4;
        if (mc.mode === 'gte' || mc.mode === 'eq') {
            minCal += mc.grams * calPerG;
        }
        if (mc.mode === 'lte' || mc.mode === 'eq') {
            // maxCal from caps — not summed, but individual checks below
        }
    }
    if (minCal > cal + calTol) {
        return `Hard macro floors require at least ${minCal} cal — daily target is ${cal} cal`;
    }

    // Check: each hard constraint vs its ratio target percentage
    const ratioMap: Record<string, number> = { carbs: carbPct, protein: proteinPct, fat: fatPct };
    for (const mc of hardConstraints) {
        const targetPct = ratioMap[mc.nutrient];
        if (targetPct === undefined) continue;
        const calPerG = mc.nutrient === 'fat' ? 9 : 4;
        const impliedPct = Math.round((mc.grams * calPerG) / cal * 100);

        if (mc.mode === 'lte' && impliedPct < targetPct) {
            return `${mc.nutrient} capped at ${mc.grams}g can only reach ${impliedPct}% of ${cal} cal — ratio target requires ${targetPct}%`;
        }
        if (mc.mode === 'gte' && impliedPct > targetPct) {
            return `${mc.nutrient} floor of ${mc.grams}g forces at least ${impliedPct}% of ${cal} cal — ratio target is ${targetPct}%`;
        }
        if (mc.mode === 'eq' && impliedPct !== targetPct) {
            return `${mc.nutrient} fixed at ${mc.grams}g (${impliedPct}% of ${cal} cal) — ratio target is ${targetPct}%`;
        }
    }

    return null;
}
```

**Step 2: Integrate into doSolve()**

At the start of `doSolve()`, before the API call:

```typescript
async function doSolve() {
    const enabled = ingredients.filter((i) => i.enabled);
    if (enabled.length === 0) {
        solution = {
            status: 'infeasible', ingredients: [], meal_calories_kcal: 0, meal_protein_g: 0,
            meal_fat_g: 0, meal_carbs_g: 0, meal_fiber_g: 0, micros: {}
        };
        conflictReason = null;
        return;
    }

    // Pre-solve conflict detection
    const conflict = detectConflicts();
    if (conflict) {
        solution = {
            status: 'infeasible', ingredients: [], meal_calories_kcal: 0, meal_protein_g: 0,
            meal_fat_g: 0, meal_carbs_g: 0, meal_fiber_g: 0, micros: {}
        };
        conflictReason = conflict;
        return;
    }
    conflictReason = null;

    // ... rest of doSolve
```

Add state variable:

```typescript
let conflictReason = $state<string | null>(null);
```

**Step 3: Display conflict reason in the infeasibility UI**

Update the infeasibility display (around line 714):

```svelte
{#if solution.status === 'infeasible'}
    {#if conflictReason}
        ✗ CONFLICT — {conflictReason}
    {:else}
        ✗ INFEASIBLE — widen ranges or disable ingredients
    {/if}
{:else}
    ✓ {solution.status.toUpperCase()}
{/if}
```

**Step 4: Verify end-to-end**

Test scenarios:
- Set protein hard `≤ 50g` with ratio at 25% and 3500 cal → should show conflict message
- Set carbs hard `≥ 400g` with ratio at 30% and 2500 cal → should show conflict
- Remove the conflicting constraint → should solve normally

**Step 5: Commit**

```bash
git add frontend/src/routes/+page.svelte
git commit -m "feat(frontend): pre-solve conflict detection with explanatory messages"
```

---

### Task 10: Polish and final verification

**Step 1: Run full backend test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS.

**Step 2: Manual end-to-end testing in browser**

Verify all features work together:
- [ ] Wheel cycles through all four modes with animation
- [ ] Lock icon toggles hard/loose
- [ ] Gram input updates and triggers solve
- [ ] Unconstrained (`—`) disables input and lock
- [ ] Hard `≤` actually caps the solved result
- [ ] Hard `=` actually fixes the solved result and greys out ratio bar segment
- [ ] Loose constraints influence but don't strictly enforce
- [ ] Conflict detection fires and shows message for impossible combinations
- [ ] State persists across page refresh
- [ ] Old localStorage format migrates correctly (clear storage and test with old format)
- [ ] Pinned meals correctly subtract from constraint grams

**Step 3: Commit any polish fixes**

```bash
git add -A
git commit -m "polish: macro constraint UI and behavior refinements"
```
