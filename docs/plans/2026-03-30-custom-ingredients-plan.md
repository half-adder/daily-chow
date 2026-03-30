# Custom Ingredients Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to create custom ingredients with manually entered nutrition data, stored in localStorage with import/export.

**Architecture:** New `customFoods.ts` module handles localStorage CRUD and ID generation. The `AddIngredientModal` gains two new views (create/edit form, management list) via internal state toggle. Custom foods merge into the main `foods` record on load and after create/edit/delete.

**Tech Stack:** SvelteKit (Svelte 5 with runes), TypeScript, localStorage

---

### Task 1: Custom Foods Storage Module

**Files:**
- Create: `frontend/src/lib/customFoods.ts`

**Step 1: Create the module**

```typescript
import type { Food } from './api';

const STORAGE_KEY = 'custom-foods';

export function loadCustomFoods(): Food[] {
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (!raw) return [];
		return JSON.parse(raw) as Food[];
	} catch {
		return [];
	}
}

export function saveCustomFoods(foods: Food[]): void {
	localStorage.setItem(STORAGE_KEY, JSON.stringify(foods));
}

export function nextCustomId(existing: Food[]): number {
	if (existing.length === 0) return -1;
	return Math.min(...existing.map((f) => f.fdc_id)) - 1;
}

export function mergeCustomFoods(
	usdaFoods: Record<number, Food>,
	customFoods: Food[]
): Record<number, Food> {
	const merged = { ...usdaFoods };
	for (const f of customFoods) {
		merged[f.fdc_id] = f;
	}
	return merged;
}

export function exportCustomFoods(foods: Food[]): void {
	const blob = new Blob([JSON.stringify(foods, null, 2)], { type: 'application/json' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = 'custom-ingredients.json';
	a.click();
	URL.revokeObjectURL(url);
}

export interface ImportResult {
	added: number;
	skipped: number;
	conflicts: string[];
}

export function validateImportedFoods(data: unknown): Food[] | null {
	if (!Array.isArray(data)) return null;
	for (const item of data) {
		if (
			typeof item !== 'object' || item === null ||
			typeof item.name !== 'string' ||
			typeof item.calories_kcal_per_100g !== 'number' ||
			typeof item.protein_g_per_100g !== 'number' ||
			typeof item.fat_g_per_100g !== 'number' ||
			typeof item.carbs_g_per_100g !== 'number' ||
			typeof item.fiber_g_per_100g !== 'number'
		) {
			return null;
		}
	}
	return data as Food[];
}
```

**Step 2: Commit**

```bash
git add frontend/src/lib/customFoods.ts
git commit -m "feat: add custom foods localStorage module"
```

---

### Task 2: Integrate Custom Foods into App Startup

**Files:**
- Modify: `frontend/src/routes/+page.svelte`

**Step 1: Import and wire up custom foods loading**

At the top of `+page.svelte`, add import:

```typescript
import { loadCustomFoods, saveCustomFoods, mergeCustomFoods, nextCustomId } from '$lib/customFoods';
```

Add state for custom foods (near other state declarations around line 60):

```typescript
let customFoods = $state<Food[]>([]);
```

**Step 2: Modify `onMount` to merge custom foods**

Change the `onMount` block (line 574) from:

```typescript
onMount(async () => {
    const hasState = localStorage.getItem('daily-chow');
    const rawFoods = await fetchFoods();
    initWorkerFoods(rawFoods);
    foods = rawFoods;
    loadState();
    applyTheme(theme);
    doSolve();
    if (!hasState) showWelcome = true;
});
```

To:

```typescript
onMount(async () => {
    const hasState = localStorage.getItem('daily-chow');
    const rawFoods = await fetchFoods();
    customFoods = loadCustomFoods();
    const merged = mergeCustomFoods(rawFoods, customFoods);
    initWorkerFoods(merged);
    foods = merged;
    loadState();
    applyTheme(theme);
    doSolve();
    if (!hasState) showWelcome = true;
});
```

**Step 3: Add helper to refresh foods after custom food changes**

Add near the `addIngredient` function (around line 455):

```typescript
function refreshCustomFoods() {
    customFoods = loadCustomFoods();
    // Re-merge: need original USDA foods, so subtract existing custom entries
    const usdaOnly: Record<number, Food> = {};
    for (const [id, food] of Object.entries(foods)) {
        if (food.category !== 'Custom') usdaOnly[Number(id)] = food;
    }
    const merged = mergeCustomFoods(usdaOnly, customFoods);
    foods = merged;
    initWorkerFoods(merged);
}
```

