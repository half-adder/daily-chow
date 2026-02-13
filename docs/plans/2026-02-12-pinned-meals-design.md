# Pinned Meals Design

Generalize the hardcoded smoothie into user-addable, user-configurable "pinned meals." The solver works around the aggregate of all pinned meals. Users specify macros (required) and micros (optional) per meal, with JSON import/export support.

## Data Model

```typescript
interface PinnedMeal {
  id: string;                          // crypto.randomUUID()
  name: string;
  nutrients: Record<string, number>;   // unit-suffixed keys, non-negative
}
```

### Nutrient Keys (canonical vocabulary)

**Macros (required):** `calories_kcal`, `protein_g`, `fat_g`, `carbs_g`, `fiber_g`

**Micros (optional):** `calcium_mg`, `iron_mg`, `magnesium_mg`, `phosphorus_mg`, `potassium_mg`, `zinc_mg`, `copper_mg`, `manganese_mg`, `selenium_mcg`, `vitamin_c_mg`, `thiamin_mg`, `riboflavin_mg`, `niacin_mg`, `vitamin_b6_mg`, `folate_mcg`, `vitamin_b12_mcg`, `vitamin_a_mcg`, `vitamin_d_mcg`, `vitamin_e_mg`, `vitamin_k_mcg`

### JSON Schema

Located at `src/daily_chow/data/schemas/pinned-meal.schema.json`. Validates:

- Single meal object or array of meals
- `name` required, string
- `nutrients` required, all 5 macros required, 20 micros optional
- `additionalProperties: false` on nutrients (rejects typos)
- All nutrient values: `type: number`, `minimum: 0`

### JSON Import/Export Format

Identical to the data model. Accepts single object or array:

```json
{
  "name": "Morning Smoothie",
  "nutrients": {
    "calories_kcal": 720,
    "protein_g": 30,
    "fat_g": 15,
    "carbs_g": 80,
    "fiber_g": 14,
    "calcium_mg": 659,
    "vitamin_b12_mcg": 1.9
  }
}
```

## Macro Field Rename

Prerequisite refactor: rename all macro field names to include units for consistency with the nutrient key vocabulary. ~91 references across 11 files, mechanical find-and-replace.

### Rename Map

| Current | New |
|---|---|
| `cal_per_100g` | `calories_kcal_per_100g` |
| `protein_per_100g` | `protein_g_per_100g` |
| `fat_per_100g` | `fat_g_per_100g` |
| `carbs_per_100g` | `carbs_g_per_100g` |
| `fiber_per_100g` | `fiber_g_per_100g` |
| `calories` (on ingredients) | `calories_kcal` |
| `protein` (on ingredients) | `protein_g` |
| `fat` (on ingredients) | `fat_g` |
| `carbs` (on ingredients) | `carbs_g` |
| `fiber` (on ingredients) | `fiber_g` |
| `meal_calories` | `meal_calories_kcal` |
| `meal_protein` | `meal_protein_g` |
| `meal_fat` | `meal_fat_g` |
| `meal_carbs` | `meal_carbs_g` |
| `meal_fiber` | `meal_fiber_g` |
| `meal_fiber_min` | `meal_fiber_min_g` |

### Files Affected

**Python (4 files):**
- `food_db.py` - `Food` dataclass fields, `_MACRO_USDA_IDS` keys, `_build_food()` kwargs
- `solver.py` - `SolvedIngredient`, `Solution`, `Targets` dataclass fields + all usages
- `api.py` - Pydantic models (TargetsRequest, SolvedIngredientResponse, SolveResponse, FoodResponse)
- `tests/test_solver.py` - Assertion field names

**Frontend (5 files):**
- `api.ts` - TypeScript interfaces (Food, SolvedIngredient, SolveTargets, SolveResponse)
- `contributions.ts` - Property access on solution and ingredient objects
- `+page.svelte` - Derived values, display, segment calculations
- `IngredientRow.svelte` - Ingredient property access
- `AddIngredientModal.svelte` - Food property display

**Not affected:** `foods.json` (uses USDA IDs), `build_food_db.py` (writes USDA IDs), `MacroPcts` interface (internal shorthand).

## Architecture

### Frontend Aggregates, Solver Unchanged

