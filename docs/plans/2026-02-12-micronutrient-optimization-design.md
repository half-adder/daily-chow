# Micronutrient Optimization Design

## Overview

Add micronutrient tracking and soft optimization to Daily Chow. The solver will
attempt to maximize micronutrient coverage (% of DRI met) as a secondary
objective, while keeping existing hard constraints (calories, protein, fiber)
unchanged. All nutrition data sourced from USDA FoodData Central Foundation
Foods at runtime.

## Decisions

- **Data source**: USDA FoodData Central Foundation Foods JSON, loaded at runtime
- **Nutrient set**: 20 micronutrients across 3 tiers
- **DRI targets**: Vary by sex (M/F) and age group (19-30, 31-50, 51-70, 71+)
- **Smoothie offset**: Smoothie micronutrient contribution subtracted from DRI
  before solving, same pattern as existing macro offsets
- **Solver approach**: Soft objective (penalty for shortfall), not hard constraints
- **UI controls**: Per-nutrient checkboxes with group-level toggle, collapsible report

## 20 Tracked Micronutrients

### Tier 1 — Major Minerals (excellent USDA coverage, 335-353/365 foods)

| Key | USDA ID | Unit | Name |
|-----|---------|------|------|
| `calcium_mg` | 1087 | mg | Calcium |
| `iron_mg` | 1089 | mg | Iron |
| `magnesium_mg` | 1090 | mg | Magnesium |
| `phosphorus_mg` | 1091 | mg | Phosphorus |
| `potassium_mg` | 1092 | mg | Potassium |
| `zinc_mg` | 1095 | mg | Zinc |
| `copper_mg` | 1098 | mg | Copper |
| `manganese_mg` | 1101 | mg | Manganese |
| `selenium_mcg` | 1103 | mcg | Selenium |

### Tier 2 — B-Vitamins + C (moderate coverage, 110-199/365 foods)

| Key | USDA ID | Unit | Name |
|-----|---------|------|------|
| `vitamin_c_mg` | 1162 | mg | Vitamin C |
| `thiamin_mg` | 1165 | mg | Thiamin (B1) |
| `riboflavin_mg` | 1166 | mg | Riboflavin (B2) |
| `niacin_mg` | 1167 | mg | Niacin (B3) |
| `vitamin_b6_mg` | 1175 | mg | Vitamin B-6 |
| `folate_mcg` | 1177 | mcg | Folate |
| `vitamin_b12_mcg` | 1178 | mcg | Vitamin B-12 |

### Tier 3 — Fat-soluble Vitamins (sparse coverage, 51-75/365 foods)

| Key | USDA ID | Unit | Name |
|-----|---------|------|------|
| `vitamin_a_mcg` | 1106 | mcg | Vitamin A (RAE) |
| `vitamin_d_mcg` | 1114 | mcg | Vitamin D |
| `vitamin_e_mg` | 1109 | mg | Vitamin E |
| `vitamin_k_mcg` | 1185 | mcg | Vitamin K |

## Architecture

### Data Layer

**`food_db.py`** — lightweight mapping file:

```python
@dataclass(frozen=True, slots=True)
class FoodEntry:
    key: str
    name: str           # our display name
    usda_fdc_id: int    # links to USDA JSON
    category: str       # "protein", "grains", "vegetables", etc.
    unit_note: str      # "1 cup ~ 185g"
    default_min: int
    default_max: int

FOOD_ENTRIES: dict[str, FoodEntry] = {
    "chicken_breast": FoodEntry("chicken_breast", "Chicken Breast", 2646170, ...),
    "white_rice": FoodEntry("white_rice", "White Rice", 2512381, ...),
    # ... ~60 entries
}
```

**`usda.py`** — runtime loader:

- Loads trimmed USDA JSON from `src/daily_chow/data/usda_foundation.json`
- Joins USDA nutrition data with our `FoodEntry` mappings
- Builds `Food` objects with both macros and micros from USDA data
- Maps USDA nutrient IDs to canonical keys (e.g. `1087` -> `calcium_mg`)
- Loaded once at startup, cached

**`Food` dataclass**:

```python
@dataclass(frozen=True, slots=True)
class Food:
    name: str
    unit_note: str
    cal_per_100g: float
    protein_per_100g: float
    fat_per_100g: float
    carbs_per_100g: float
    fiber_per_100g: float
    category: str
    default_min: int
    default_max: int
    micros: dict[str, float]  # nutrient_key -> amount per 100g
```

**Trimmed USDA JSON** (`src/daily_chow/data/usda_foundation.json`):

```json
{
  "747447": {
    "description": "Broccoli, raw",
    "nutrients": {
      "1087": 46.0,
      "1089": 0.69,
      "2047": 31.0
    }
  }
}
```

Flattened from the full USDA file. Keyed by fdcId, nutrients keyed by USDA
nutrient ID. Only includes the ~25 nutrients we use (macros + 20 micros).
Approximately 200KB.

### DRI Targets (`dri.py`)

Lookup table indexed by `(Sex, AgeGroup)` -> `dict[nutrient_key, daily_target]`.

```python
class Sex(Enum):
    MALE = "male"
    FEMALE = "female"

class AgeGroup(Enum):
    AGE_19_30 = "19-30"
    AGE_31_50 = "31-50"
    AGE_51_70 = "51-70"
    AGE_71_PLUS = "71+"
```