**Step 4: Commit**

```bash
git add frontend/src/routes/+page.svelte
git commit -m "feat: load and merge custom foods on startup"
```

---

### Task 3: Create/Edit Form in AddIngredientModal

**Files:**
- Modify: `frontend/src/lib/components/AddIngredientModal.svelte`

**Step 1: Add new props and state for custom food workflow**

Add to the Props interface:

```typescript
customFoods: Food[];
oncustomchange: () => void;
```

Add internal state for view management:

```typescript
type ModalView = 'search' | 'create' | 'manage';
let view = $state<ModalView>('search');
let editingFood = $state<Food | null>(null);

// Form fields
let formName = $state('');
let formSubtitle = $state('');
let formCalories = $state('');
let formProtein = $state('');
let formFat = $state('');
let formCarbs = $state('');
let formFiber = $state('');
let formPortionUnit = $state('');
let formPortionG = $state('');
let showMicros = $state(false);
let formMicros = $state<Record<string, string>>({});
let formError = $state('');
```

**Step 2: Add the form reset and populate helpers**

```typescript
import { loadCustomFoods, saveCustomFoods, nextCustomId, exportCustomFoods, validateImportedFoods, type ImportResult } from '$lib/customFoods';

const MICRO_LABELS: Record<string, { name: string; unit: string }> = {
    calcium_mg: { name: 'Calcium', unit: 'mg' },
    iron_mg: { name: 'Iron', unit: 'mg' },
    magnesium_mg: { name: 'Magnesium', unit: 'mg' },
    phosphorus_mg: { name: 'Phosphorus', unit: 'mg' },
    potassium_mg: { name: 'Potassium', unit: 'mg' },
    zinc_mg: { name: 'Zinc', unit: 'mg' },
    copper_mg: { name: 'Copper', unit: 'mg' },
    manganese_mg: { name: 'Manganese', unit: 'mg' },
    selenium_mcg: { name: 'Selenium', unit: 'mcg' },
    vitamin_c_mg: { name: 'Vitamin C', unit: 'mg' },
    thiamin_mg: { name: 'Thiamin (B1)', unit: 'mg' },
    riboflavin_mg: { name: 'Riboflavin (B2)', unit: 'mg' },
    niacin_mg: { name: 'Niacin (B3)', unit: 'mg' },
    vitamin_b6_mg: { name: 'Vitamin B6', unit: 'mg' },
    folate_mcg: { name: 'Folate', unit: 'mcg' },
    vitamin_b12_mcg: { name: 'Vitamin B12', unit: 'mcg' },
    vitamin_a_mcg: { name: 'Vitamin A', unit: 'mcg' },
    vitamin_d_mcg: { name: 'Vitamin D', unit: 'mcg' },
    vitamin_e_mg: { name: 'Vitamin E', unit: 'mg' },
    vitamin_k_mcg: { name: 'Vitamin K', unit: 'mcg' },
};

function resetForm() {
    formName = '';
    formSubtitle = '';
    formCalories = '';
    formProtein = '';
    formFat = '';
    formCarbs = '';
    formFiber = '';
    formPortionUnit = '';
    formPortionG = '';
    showMicros = false;
    formMicros = {};
    formError = '';
    editingFood = null;
}

function populateForm(food: Food) {
    editingFood = food;
    formName = food.name;
    formSubtitle = food.subtitle;
    formCalories = String(food.calories_kcal_per_100g);
    formProtein = String(food.protein_g_per_100g);
    formFat = String(food.fat_g_per_100g);
    formCarbs = String(food.carbs_g_per_100g);
    formFiber = String(food.fiber_g_per_100g);
    formPortionUnit = food.portion?.unit ?? '';
    formPortionG = food.portion ? String(food.portion.g) : '';
    const micros: Record<string, string> = {};
    for (const [k, v] of Object.entries(food.micros)) {
        if (v > 0) micros[k] = String(v);
    }
    formMicros = micros;
    showMicros = Object.keys(micros).length > 0;
    formError = '';
}

function saveForm() {
    // Validate
    if (!formName.trim()) { formError = 'Name is required'; return; }
    const cal = Number(formCalories);
    const pro = Number(formProtein);
    const fat = Number(formFat);
    const carb = Number(formCarbs);
    const fib = Number(formFiber);
    if ([cal, pro, fat, carb, fib].some((v) => isNaN(v) || v < 0)) {
        formError = 'All macro values must be non-negative numbers';
        return;
    }

    const micros: Record<string, number> = {};
    for (const [k, v] of Object.entries(formMicros)) {
        if (v.trim() === '') continue;
        const num = Number(v);
        if (isNaN(num) || num < 0) {
            formError = `Invalid value for ${MICRO_LABELS[k]?.name ?? k}`;
            return;
        }
        micros[k] = num;
    }

    const existing = loadCustomFoods();
    const food: Food = {
        fdc_id: editingFood ? editingFood.fdc_id : nextCustomId(existing),
        name: formName.trim(),
        subtitle: formSubtitle.trim(),
        usda_description: formName.trim(),
        category: 'Custom',
        commonness: 5,
        group: formName.trim(),
        calories_kcal_per_100g: cal,
        protein_g_per_100g: pro,
        fat_g_per_100g: fat,
        carbs_g_per_100g: carb,
        fiber_g_per_100g: fib,
        micros,
    };
    if (formPortionUnit.trim() && formPortionG.trim()) {
        const pg = Number(formPortionG);
        if (!isNaN(pg) && pg > 0) {
            food.portion = { unit: formPortionUnit.trim(), g: pg };
        }
    }

    if (editingFood) {
        const idx = existing.findIndex((f) => f.fdc_id === editingFood!.fdc_id);
        if (idx >= 0) existing[idx] = food;
        else existing.push(food);
    } else {
        existing.push(food);
    }
    saveCustomFoods(existing);
    oncustomchange();
    resetForm();
    view = 'search';
}
```

