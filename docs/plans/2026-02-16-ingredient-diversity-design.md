# Ingredient Diversity via L2 Regularization

**Date:** 2026-02-16
**Status:** Approved

## Problem

The solver sometimes assigns the vast majority of grams to a single ingredient (e.g. 500g rice, 20g everything else) because nothing in the objective penalizes concentration. Users want a more balanced plate.

## Approach: Sum-of-Squares Regularization

Add a new objective term that minimizes the sum of squared gram amounts across all ingredients: **minimize Σ(gram_i²)**.

This is minimized when grams are spread evenly (by convexity of x²). For example, with 600g total across 3 ingredients:
- 200/200/200 → sum = 120,000 (preferred)
- 500/50/50 → sum = 255,000 (penalized)

### Why not minimax?

Minimax (minimize the largest ingredient) only cares about the single biggest ingredient. It can't distinguish between 300/100/100 and 300/200/0. L2 regularization penalizes all unevenness proportionally.

## Design

### Solver (`solver.py`)

**New priority constant:**
```python
PRIORITY_INGREDIENT_DIVERSITY = "ingredient_diversity"
DEFAULT_PRIORITIES = [
    PRIORITY_MICROS,
    PRIORITY_MACRO_RATIO,
    PRIORITY_INGREDIENT_DIVERSITY,
    PRIORITY_TOTAL_WEIGHT,
]
```

**Position in lex chain:** Below micros and macro ratio (nutrition targets matter more), above total weight (evenness matters more than minimizing total grams).

**Objective term implementation:**
1. For each ingredient, compute `sq_i = gram_vars[i]²` via `model.add_multiplication_equality`
2. Sum them: `sum_sq = Σ sq_i`
3. Normalize to `[0, PCT_SCALE]` for consistency: `pct_var * max_sum_sq >= sum_sq * PCT_SCALE`
4. Add `pct_var` to the lex chain

**Overflow safety:** Max sum of squares for 15 ingredients at 500g each = 3.75M. Normalized to PCT_SCALE (10,000), this keeps magnitudes safe in the lex weight chain. The existing int64 overflow assertion catches edge cases.

### API (`api.py`)

No changes needed. The `priorities` list parameter already accepts arbitrary priority strings — the new `"ingredient_diversity"` constant is just a new valid value.

### Frontend (`+page.svelte`)

1. Add `'ingredient_diversity'` to the default priorities array
2. Add label mapping: `'ingredient_diversity'` → `"Ingredient diversity"`
3. Add migration logic to backfill the new priority into old saved states (same pattern as the existing `macro_ratio` migration)

No new UI controls — it appears as a new reorderable item in the existing priority list.

## Testing

- **Evenness test:** With diversity enabled, solver prefers 200/200/200 over 500/50/50 given the same calorie constraint
- **Priority ordering test:** Enabling diversity doesn't degrade micronutrient coverage (micros take priority)
- **Migration test:** Old saved states without `ingredient_diversity` get it backfilled correctly
