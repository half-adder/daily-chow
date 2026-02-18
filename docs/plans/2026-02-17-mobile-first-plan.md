# Mobile-First Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Daily Chow fully usable on phones (≤640px) with compact constraints, two-line ingredient rows with always-visible sliders, and a sticky bottom nutrition bar.

**Architecture:** Pure CSS media queries at `≤640px` breakpoint. No new dependencies. Three changes: (1) horizontal wheel variant in MacroConstraintWheel + compact constraint layout, (2) mobile layout in IngredientRow, (3) new StickyBottomBar component. All gated behind `@media (max-width: 640px)`.

**Tech Stack:** SvelteKit, Svelte 5 runes, vanilla CSS with custom properties, bun

---

### Task 1: MacroConstraintWheel — Horizontal Mode for Mobile

**Files:**
- Modify: `frontend/src/lib/components/MacroConstraintWheel.svelte`

The current wheel is vertical (60px tall, 24px wide). On mobile, rotate it to horizontal (24px tall, 60px wide) using a CSS media query. The component already renders 3 items (prev, current, next) in a flex column with translateY animation.

**Step 1: Add mobile CSS to MacroConstraintWheel**

Add this `@media` block inside the existing `<style>` section at the end of `MacroConstraintWheel.svelte`:

```css
@media (max-width: 640px) {
    .wheel-container {
        width: 60px;
        height: 24px;
        -webkit-mask-image: linear-gradient(to right, transparent 0%, black 25%, black 75%, transparent 100%);
        mask-image: linear-gradient(to right, transparent 0%, black 25%, black 75%, transparent 100%);
    }

    .wheel-track {
        flex-direction: row;
    }

    .wheel-item {
        width: 20px;
        height: 24px;
    }
}
```

**Step 2: Switch animation axis on mobile**

The `cycleMode()` function in the `<script>` currently hardcodes `translateY(20px)`. We need to detect mobile and use `translateX(-20px)` instead (negative because horizontal scrolls left on cycle-forward).

Add a reactive state for detecting mobile:

```ts
let isMobile = $state(false);

function checkMobile() {
    isMobile = window.matchMedia('(max-width: 640px)').matches;
}
```

In `onMount` equivalent (use `$effect` with cleanup):

```ts
$effect(() => {
    checkMobile();
    const mql = window.matchMedia('(max-width: 640px)');
    const handler = () => checkMobile();
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
});
```

Update `cycleMode()`:
- Replace `trackEl.style.transform = 'translateY(20px)'` with:
  `trackEl.style.transform = isMobile ? 'translateX(-20px)' : 'translateY(20px)'`

**Step 3: Verify visually**

Open browser at 375×812 (iPhone SE), confirm:
- Wheel shows 3 symbols horizontally with fade mask on edges
- Tapping cycles with smooth horizontal slide animation
- Each constraint row fits on one line

**Step 4: Commit**

```bash
git add frontend/src/lib/components/MacroConstraintWheel.svelte
git commit -m "feat: horizontal constraint wheel on mobile (≤640px)"
```

---

### Task 2: Compact Constraints Layout on Mobile

**Files:**
- Modify: `frontend/src/routes/+page.svelte` (CSS only, lines 1017–1200)

**Step 1: Add mobile CSS for targets section**

Add at the end of the `<style>` block in `+page.svelte`, before the closing `</style>`:

```css
@media (max-width: 640px) {
    .app {
        padding: 16px 12px;
    }

    h1 {
        font-size: 22px;
    }

    .targets-section {
        padding: 12px 14px;
    }

    .targets-row {
        flex-direction: column;
        gap: 8px;
    }

    .cal-row {
        width: 100%;
    }

    .cal-row-symbol {
        height: 24px;
    }

    .target-group {
        flex-direction: row;
        align-items: center;
        gap: 8px;
    }

    .target-group label {
        min-width: 32px;
    }

    .priority-group {
        flex-direction: column;
        min-width: 0;
    }
}
```

**Step 2: Verify visually**

At 375×812: constraints section should be noticeably shorter. Each macro row is a single horizontal line. Sex/Age/Max are inline.

**Step 3: Commit**

```bash
git add frontend/src/routes/+page.svelte
git commit -m "feat: compact constraints layout on mobile (≤640px)"
```

---

### Task 3: Mobile Ingredient Rows

