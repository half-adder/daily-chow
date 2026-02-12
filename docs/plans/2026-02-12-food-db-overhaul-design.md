# Food Database Overhaul Design

## Goal

Replace the hand-curated 60-food registry with the full USDA FoodData Central catalog (~7,800 foods), making the raw USDA JSON files the single source of truth for all nutrition data.

## Data Sources

- **Foundation Foods** (365 foods, Dec 2025): Higher-quality analytical data with median/min/max per nutrient. 6.5MB raw JSON.
- **SR Legacy** (7,793 foods, Apr 2018): Broader coverage, ~83 nutrients per food. 201MB raw JSON.

Merge strategy: index both by NDB number. When a food exists in both, prefer Foundation data. Result: ~7,800 unique foods.

## Build-Time Processing

A new script `scripts/build_food_db.py`:

1. Reads both raw USDA JSON files (passed as args).
2. Merges by NDB number, Foundation preferred.
3. For each food, extracts: `fdcId`, `ndbNumber`, `description`, `category` (from `foodCategory.description`), and nutrient values for the ~25 IDs we track (5 macros + 20 micros). All values per 100g.
4. Batches all USDA descriptions through Claude Haiku (~50 per prompt, ~156 calls) to generate `short_name` and `subtitle` fields. Caches results so re-runs only process new/changed foods.
5. Outputs `src/daily_chow/data/foods.json` (~3-4MB). This file is committed to the repo.

The raw USDA files are not committed or shipped. The build script runs once when USDA data updates.

## Simplified Data Model

The two-dataclass system (`FoodEntry` -> `Food`) collapses to a single `Food` loaded directly from the trimmed JSON:

```python
@dataclass(frozen=True, slots=True)
class Food:
    fdc_id: int
    name: str              # Haiku-generated short name, e.g. "Avocado oil"
    subtitle: str          # Haiku-generated qualifier, e.g. "raw, enriched"
    usda_description: str  # original USDA description for searchability
    category: str          # USDA category, e.g. "Cereal Grains and Pasta"
    cal_per_100g: float
    protein_per_100g: float
    fat_per_100g: float
    carbs_per_100g: float
    fiber_per_100g: float
    micros: dict[str, float]  # canonical key -> value per 100g
```

Eliminated: `FoodEntry`, `FOOD_ENTRIES`, all `manual_*` fallback fields, `usda_fdc_id` indirection.

## Loading

A single `load_foods() -> dict[int, Food]` in `food_db.py` reads `foods.json`. No more `usda.py` join layer.

`GET /foods` returns all ~7,800 foods. At ~500 bytes/food that's ~4MB JSON, gzips to ~1MB. Fine for a personal app.

## Solver Changes

- **Ingredient keys:** Change from string slugs to FDC IDs (int).
- **"Minimize oil":** Match on USDA category `"Fats and Oils"` instead of `"oils_fats"`.
- **Drop `MINIMIZE_RICE_DEVIATION`:** Remove from `Objective` enum. Only `MINIMIZE_OIL` and `MINIMIZE_TOTAL_GRAMS` remain.
- Everything else (constraints, scaling, blended micro penalty) unchanged.

## Frontend Changes

- **Add ingredient modal:** Searches ~7,800 foods instead of 60. Gap-score sorting still works.
- **Ingredient identification:** FDC ID (number) instead of string slugs. Affects the `ingredients` array, localStorage, and API requests.
- **Display:** Short name + subtitle replaces name + `unit_note`. Search matches against both `name` and `usda_description`.
- **localStorage migration:** Old slug-based state is discarded; falls back to default starter set.

## Default Starter Ingredients

A hardcoded list of FDC IDs in the frontend for first-visit defaults (similar to the current ~9 ingredients). All default to enabled, min=0, max=500g. localStorage overrides after first visit.

## What Stays Unchanged

- `dri.py`: 20 tracked micronutrients, DRI targets, smoothie offsets.
- Solver architecture: CP-SAT model, hard macro constraints, soft micro penalty, blended objective.
- Frontend layout and UX patterns (sliders, micro panel, impact visualization).

## Haiku Name Generation

Prompt structure (batched, ~50 foods per call):

```
For each USDA food description, generate a short display name and subtitle.
The name should be natural English (e.g. "Avocado oil" not "Oil, avocado").
The subtitle should contain key qualifiers (raw/cooked, variety, etc.).

Input: "Oil, avocado"
Output: { "name": "Avocado oil", "subtitle": "" }

Input: "Rice, white, long-grain, regular, raw, enriched"
Output: { "name": "White rice", "subtitle": "long-grain, raw" }
```

Results cached in a sidecar file (`data/name_cache.json`) keyed by FDC ID so incremental updates only process new foods.
