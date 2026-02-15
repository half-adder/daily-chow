# Macro Constraint Modes Design

## Goal

Replace the single protein-min / fiber-min fields with a unified constraint system for all four macros (carbs, protein, fat, fiber). Each macro gets a configurable constraint mode (≥, ≤, =, or unconstrained) with hard/loose enforcement. This lets users clamp expensive macros like protein (hard ≤) while keeping others ratio-driven.

## UI: Constraint Wheel + Lock

Each macro field in the targets row has three elements:

```
        ≤
Protein ≥  🔒  [160] g
        =
```

### Constraint wheel (left)

A vertical mini-wheel that cycles through four modes on click:

- `≥` — at least N grams
- `≤` — at most N grams (the "clamp")
- `=` — exactly N grams
- `—` — unconstrained (no target)

The active mode is displayed at full size and opacity. The adjacent modes (one above, one below in the cycle) are visible but at ~60% scale and ~30% opacity, hinting at a selection wheel. Clicking animates a wheel rotation (~200ms ease-out) to the next mode.

When set to `—`, the gram input and lock icon are greyed out / disabled since there's nothing to enforce.

### Lock icon (middle)

A small lock/unlock icon toggling hard vs loose enforcement:

- 🔒 **Hard**: solver must satisfy this constraint. Infeasible if impossible.
- 🔓 **Loose**: solver treats this as a soft objective. Competes with other soft objectives (macro ratio, other loose constraints) via the priority system.

Greyed out when constraint mode is `—` (unconstrained).

### Gram input (right)

Numeric input for the target gram value.

### Defaults

| Macro   | Mode | Hard/Loose | Grams |
|---------|------|------------|-------|
| Carbs   | —    | n/a        | —     |
| Protein | ≥    | Hard       | 160   |
| Fat     | —    | n/a        | —     |
| Fiber   | ≥    | Hard       | 40    |

### MacroRatioBar interaction

- Macros with mode `=` (hard) are greyed out in the ratio bar — no freedom to optimize.
- All other constrained macros (≥, ≤, loose =) still participate in ratio optimization. Hard constraints clip the feasible range; the ratio optimizer works within that range.
- Unconstrained macros (`—`) are fully ratio-driven.
- Drag handles adjacent to a greyed-out segment are disabled.

## Pre-Solve Conflict Detection

Before calling the solver, the frontend checks for arithmetic conflicts between hard constraints and other targets. If any conflict is detected, no solution is displayed — instead, the UI shows an infeasibility-style error with a specific reason.

### Checks

1. **Hard cap vs ratio target**: hard `≤ 160g` protein but ratio at current calories requires 219g → "Protein capped at 160g can only reach 18% of 3500 cal — ratio target requires 25%"

2. **Hard floor vs ratio target**: hard `≥ 300g` carbs but ratio at current calories only allows 250g → "Carbs floor of 300g forces at least 34% of 3500 cal — ratio target is 29%"

3. **Hard constraints vs calorie budget**: hard `≥ 300g` carbs (1200 cal) + hard `≥ 200g` protein (800 cal) + hard `≥ 100g` fat (900 cal) = 2900 cal minimum, exceeding a 2500 cal target → "Hard macro floors require at least 2900 cal — daily target is 2500 cal"

4. **Hard `=` vs ratio**: hard `= 100g` fat at 3000 cal = 30%, but ratio target is 25% → "Fat fixed at 100g (30% of 3000 cal) — ratio target is 25%"

These checks only apply to hard (🔒) constraints. Loose constraints are soft objectives and cannot conflict.

## Solver Changes

### New data model

Replace `Targets.meal_protein_min_g` and `Targets.meal_fiber_min_g` with a list of `MacroConstraint`:

```python
@dataclass(frozen=True, slots=True)
class MacroConstraint:
    nutrient: str   # 'carbs', 'protein', 'fat', 'fiber'
    mode: str       # 'gte', 'lte', 'eq', 'none'
    grams: int      # target gram value (ignored when mode='none')
    hard: bool      # True = hard constraint, False = soft objective
```

`Targets` shrinks to just `meal_calories_kcal` and `cal_tolerance`.

### Hard constraints (🔒)

Added as `model.Add(...)` — inviolable:

- `gte`: `model.Add(total_macro >= grams * SCALE)`
- `lte`: `model.Add(total_macro <= grams * SCALE)`
- `eq`: `model.Add(total_macro >= grams * SCALE)` + `model.Add(total_macro <= grams * SCALE)`
- `none`: no constraint added

### Loose constraints (🔓)

Added as penalty terms in the objective function. For each loose constraint, a deviation variable measures how far the actual value is from the target:

- `gte`: deviation = max(0, target - actual)
- `lte`: deviation = max(0, actual - target)
- `eq`: deviation = |actual - target|

These deviation variables participate in the minimax objective alongside macro ratio deviations, sharing the same priority level (`macro_ratio`). The lexicographic priority system ensures higher-priority objectives (e.g., micros) are never sacrificed for loose constraints.

### Ratio optimization

- Macros with hard `=` are excluded from ratio optimization (zero freedom).
- All other macros participate. Hard `≥`/`≤` constraints clip the feasible range; the ratio optimizer works within it.
- Unconstrained macros are fully ratio-driven.

## API Changes

### Request model

```python
class MacroConstraintRequest(BaseModel):
    nutrient: str          # 'carbs', 'protein', 'fat', 'fiber'
    mode: str = 'none'     # 'gte', 'lte', 'eq', 'none'
    grams: int = 0
    hard: bool = True

class SolveRequest(BaseModel):
    ingredients: list[IngredientRequest]
    targets: TargetsRequest          # just calories + tolerance now
    macro_constraints: list[MacroConstraintRequest] = []
    macro_ratio: MacroRatioRequest | None = None
    priorities: list[str] = list(DEFAULT_PRIORITIES)
    # ... rest unchanged
```

### Backward compatibility

If `macro_constraints` is empty and the old `meal_protein_min_g` / `meal_fiber_min_g` fields are present, convert them to `MacroConstraint(mode='gte', hard=True)` for backward compatibility during migration.

## Frontend State

```typescript
interface MacroConstraint {
    nutrient: 'carbs' | 'protein' | 'fat' | 'fiber';
    mode: 'gte' | 'lte' | 'eq' | 'none';
    grams: number;
    hard: boolean;
}

let macroConstraints = $state<MacroConstraint[]>([
    { nutrient: 'carbs',   mode: 'none', grams: 0,   hard: true },
    { nutrient: 'protein', mode: 'gte',  grams: 160, hard: true },
    { nutrient: 'fat',     mode: 'none', grams: 0,   hard: true },
    { nutrient: 'fiber',   mode: 'gte',  grams: 40,  hard: true },
]);
```

Persisted to localStorage. Old `dailyPro` / `dailyFiberMin` state migrated on load.

## Files to Change

| File | Change |
|------|--------|
| `frontend/src/lib/components/MacroConstraintWheel.svelte` | New component: wheel + lock + input |
| `frontend/src/lib/components/MacroRatioBar.svelte` | Grey out segments for hard `=` macros |
| `frontend/src/routes/+page.svelte` | Replace protein/fiber inputs with MacroConstraintWheel per macro; add pre-solve conflict detection; update state/persistence |
| `frontend/src/lib/api.ts` | Add `MacroConstraint` type; update `solve()` call |
| `src/daily_chow/solver.py` | Replace `Targets` protein/fiber fields with `MacroConstraint` list; add hard/loose constraint logic |
| `src/daily_chow/api.py` | Add `MacroConstraintRequest`; update `SolveRequest` and endpoint |