**Files:**
- Modify: `frontend/src/lib/components/IngredientRow.svelte`

The current grid is `32px 180px 64px 1fr 64px 72px 100px 32px` (8 columns). On mobile, switch to a two-line stacked layout.

**Step 1: Add mobile CSS to IngredientRow**

Add at end of `<style>` in `IngredientRow.svelte`:

```css
@media (max-width: 640px) {
    .ingredient-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 4px 8px;
        padding: 10px 12px 4px;
    }

    .checkbox-cell {
        flex-shrink: 0;
    }

    .name-cell {
        flex: 1;
        min-width: 0;
        flex-direction: row;
        align-items: baseline;
        gap: 6px;
    }

    .unit-note {
        padding-left: 0;
        font-size: 10px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .bound-input {
        display: none;
    }

    .solved-cell {
        flex-shrink: 0;
    }

    .macros-cell {
        display: none;
    }

    .remove-btn {
        flex-shrink: 0;
    }

    .slider-cell {
        width: 100%;
        order: 10;
        padding: 0 0 6px 32px;
    }

    .detail-panel {
        grid-template-columns: 1fr;
        padding: 12px 12px 16px 40px;
    }
}
```

This makes line 1 = checkbox + name (with inline subtitle) + solved amount + × button, and line 2 = full-width slider (indented to align under name). The min/max inputs and kcal/pro are hidden in the default view (available in the tap-to-expand detail panel).

**Step 2: Add min/max inputs to the detail panel for mobile**

Currently the detail panel only shows macro/micro contribution bars. On mobile, we need to also show min/max inputs there since they're hidden from the main row. Add min/max input fields at the top of the detail panel markup (inside the `{#if expanded && contribution && solved}` block, before `detail-macros`):

```svelte
<div class="detail-bounds">
    <label>
        <span>Min</span>
        <input type="number" class="bound-input-mobile" value={minG} onchange={handleMinInput} min="0" />
        <span class="unit">g</span>
    </label>
    <label>
        <span>Max</span>
        <input type="number" class="bound-input-mobile" value={maxG} onchange={handleMaxInput} min="0" />
        <span class="unit">g</span>
    </label>
    <div class="detail-kcal-pro">
        <span class="macro-cal">{Math.round(solved.calories_kcal)} kcal</span>
        <span class="macro-sep">/</span>
        <span class="macro-pro">{Math.round(solved.protein_g)}g pro</span>
    </div>
</div>
```

Add corresponding CSS inside the `@media (max-width: 640px)` block:

```css
.detail-bounds {
    display: flex;
    align-items: center;
    gap: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 12px;
}

.detail-bounds label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: var(--text-muted);
}

.bound-input-mobile {
    width: 56px;
    padding: 4px 6px;
    background: var(--bg-input);
    border: 1px solid var(--border-input);
    border-radius: 4px;
    color: var(--text-secondary);
    font-size: 13px;
    text-align: right;
    -moz-appearance: textfield;
}

.bound-input-mobile::-webkit-inner-spin-button,
.bound-input-mobile::-webkit-outer-spin-button {
    -webkit-appearance: none;
}

.detail-kcal-pro {
    margin-left: auto;
    font-size: 13px;
    font-variant-numeric: tabular-nums;
}
```

And on desktop, hide the mobile bounds row:

```css
.detail-bounds {
    display: none;
}
```
(Put this _outside_ the `@media` block so it applies by default, and the `@media` block overrides with `display: flex`.)

**Step 3: Verify visually**

At 375×812:
- Each ingredient is two lines: name row + slider
- Subtitle appears inline in lighter/smaller text
- Tap a row → detail panel shows min/max inputs + kcal/pro + contribution bars

**Step 4: Commit**

```bash
git add frontend/src/lib/components/IngredientRow.svelte
git commit -m "feat: compact two-line ingredient rows on mobile (≤640px)"
```

---

### Task 4: Hide Ingredients Header on Mobile

**Files:**
- Modify: `frontend/src/routes/+page.svelte` (CSS only)

**Step 1: Add to the `@media (max-width: 640px)` block in +page.svelte**

```css
.ingredients-header {
    display: none;
}
```

The column headers (Ingredient, Min, Range, Max, Solved, kcal/pro) don't apply to the mobile card layout.

**Step 2: Commit**