**Step 3: Add the form markup**

Inside the modal `<div class="modal">`, after the search input and before the results div, add a conditional block for the create/edit form view. When `view === 'create'`, show the form instead of the search/results content.

The form layout:
- Required macro fields as a 2-column grid (label + input)
- Optional subtitle and portion fields
- Collapsible micronutrients section with all 20 fields
- Save / Cancel buttons
- Error message display

**Step 4: Add the "Create Custom Ingredient" button and "My Ingredients" link**

In the search view (between the search input and results):
- "Create Custom Ingredient" button that sets `view = 'create'`
- "My Ingredients (N)" link (only shown if `customFoods.length > 0`) that sets `view = 'manage'`

**Step 5: Add "Custom" badge in search results**

In the result-item template, after the category badge, add:
```svelte
{#if food.category === 'Custom'}
    <span class="custom-badge">Custom</span>
{/if}
```

Style the badge with a distinct color (e.g., purple/violet background).

**Step 6: Commit**

```bash
git add frontend/src/lib/components/AddIngredientModal.svelte
git commit -m "feat: add create/edit form for custom ingredients"
```

---

### Task 4: Management View in AddIngredientModal

**Files:**
- Modify: `frontend/src/lib/components/AddIngredientModal.svelte`

**Step 1: Add delete and import functions**

```typescript
function deleteCustomFood(fdcId: number) {
    if (!confirm('Delete this custom ingredient?')) return;
    const existing = loadCustomFoods();
    const updated = existing.filter((f) => f.fdc_id !== fdcId);
    saveCustomFoods(updated);
    oncustomchange();
}

function handleImport() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async () => {
        const file = input.files?.[0];
        if (!file) return;
        try {
            const text = await file.text();
            const data = JSON.parse(text);
            const imported = validateImportedFoods(data);
            if (!imported) {
                formError = 'Invalid file format';
                return;
            }
            const existing = loadCustomFoods();
            let added = 0;
            let skipped = 0;
            for (const food of imported) {
                const conflict = existing.find((f) => f.name === food.name);
                if (conflict) {
                    if (confirm(`"${food.name}" already exists. Overwrite?`)) {
                        const idx = existing.indexOf(conflict);
                        food.fdc_id = conflict.fdc_id;
                        food.category = 'Custom';
                        existing[idx] = food;
                        added++;
                    } else {
                        skipped++;
                    }
                } else {
                    food.fdc_id = nextCustomId(existing);
                    food.category = 'Custom';
                    existing.push(food);
                    added++;
                }
            }
            saveCustomFoods(existing);
            oncustomchange();
            formError = '';
        } catch {
            formError = 'Failed to read file';
        }
    };
    input.click();
}
```

**Step 2: Add management view markup**

When `view === 'manage'`, show:
- Header: "My Ingredients" with a back arrow to return to search
- List of custom foods, each showing:
  - Name + subtitle
  - Macros summary line
  - Edit button (calls `populateForm(food); view = 'create'`)
  - Delete button (calls `deleteCustomFood(food.fdc_id)`)
- Import / Export buttons at the bottom
- The management view reads `customFoods` prop to list items

**Step 3: Commit**