8 combinations total (2 sexes x 4 age groups).

**Smoothie offsets** — hardcoded `SMOOTHIE_MICROS` dict:

| Nutrient | Smoothie contribution |
|---|---|
| `calcium_mg` | 659 |
| `iron_mg` | 3.1 |
| `magnesium_mg` | 151.6 |
| `phosphorus_mg` | 696.4 |
| `potassium_mg` | 1160.7 |
| `zinc_mg` | 3.4 |
| `copper_mg` | 0.6 |
| `manganese_mg` | 1.9 |
| `selenium_mcg` | 40.9 |
| `vitamin_c_mg` | 149.6 |
| `thiamin_mg` | 0.4 |
| `riboflavin_mg` | 1.0 |
| `niacin_mg` | 3.3 |
| `vitamin_b6_mg` | 0.4 |
| `folate_mcg` | 97.7 |
| `vitamin_b12_mcg` | 1.9 |
| `vitamin_a_mcg` | 292 |
| `vitamin_d_mcg` | 3.2 |
| `vitamin_e_mg` | 2.4 |
| `vitamin_k_mcg` | 46.3 |

Remaining target for solver: `max(0, DRI[nutrient] - SMOOTHIE_MICROS[nutrient])`

### Solver Changes

New optional parameter `micro_targets: dict[str, float]` — only includes
nutrients the user has checked for optimization.

Objective function becomes:

```
minimize(
    primary_objective * W_primary
    + micro_penalty * W_micro
    + total_grams * W_tiebreaker
)
```

Where `micro_penalty` = sum of normalized shortfalls:

```python
for nutrient_key, target in micro_targets.items():
    coeff = scaled_micro_coeff(ing, nutrient_key)  # per-gram, integer-scaled
    total = sum(coeff[k] * gram_vars[k] for k in gram_vars)

    # shortfall = max(0, target_scaled - total), normalized to % DRI
    shortfall = model.new_int_var(0, target_scaled, f"{nutrient_key}_shortfall")
    diff = target_scaled - total
    model.add_max_equality(shortfall, [diff, model.new_constant(0)])

    # normalize by target so each nutrient contributes 0-100% penalty
    micro_penalty += shortfall * NORMALIZE_FACTOR / target_scaled
```

Weight hierarchy: `W_primary >> W_micro >> W_tiebreaker`

Existing hard constraints (calories, protein, fiber) are unchanged.

### API Changes

**Request** — new fields on `SolveRequest`:

```python
sex: str = "male"
age_group: str = "19-30"
optimize_nutrients: list[str] = []  # list of nutrient keys to optimize
```

**Response** — new field on `SolveResponse`:

```python
micros: dict[str, MicroResult]  # all 20 nutrients, always reported

class MicroResult(BaseModel):
    total: float        # amount from the meal
    smoothie: float     # amount from smoothie
    dri: float          # full daily target
    remaining: float    # max(0, dri - smoothie)
    pct: float          # (total + smoothie) / dri * 100
    optimized: bool     # whether this was in optimize_nutrients
```

The `/foods` endpoint also returns `micros` per food.

### Frontend UI

**Profile selector** — two dropdowns (Sex, Age) in the targets section. Stored
in localStorage.

**Micronutrient report** — collapsible section below the macro totals bar:

```
> Micronutrients

  [x] Major Minerals
      [x] Calcium    ||||||||....  72%   341 / 475 mg
      [x] Iron       ||||||......  58%   2.8 / 4.9 mg
      [ ] Sodium     ||||||||||||  100%  already met
      ...

  [x] B-Vitamins + C + Selenium
      [x] Thiamin    ||||||||||..  90%   0.7 / 0.8 mg
      ...

  [ ] Fat-soluble + B12
      [ ] Vitamin A  |||.........  28%   170 / 608 mcg
      [ ] Vitamin D  ||..........  15%   1.8 / 11.8 mcg
      ...
```

- Group-level checkbox toggles all nutrients in group
- Individual checkboxes for fine-tuning
- Indeterminate state when group is partially checked
- Progress bar colors: green >= 80%, amber 50-80%, red < 50%
- Always shows all 20 nutrients; unchecked ones dimmed
- Checking/unchecking any nutrient re-solves

## Data Pipeline

**One-time `scripts/match_usda.py`**:

1. Fuzzy-matches our ~60 food names against 365 USDA descriptions
2. Outputs proposed `usda_fdc_id` mapping for human review
3. After hand-correction, mapping committed to `food_db.py`

**One-time `scripts/trim_usda.py`**:

1. Reads full USDA JSON (~20-50MB)
2. Extracts only the ~25 nutrients we need per food
3. Outputs trimmed `src/daily_chow/data/usda_foundation.json` (~200KB)

Neither script runs at runtime. Only needed when adding foods or updating
USDA data.

## Implementation Order

1. `scripts/trim_usda.py` — generate trimmed USDA JSON
2. `scripts/match_usda.py` — map our foods to USDA fdcIds
3. Refactor `food_db.py` to `FoodEntry` with `usda_fdc_id`
4. New `usda.py` loader (builds `Food` objects from USDA data)
5. New `dri.py` (DRI tables + smoothie offsets)
6. Solver changes (soft micro penalty in objective)
7. API changes (new request/response fields)
8. Frontend: profile selector + micronutrient report with checkboxes