```bash
git add frontend/src/routes/+page.svelte
git commit -m "feat: hide ingredient table header on mobile"
```

---

### Task 5: Sticky Bottom Bar Component

**Files:**
- Create: `frontend/src/lib/components/StickyBottomBar.svelte`
- Modify: `frontend/src/routes/+page.svelte`

**Step 1: Create StickyBottomBar.svelte**

This component receives the solution data and renders a fixed bottom bar on mobile. Tapping it expands a slide-up panel with the full right-sidebar content (totals, macros, micros).

Props needed (all passed from +page.svelte):
- `solution: SolveResponse | null`
- `pinnedTotals: Record<string, number>`
- `macroPcts: { carb: number; pro: number; fat: number } | null`
- `conflictReason: string | null`
- `expanded: boolean`
- `ontoggle: () => void`

```svelte
<script lang="ts">
    import type { SolveResponse } from '$lib/api';

    interface Props {
        solution: SolveResponse | null;
        pinnedTotals: Record<string, number>;
        macroPcts: { carb: number; pro: number; fat: number } | null;
        conflictReason: string | null;
        expanded: boolean;
        ontoggle: () => void;
    }

    let { solution, pinnedTotals, macroPcts, conflictReason, expanded, ontoggle }: Props = $props();

    let dayCal = $derived(
        solution ? Math.round(solution.meal_calories_kcal + (pinnedTotals.calories_kcal ?? 0)) : 0
    );
    let dayPro = $derived(
        solution ? Math.round(solution.meal_protein_g + (pinnedTotals.protein_g ?? 0)) : 0
    );
    let dayFib = $derived(
        solution ? Math.round(solution.meal_fiber_g + (pinnedTotals.fiber_g ?? 0)) : 0
    );
    let isFeasible = $derived(solution ? solution.status !== 'infeasible' : false);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
{#if solution}
    <div class="sticky-bar" onclick={ontoggle}>
        <span class="bar-cal">{dayCal} kcal</span>
        <span class="bar-pro">{dayPro}g pro</span>
        <span class="bar-fib">{dayFib}g fib</span>
        <span class="bar-status" class:feasible={isFeasible} class:infeasible={!isFeasible}>
            {isFeasible ? '✓' : '✗'}
        </span>
        <span class="bar-chevron" class:open={expanded}>▲</span>
    </div>
{/if}

{#if expanded}
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div class="overlay" onclick={ontoggle}></div>
{/if}

<style>
    .sticky-bar {
        display: none;
    }

    @media (max-width: 640px) {
        .sticky-bar {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 100;
            background: var(--bg-panel);
            border-top: 1px solid var(--border);
            padding: 10px 16px;
            font-size: 14px;
            font-weight: 500;
            font-variant-numeric: tabular-nums;
            cursor: pointer;
            -webkit-backdrop-filter: blur(12px);
            backdrop-filter: blur(12px);
        }

        .bar-cal { color: #f59e0b; }
        .bar-pro { color: #3b82f6; }
        .bar-fib { color: #22c55e; }

        .bar-status {
            font-weight: 700;
            font-size: 16px;
        }

        .bar-status.feasible { color: #22c55e; }
        .bar-status.infeasible { color: #ef4444; }

        .bar-chevron {
            font-size: 10px;
            color: var(--text-muted);
            transition: transform 0.2s;
        }

        .bar-chevron.open {
            transform: rotate(180deg);
        }

        .overlay {
            position: fixed;
            inset: 0;
            z-index: 90;
            background: rgba(0, 0, 0, 0.4);
        }
    }
</style>
```

**Step 2: Add state and mount StickyBottomBar in +page.svelte**

In the `<script>` section of `+page.svelte`, add:

```ts
import StickyBottomBar from '$lib/components/StickyBottomBar.svelte';
```

Add state:

```ts
let bottomBarExpanded = $state(false);
```

In the template, after the closing `</div><!-- /.main-columns -->` (line ~885) and before the modals, add:

```svelte
<StickyBottomBar
    {solution}
    {pinnedTotals}
    {macroPcts}
    {conflictReason}
    expanded={bottomBarExpanded}
    ontoggle={() => { bottomBarExpanded = !bottomBarExpanded; }}
/>
```

**Step 3: Hide right-column on mobile and show slide-up panel instead**

Add to the `@media (max-width: 640px)` block in `+page.svelte`:

