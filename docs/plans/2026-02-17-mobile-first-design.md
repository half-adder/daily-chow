# Mobile-First Redesign

## Breakpoints

- `>1200px`: Two-column desktop layout (unchanged)
- `≤1200px`: Single-column stack (existing, unchanged)
- `≤640px`: Mobile-specific redesign (new)

No changes to desktop or tablet layouts.

## 1. Constraints Area (≤640px)

Each macro constraint row becomes a single horizontal line:

```
Protein  ‹ · [≥] ≤ ›  🔒  [160] g
```

- **Horizontal wheel** replaces the vertical wheel — same 3-item track (prev, current, next) but laid out left-to-right
- Horizontal fade mask on left/right edges (CSS `mask-image` gradient)
- `translateX` animation on cycle instead of `translateY`
- Tap cycles forward through modes (`≥ ≤ = ·`)
- Lock icon and gram input remain inline
- Sex / Age / Max per ingredient on one compact row

Target: cut constraints section from ~600px to ~300px height.

## 2. Ingredient Rows (≤640px)

Two-line compact rows with always-visible sliders:

```
☑ White Rice  long grain, unenriched, raw    100g  ×
  ──────────────────●──────── 0–100
```

**Line 1:** Checkbox, ingredient name, subtitle (de-emphasized — smaller font, lighter color, inline), solved amount, delete button. Truncate with ellipsis on overflow.

**Line 2:** Full-width dual-range slider with min–max labels.

**Tap to expand** reveals detail panel:
- Exact min/max number inputs
- kcal / protein breakdown

"Add ingredient" button stays full-width at the bottom.

## 3. Sticky Bottom Bar (≤640px)

Fixed bar at viewport bottom replacing the stacked right sidebar:

```
┌─────────────────────────────────────┐
│  3450 kcal  160g pro  40g fib  ✓   │
└─────────────────────────────────────┘
```

- Shows: calories, protein, fiber, solve status (✓ OPTIMAL / ⚠ INFEASIBLE)
- Tap to expand a slide-up panel with:
  - Meal/Day totals
  - Macro ratio bar (carb/pro/fat %)
  - Full micronutrient breakdown
- Panel is scrollable and dismissible (tap outside or swipe down)

## 4. Unchanged on Mobile

- Header (title + theme toggle)
- Pinned Meals section
- Macro target bar
- Solve priorities list

These already work acceptably at mobile widths.
