# Smarter Gap-Fill Heuristic Design

## Problem

The "fills N gaps" badge in the Add Ingredient modal is misleading. It uses a fixed 250g serving estimate and counts all gaps equally, regardless of severity. This causes two issues:

1. **Calorie-dense foods overestimated** — 250g of butter (1793 kcal) is unrealistic when the solver would only allocate ~30g
2. **Low-value gaps counted equally** — a food helping calcium at 95% scores the same as one helping vitamin K at 48%, but the solver's minimax strategy only cares about the worst gaps

## Design

### 1. Calorie-aware serving estimate

Replace the fixed `ESTIMATED_SERVING_G = 250` with a per-food estimate derived from actual plan data:

```
calorieShareG = mealCal / (numIngredients + 1) / (food.calories_kcal_per_100g / 100)
estimatedG = min(maxPerIngredient, calorieShareG)
```

- `mealCal`: meal calorie target (after subtracting pinned meals)
- `numIngredients`: count of existing plan ingredients (`existingKeys.size`)
- `maxPerIngredient`: user's configured max grams per ingredient
- Divides calorie budget evenly among ingredients, converts to grams for each food

### 2. Severity weighting in gap score (for sort ranking)

Weight each gap contribution in `computeGapScore` by how severe the deficiency is:

```
score += fillPct * (100 - mr.pct) / 100
```

Nutrient at 48% DRI gets weighted 0.52x, nutrient at 95% gets 0.05x. Aligns sort ranking with solver's minimax strategy (improve worst nutrient first).

### 3. `countGapsFilled` — calorie-aware only

Keep the simple >10% fill threshold for the displayed count, but use the calorie-aware serving estimate instead of fixed 250g. Severity weighting goes into the sort score only, not the badge count.

### Data flow

```
+page.svelte: passes mealCalories + maxPerIngredient to AddIngredientModal
  → AddIngredientModal: computes estimatedServingG per food
  → computeGapScore(food, microResults, estimatedServingG) — severity-weighted sort
  → countGapsFilled(food, microResults, estimatedServingG) — calorie-aware badge
```

### Files changed

- `frontend/src/lib/contributions.ts` — update `computeGapScore` and `countGapsFilled` to accept `estimatedServingG` parameter, add severity weighting to score
- `frontend/src/lib/components/AddIngredientModal.svelte` — compute per-food serving estimates, pass to functions
- `frontend/src/routes/+page.svelte` — pass `mealCalories` and `maxPerIngredient` props to modal