```css
.right-column {
    display: none;
}

/* Add bottom padding so content isn't hidden behind sticky bar */
.app {
    padding-bottom: 60px;
}
```

**Step 4: Verify visually**

At 375×812:
- Right sidebar is hidden
- Sticky bar appears at bottom: "3450 kcal  160g pro  40g fib  ✓"
- Tapping shows overlay

**Step 5: Commit**

```bash
git add frontend/src/lib/components/StickyBottomBar.svelte frontend/src/routes/+page.svelte
git commit -m "feat: sticky bottom nutrition bar on mobile (≤640px)"
```

---

### Task 6: Slide-Up Panel for Full Nutrition Details

**Files:**
- Modify: `frontend/src/lib/components/StickyBottomBar.svelte`
- Modify: `frontend/src/routes/+page.svelte`

The slide-up panel needs to show the same content as the right sidebar: totals, macro breakdown bar, and full micronutrient table. Rather than duplicating all that markup, we'll use a CSS approach: on mobile when `bottomBarExpanded` is true, show the right-column in a fixed slide-up panel.

**Step 1: Change approach — conditionally show right-column as slide-up panel**

Instead of hiding `.right-column` entirely, restyle it as a slide-up panel on mobile when expanded.

Remove the `display: none` for `.right-column` from the mobile CSS added in Task 5. Replace with:

```css
.right-column {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 95;
    max-height: 70vh;
    overflow-y: auto;
    transform: translateY(100%);
    transition: transform 0.3s ease;
    padding: 16px;
    background: var(--bg-body);
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.3);
}

.right-column.mobile-open {
    transform: translateY(0);
}
```

**Step 2: Add mobile-open class binding**

In `+page.svelte` template, update the right-column div (line ~741):

From:
```svelte
<div class="right-column">
```

To:
```svelte
<div class="right-column" class:mobile-open={bottomBarExpanded}>
```

**Step 3: Add overlay to StickyBottomBar**

The overlay is already in StickyBottomBar from Task 5. It covers the screen behind the panel at z-index: 90 (panel is 95, bar is 100).

**Step 4: Verify visually**

At 375×812:
- Tap sticky bar → right-column slides up from bottom covering 70% of screen
- Can scroll through all micronutrients
- Tap overlay or bar again → panel slides down

**Step 5: Commit**

```bash
git add frontend/src/lib/components/StickyBottomBar.svelte frontend/src/routes/+page.svelte
git commit -m "feat: slide-up nutrition panel on mobile"
```

---

### Task 7: Polish and Visual Verification

**Files:**
- Modify: `frontend/src/routes/+page.svelte` (minor CSS tweaks)
- Modify: `frontend/src/lib/components/IngredientRow.svelte` (minor tweaks)

**Step 1: Test at multiple mobile widths**

Using Playwright, resize to and screenshot at:
- 375×812 (iPhone SE)
- 390×844 (iPhone 14)
- 414×896 (iPhone 11)
- 360×800 (Android common)

Check for:
- No horizontal overflow / scrollbar
- All text readable (minimum ~12px effective)
- Sliders are draggable with thumb targets ≥44px
- Sticky bar doesn't overlap content
- Slide-up panel scrolls properly

**Step 2: Test at desktop width to ensure no regressions**

Resize to 1400×900 and verify desktop layout is unchanged.

**Step 3: Fix any issues found**

Apply targeted CSS fixes for any problems discovered.

**Step 4: Commit**

```bash
git add -A
git commit -m "fix: mobile layout polish and edge cases"
```

---

### Task 8: AddIngredientModal Mobile Tweaks

**Files:**
- Modify: `frontend/src/lib/components/AddIngredientModal.svelte`

**Step 1: Read current modal styles**

Read `AddIngredientModal.svelte` to understand current layout.

**Step 2: Add mobile CSS**

The modal likely uses `position: fixed` already. Add mobile tweaks to make it full-screen on phones:

```css
@media (max-width: 640px) {
    .modal-content {
        width: 100%;
        height: 100%;
        max-width: none;
        max-height: none;
        border-radius: 0;
        margin: 0;
    }
}
```

(Exact selectors depend on reading the file in Step 1.)

**Step 3: Verify and commit**

```bash
git add frontend/src/lib/components/AddIngredientModal.svelte
git commit -m "feat: full-screen add ingredient modal on mobile"
```