The frontend sums all pinned meal nutrients and:
1. Subtracts pinned macros from daily targets before sending to solver
2. Sends aggregated pinned micros in the solve request

The solver remains a pure "solve for these targets" function.

### Frontend State

```typescript
let pinnedMeals = $state<PinnedMeal[]>([]);

let pinnedTotals = $derived.by(() => {
  const totals: Record<string, number> = {};
  for (const meal of pinnedMeals) {
    for (const [key, val] of Object.entries(meal.nutrients)) {
      totals[key] = (totals[key] ?? 0) + val;
    }
  }
  return totals;
});

let mealCal = $derived(dailyCal - (pinnedTotals.calories_kcal ?? 0));
let mealPro = $derived(dailyPro - (pinnedTotals.protein_g ?? 0));
let mealFiberMin = $derived(dailyFiberMin - (pinnedTotals.fiber_g ?? 0));
```

### Zero Pinned Meals

When `pinnedMeals` is empty, `pinnedTotals` is `{}`. All `?? 0` fallbacks make the full daily target go to the solver. "Day" row matches "Meal" row. No pinned segments in breakdown bars. No special-casing needed.

### Solve Request Changes

```python
class SolveRequest(BaseModel):
    # ... existing fields ...
    pinned_micros: dict[str, float] = {}  # aggregated micro totals
```

Frontend filters `pinnedTotals` to micro keys only before sending.

### Micro Result Changes

`MicroResult.smoothie` renamed to `MicroResult.pinned`. Backend computes from `req.pinned_micros` instead of hardcoded `SMOOTHIE_MICROS`.

## Backend Changes

### `dri.py`
- Delete `SMOOTHIE_MICROS` dict
- Delete `remaining_targets()` helper

### `api.py`
- Add `pinned_micros: dict[str, float] = {}` to `SolveRequest`
- Rename `MicroResult.smoothie` to `MicroResult.pinned`
- Replace `SMOOTHIE_MICROS.get(key, 0.0)` with `req.pinned_micros.get(key, 0.0)`
- Compute remaining targets inline: `max(0, dri - pinned)`

### `solver.py`
No changes (receives pre-computed targets).

## UI

### Main Page - Pinned Meals Section

Collapsible section between config panel and ingredients table:

```
▸ Pinned Meals (2)                              [+ Add]
  Morning Smoothie   720 kcal · 30g pro · 15g fat · 80g carb · 14g fib
  Protein Bar        250 kcal · 20g pro · 8g fat · 30g carb · 3g fib
```

Each row clickable to edit (opens modal). Delete button (x) on each row. Small export icon per row to download as JSON.

### PinnedMealModal.svelte (new component)

Modal for add/edit with structured form:

- **Name** text input
- **Macros** section: 5 required number inputs (cal, pro, fat, carb, fiber) in a compact row
- **Micros** section: collapsible, grouped by category (Major Minerals, B-Vitamins + C, Fat-Soluble Vitamins), all optional
- **Import JSON** button: file picker, parses and fills form, validates against schema
- **Save / Cancel** buttons
- Works for both add (blank) and edit (pre-filled)

### Macro Displays with Pinned Meals

- "Meal" row: solver output (unchanged)
- "Day" row: `solution.meal_*` + `pinnedTotals.*`
- Macro % bar: includes pinned meal macros in the calculation
- `macroStackedSegments()`: adds "Pinned" segment (gray `#94a3b8`) using pinned macro totals
- `microStackedSegments()`: adds "Pinned" segment using `MicroResult.pinned`

### Persistence

`pinnedMeals` array saved/loaded in localStorage. Old `smoothieCal/Pro/Fiber` keys ignored on load (clean break).

## Migration

No auto-migration. Export current smoothie data to `docs/smoothie-default.json` with all macro and micro values from `SMOOTHIE_MICROS`. Fat and carbs omitted (unknown). User imports this file after the feature ships.

## Implementation Order

1. Macro field rename (mechanical, verified by `bun run check` + `pytest`)
2. JSON schema file
3. Backend changes (delete smoothie, add `pinned_micros`, rename `smoothie` -> `pinned`)
4. Frontend data model + state + aggregation
5. `PinnedMealModal.svelte` component
6. Main page pinned meals section
7. Update macro/micro displays with pinned segments
8. Smoothie export JSON file
9. Verify zero-pinned-meals state
