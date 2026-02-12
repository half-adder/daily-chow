# Ingredient Impact Visualization

## Overview

Visualize how much each ingredient contributes to the solution across macros and micronutrients. Four interconnected features:

1. Expandable ingredient detail panels
2. Clickable macro summary with per-ingredient stacked bars
3. Clickable micronutrient bars with per-ingredient breakdown
4. Gap-filling sort in the add ingredient menu

## Data Foundation

No API changes needed. All contribution data is computable client-side from the existing solve response + food database:

- **Macro %**: `ingredient.calories / totalMealCalories` (same pattern for protein, fat, carbs, fiber)
- **Micro contribution**: `food.micros[key] * ingredient.grams / 100` gives absolute amount; divide by DRI for % of daily target
- **Gap-filling score**: For each candidate food, estimate contribution at `(default_min + default_max) / 2` grams. Sum `min(contribution / remainingGap, 1.0)` across all nutrients below 100% DRI.

A new `contributions.ts` module exports:
- `computeContributions(solveResult, foods)` — per-ingredient macro % and micro absolute/% values
- `computeGapScore(food, solveResult, microResults)` — gap-filling score for add menu sort

## Ingredient Colors

Each ingredient gets a color assigned from a 15-color palette when added, stored in the ingredient state alongside minG/maxG/enabled. The color appears as a swatch in the ingredient row and is reused in all stacked bar charts for consistency. Removed ingredients free their color for reuse.

## Expandable Ingredient Detail Panel

Click an ingredient row to expand a detail panel below it. Only one row expands at a time.

**Left — Macro contribution:** Horizontal bars showing what % of the meal total this ingredient provides (calories, protein, fat, carbs, fiber). Colored per the existing macro color scheme.

**Right — Top micro contributions:** Only nutrients where this ingredient contributes >10% of DRI, sorted descending. Keeps the panel scannable.

## Clickable Macro Summary Breakdown

The existing `carb X% / pro Y% / fat Z%` summary bar becomes clickable. Clicking expands a panel with three stacked horizontal bars (calories, protein, fat), each segmented by ingredient using the ingredient color palette. Hovering a segment shows a tooltip with ingredient name and value. Click again to collapse.

## Clickable Micronutrient Breakdown

Each nutrient row in the micronutrient report becomes clickable. Clicking expands a stacked bar showing which ingredients contribute how much, using the same ingredient colors. Only one nutrient detail open at a time (independent of other expandable panels).

## Gap-Filling Sort in Add Menu

When opening the add ingredient picker, candidates are sorted by gap-filling score — how much they'd help close nutritional gaps in the current solution. Foods already in the ingredient list are pushed to the bottom. A subtle indicator (e.g., "fills N gaps") explains the ranking.

## New/Modified Components

| Component | Change |
|---|---|
| `IngredientRow.svelte` | Add color swatch, click-to-expand detail panel |
| `StackedBar.svelte` | New reusable stacked bar with colored segments + hover tooltips |
| Macro summary section | Make clickable, add expandable stacked breakdown |
| Micronutrient report rows | Make clickable, add expandable stacked breakdown |
| Add ingredient menu | Sort by gap-filling score |
| `contributions.ts` | New module for all contribution/score computations |

## New State

- `color: string` on each ingredient (assigned from palette on add)
- `expandedIngredient: string | null` — which ingredient row is expanded
- `expandedMacro: boolean` — whether macro summary breakdown is open
- `expandedMicro: string | null` — which micronutrient row is expanded
