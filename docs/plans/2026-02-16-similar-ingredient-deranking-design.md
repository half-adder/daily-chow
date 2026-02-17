# Similar Ingredient De-ranking in Add Ingredient Modal

## Problem

When browsing the Add Ingredient modal, similar ingredients to those already in the plan are recommended prominently. For example, if "Egg" is in the plan, "Fried Egg" and "Scrambled Egg" appear near the top. Users want dissimilar ingredients surfaced first.

## Design

### Approach: Word-overlap similarity with browse-only de-ranking

**Scope:** `AddIngredientModal.svelte` only. No backend changes.

### Algorithm

1. Build a `Set<string>` of significant words (lowercased, length >= 3) from all existing plan ingredient names
2. In browse mode (empty search query), flag each candidate as `isSimilar` if any of its name words overlap with the plan words set
3. Sort non-similar items first (by commonness, then gap-fill), then similar items (same sub-sort)
4. When the user types a search query, skip de-ranking entirely — normal search ranking applies

### What counts as "similar"

Word-level overlap on the `name` field. Examples:
- Plan has "Egg" → "Fried Egg", "Egg White", "Scrambled Egg" are similar (share word "Egg")
- Plan has "Chicken Breast" → "Chicken Thigh", "Fried Chicken" are similar (share word "Chicken")
- "Eggplant" does NOT match "Egg" (single word, no overlap)
- "Milkfish" does NOT match "Milk" (single word, no overlap)

Words shorter than 3 characters are ignored (e.g., "1%", "2%").

### Behavior

- **Browse mode (no query):** Similar items de-ranked to bottom of list
- **Search mode (user typing):** No de-ranking, normal search ranking applies
- Similar items are still visible and selectable, just sorted lower

### Files changed

- `frontend/src/lib/components/AddIngredientModal.svelte` — add similarity computation and sort adjustment in the browse branch of `results`