```bash
git add frontend/src/lib/components/AddIngredientModal.svelte
git commit -m "feat: add custom ingredient management view with import/export"
```

---

### Task 5: Wire Up Props in +page.svelte

**Files:**
- Modify: `frontend/src/routes/+page.svelte`

**Step 1: Pass new props to AddIngredientModal**

Change the modal instantiation (around line 943) from:

```svelte
<AddIngredientModal
    {foods}
    {existingKeys}
    microResults={solution?.micros ?? {}}
    mealCalories={mealCal}
    maxPerIngredient={sliderAbsMax}
    onselect={addIngredient}
    onclose={() => (showAddModal = false)}
/>
```

To:

```svelte
<AddIngredientModal
    {foods}
    {existingKeys}
    microResults={solution?.micros ?? {}}
    mealCalories={mealCal}
    maxPerIngredient={sliderAbsMax}
    onselect={addIngredient}
    onclose={() => (showAddModal = false)}
    {customFoods}
    oncustomchange={refreshCustomFoods}
/>
```

**Step 2: Handle deletion of in-use custom foods**

Modify `refreshCustomFoods` to also clean up ingredients that reference deleted custom foods:

```typescript
function refreshCustomFoods() {
    customFoods = loadCustomFoods();
    const usdaOnly: Record<number, Food> = {};
    for (const [id, food] of Object.entries(foods)) {
        if (food.category !== 'Custom') usdaOnly[Number(id)] = food;
    }
    const merged = mergeCustomFoods(usdaOnly, customFoods);
    foods = merged;
    initWorkerFoods(merged);
    // Remove ingredients that reference deleted custom foods
    const before = ingredients.length;
    ingredients = ingredients.filter((ing) => ing.key >= 0 || merged[ing.key]);
    if (ingredients.length !== before) triggerSolve();
}
```

**Step 3: Commit**

```bash
git add frontend/src/routes/+page.svelte
git commit -m "feat: wire custom food props and cleanup on delete"
```

---

### Task 6: Styling and Polish

**Files:**
- Modify: `frontend/src/lib/components/AddIngredientModal.svelte`

**Step 1: Style the create/edit form**

Key CSS additions:
- `.custom-form` - form container with padding
- `.form-grid` - 2-column grid for macro inputs (label + input)
- `.form-row` - single row with label + input
- `.form-actions` - save/cancel button row
- `.form-error` - red error text
- `.micro-section` - collapsible micros area
- `.micro-grid` - 2-column grid for micro inputs
- `.custom-badge` - purple pill badge for "Custom" label in search results
- `.manage-list` - list container for management view
- `.manage-item` - row in management list
- `.manage-actions` - edit/delete button group
- `.import-export` - bottom button row

Follow existing modal styling conventions (use CSS variables like `--bg-input`, `--border-input`, `--text-primary`, `--text-muted`, `--accent`).

Ensure the form works well on mobile (single-column layout at `max-width: 768px`).

**Step 2: Reset view state when modal closes**

Add to the `onclose` handling:

```typescript
function handleClose() {
    resetForm();
    view = 'search';
    onclose();
}
```

Replace all `onclose` references in the template with `handleClose`.

**Step 3: Visual verification**

Take a screenshot at desktop and 390x844 mobile to verify:
- No overflow
- Form fields are properly aligned
- Buttons are accessible

**Step 4: Commit**

```bash
git add frontend/src/lib/components/AddIngredientModal.svelte
git commit -m "feat: style custom ingredient form and management view"
```

---

### Task 7: End-to-End Manual Test

**Step 1: Test create flow**
- Open Add Ingredient modal
- Click "Create Custom Ingredient"
- Fill in: Name="Test Bar", Calories=200, Protein=20, Fat=8, Carbs=25, Fiber=3
- Save, verify it appears in search results with "Custom" badge
- Add it to the meal, verify solver runs and uses it

**Step 2: Test edit flow**
- Open modal, go to "My Ingredients"
- Edit the test ingredient, change protein to 30
- Save, verify updated values

**Step 3: Test delete flow**
- Add the custom ingredient to the meal
- Go to "My Ingredients", delete it
- Verify it's removed from the meal and ingredient list

**Step 4: Test import/export flow**
- Create 2 custom ingredients
- Export to file
- Delete both
- Import the file
- Verify both are restored

**Step 5: Test persistence**
- Create a custom ingredient, refresh the page
- Verify it's still available in search

**Step 6: Commit any fixes**

---

Plan complete and saved to `docs/plans/2026-03-30-custom-ingredients-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
