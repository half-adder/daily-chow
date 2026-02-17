# Export Feature Design

## Overview

Two export formats from a new `/api/export` endpoint:
- **Markdown** — plain text, suitable for pasting into notes/docs
- **PDF** — two-page document: nutrition dashboard + shopping checklist

Same-plan-scaled model: one optimized day plan multiplied by N days for the shopping list.

## Architecture

Backend (Python) generates both formats. The frontend sends the current solution data to a new API endpoint.

```
Frontend                          Backend
────────                          ───────
Export button click  ──POST──▸  /api/export
  { solution, foods,              ├─ format=md  → returns .md file
    pinnedMeals, profile,         └─ format=pdf → returns .pdf file
    numDays, config }                 Page 1: Nutrition dashboard
                                      Page 2: Shopping checklist
```

## PDF Structure

### Page 1 — Nutrition Dashboard (optional, toggled by user)

- Header: "Daily Chow — Meal Plan" with date and profile info
- **Daily Totals** box: calories, protein, fat, carbs, fiber
- **Ingredient Table**: name, weight (g/oz), calories, protein, fat, carbs, fiber per ingredient
- **Macro Breakdown Bars**: horizontal stacked bars (same colors as UI)
- **Micro Coverage Chart**: horizontal bars showing % DRI for all 20 micros

### Page 2 — Shopping List

- Header: "Shopping List — X days"
- Ingredients grouped by USDA category (produce, protein, grains, etc.)
- Each item: checkbox + name + total weight (g and oz/lbs)
- Quantities scaled by `numDays`
- Clean, minimal styling with plenty of whitespace

## Markdown Structure

```markdown
# Daily Chow — Meal Plan
Generated: 2026-02-17 | Profile: Male, 19-30 | 2000 kcal target

## Daily Totals
| Calories | Protein | Fat | Carbs | Fiber |
|----------|---------|-----|-------|-------|
| 2000     | 150g    | 67g | 200g  | 35g   |

## Ingredients
| Ingredient    | Weight | Cal | Pro | Fat | Carb | Fiber |
|---------------|--------|-----|-----|-----|------|-------|
| Chicken Breast| 200g   | 330 | 62g | 7g  | 0g   | 0g    |
| ...           |        |     |     |     |      |       |

## Shopping List (7 days)
### Produce
- [ ] Broccoli — 1.4 kg (3.1 lbs)
- [ ] Spinach — 700g (1.5 lbs)
### Protein
- [ ] Chicken Breast — 1.4 kg (3.1 lbs)
```

## Weight Conversion

Simple gram-based conversion:
- Always show grams
- Show oz for quantities < 1000g
- Show lbs for quantities >= 1000g (with one decimal)
- `1 oz = 28.35g`, `1 lb = 453.6g`

## Python Libraries

- **PDF generation**: `weasyprint` (HTML/CSS → PDF). Write the dashboard as styled HTML, render to PDF. Full CSS control for charts and layout.
- **Charts in PDF**: Render macro bars and micro bars as HTML/CSS elements (colored divs with percentage widths) — no matplotlib needed.

## API Endpoint

```python
POST /api/export
Body: {
  format: "md" | "pdf",
  include_dashboard: bool,      # Whether to include nutrition page
  num_days: int,                # For scaling shopping list (default 1)
  solution: SolveResponse,      # Current solver output
  foods: Food[],                # Food metadata for ingredients
  pinned_meals: PinnedMeal[],   # Fixed meals
  profile: { sex, age_group },  # For DRI context
  config: { daily_cal, ... }    # Plan configuration
}
Response: file download (application/pdf or text/markdown)
```

## Frontend UI

An "Export" button in the toolbar area. Clicking opens a small modal/popover with:
- Format toggle: Markdown / PDF
- Number of days: 1–14 (default 7)
- Include nutrition dashboard: checkbox (PDF only)
- "Export" button to trigger download
