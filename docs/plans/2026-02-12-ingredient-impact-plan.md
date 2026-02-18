# Ingredient Impact Visualization — Implementation Plan

## Step 1: Create `contributions.ts`

**File:** `frontend/src/lib/contributions.ts`

New utility module exporting:

- `INGREDIENT_COLORS: string[]` — palette of 15 distinguishable colors
- `assignColor(usedColors: string[]): string` — returns next unused color from palette
- `computeContributions(solution, foods)` — returns `Map<string, { macroPcts: {cal, pro, fat, carb, fiber}, micros: Record<string, {amount, driPct}> }>`
- `computeGapScore(foodKey, food, solution, microResults): number` — gap-filling score for add menu

No external deps, pure functions only.

## Step 2: Create `StackedBar.svelte`

**File:** `frontend/src/lib/components/StackedBar.svelte`

Reusable horizontal stacked bar. Props:
- `segments: { key: string; label: string; value: number; pct: number; color: string }[]`
- `height?: number` (default 20px)

Renders a flex row of colored segments sized by `pct`. Each segment shows a tooltip on hover with `label` and value. Segments below ~3% width show tooltip only (no inline text).

## Step 3: Add ingredient colors to state

**File:** `frontend/src/routes/+page.svelte`

- Add `color: string` to `IngredientEntry` interface
- Import `INGREDIENT_COLORS`, `assignColor` from contributions
- In default ingredient list and `addIngredient()`, assign a color
- In `loadState()`, backfill missing colors for existing saved state
- In `saveState()`, persist colors
- Pass `color` to `IngredientRow`

## Step 4: Expandable ingredient detail panel

**File:** `frontend/src/lib/components/IngredientRow.svelte`

- Add `color` prop
- Render color swatch (small dot) next to ingredient name
- Add `expanded` prop (bindable or callback-based)
- When expanded, render a detail panel below the grid row:
  - Left: horizontal bars for cal/pro/fat/carb/fiber showing this ingredient's % of meal total
  - Right: top micro contributions (>10% DRI), sorted descending
- Needs new props: `contributions` (this ingredient's computed data)

**File:** `frontend/src/routes/+page.svelte`

- Add `expandedIngredient: string | null` state
- Compute contributions (derived from solution + foods)
- Pass to IngredientRow, handle expand/collapse

## Step 5: Clickable macro summary breakdown

**File:** `frontend/src/routes/+page.svelte`

- Add `expandedMacro: boolean` state
- Make `.macro-bar` clickable (cursor pointer, onclick toggle)
- When expanded, render a panel below with three `StackedBar` components (calories, protein, fat), each segmented by ingredient using assigned colors
- Uses same contributions data from Step 4

## Step 6: Clickable micronutrient breakdown

**File:** `frontend/src/routes/+page.svelte`

- Add `expandedMicro: string | null` state
- Make each `.micro-row` clickable (not just the checkbox, but the whole row triggers expand; checkbox still toggles optimization)
- When a micro row is expanded, render a `StackedBar` below showing per-ingredient contribution to that nutrient
- Uses contributions data

## Step 7: Gap-filling sort in add ingredient modal

**File:** `frontend/src/lib/components/AddIngredientModal.svelte`

- Add new props: `solution` (SolveResponse | null), `microResults` (for DRI gaps)
- Import `computeGapScore` from contributions
- When no search query, sort by gap score descending instead of arbitrary order
- Show subtle indicator per food (e.g., small text "fills N gaps" or a mini bar)
- When search query is active, use existing text match sort (gap score as tiebreaker)

## Verification

After each step, check the dev server compiles cleanly (`0 errors` in terminal). After Steps 4-7, visually verify with Playwright snapshots.
