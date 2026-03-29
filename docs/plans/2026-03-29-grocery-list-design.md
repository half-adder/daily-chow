# Grocery List Feature Design

## Goal

Enable weekly grocery shopping by converting solved meal plans into a grocery list with sensible units, scaled for N days.

## Data Pipeline: Grocery Portions

Add a new step to `build_food_db.py` that assigns each food a grocery-friendly portion unit.

### Extraction

- Pull `foodPortions` from SR Legacy data for each food (keyed by NDB number, same merge logic already used for nutrients).
- Each SR Legacy portion has a free-text `modifier` field (e.g., "cup", "breast", "fillet", "oz") and a `gramWeight`.
- Foundation Foods portions are mostly RACC (regulatory serving sizes), not useful. SR Legacy has 96.7% coverage with practical units.

### Haiku Cleanup

- Send batches of foods + their available USDA portions through Claude Haiku (via `claude -p --model haiku`, same pattern as name/commonness/group generation).
- Prompt asks Haiku to pick the single best grocery-shopping unit from the available portions and clean up the modifier text (e.g., "breast, skin not eaten" becomes "breast").
- If none of the portions are grocery-relevant, return null. Food stays in grams.
- Cache results in `portion_cache.json` (same pattern as other caches).

### Storage

- Add optional `portion` field to each food in `foods.json`: `{"unit": "breast", "g": 174}`.
- Foods without a good portion omit the field.

## Frontend Data Model

Add to the `Food` type in `api.ts`:

```typescript
portion?: { unit: string; g: number }
```

Parse it during food loading alongside existing fields.

## Grocery List Logic

When the user opens the grocery list:

1. Read solved ingredients from the current solution (each has food name, grams, category).
2. Multiply grams by the user-specified number of days.
3. Convert to grocery units: if the food has a `portion`, divide total grams by `portion.g` and round to a sensible display quantity. If no portion, display in grams (or kg if over 1000g).
4. Group items by USDA `category` (already on every food).
5. Display in a modal with a "Copy to clipboard" button.

## UI Components

### Days Input

- Small number input in the header/toolbar area, labeled "Days".
- Default value: 7.

### Grocery List Button

- Button in the toolbar area (shopping cart icon or similar).
- Only enabled when there's a valid solution.

### Grocery List Modal

- Header: "Grocery List (N days)"
- Sections grouped by category, each with a text header
- Each item: food name, quantity in grocery units, grams in parentheses
- "Copy to clipboard" button at the top
- Clipboard format is plain text:

```
Grocery List (7 days)

Poultry Products
  Chicken breast - 4 breasts (696g)

Dairy and Egg Products
  Whole milk - 7 cups (1.7L)
  Eggs - 14 eggs (700g)

Vegetables
  Spinach - 10 cups (300g)
```

## Implementation Scope

1. **Build pipeline**: Add portion extraction + Haiku cleanup step to `build_food_db.py`
2. **Data model**: Add optional `portion` to `Food` type, parse it in `api.ts`
3. **UI**: Days input, grocery list button, modal with grouped/converted list + copy to clipboard
