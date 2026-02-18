# Smarter Gap-Fill Heuristic Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the "fills N gaps" badge and sort ranking in the Add Ingredient modal more accurate by using calorie-aware serving estimates and severity-weighted gap scoring.

**Architecture:** Update `computeGapScore` and `countGapsFilled` in `contributions.ts` to accept an `estimatedServingG` parameter. Add severity weighting to `computeGapScore`. Compute per-food serving estimates in `AddIngredientModal.svelte` using meal calorie data passed from the page.

**Tech Stack:** TypeScript, Svelte 5

---

### Task 1: Update `contributions.ts` functions to accept serving estimate

**Files:**
- Modify: `frontend/src/lib/contributions.ts:101-146`

**Step 1: Update `computeGapScore` signature and add severity weighting**

Replace lines 101-125:

```typescript
export function computeGapScore(
	foodKey: number | string,
	food: Food,
	microResults: Record<string, MicroResult>,
	estimatedServingG: number = 250
): number {
	let score = 0;

	for (const [key, mr] of Object.entries(microResults)) {
		if (mr.pct >= 100) continue; // no gap
		const gap = mr.dri - (mr.total + mr.pinned);
		if (gap <= 0) continue;

		const per100g = food.micros[key];
		if (!per100g) continue;

		const wouldAdd = (per100g * estimatedServingG) / 100;
		const fillPct = Math.min(wouldAdd / gap, 1.0);
		// Weight by gap severity: nutrients further from 100% matter more
		const severity = (100 - mr.pct) / 100;
		score += fillPct * severity;
	}

	return score;
}
```

**Step 2: Update `countGapsFilled` to accept serving estimate**

Replace lines 127-146:

```typescript
export function countGapsFilled(
	food: Food,
	microResults: Record<string, MicroResult>,
	estimatedServingG: number = 250
): number {
	let count = 0;

	for (const [key, mr] of Object.entries(microResults)) {
		if (mr.pct >= 100) continue;
		const gap = mr.dri - (mr.total + mr.pinned);
		if (gap <= 0) continue;

		const per100g = food.micros[key];
		if (!per100g) continue;

		const wouldAdd = (per100g * estimatedServingG) / 100;
		if (wouldAdd / gap > 0.1) count++;
	}

	return count;
}
```

**Step 3: Remove the `ESTIMATED_SERVING_G` constant (line 102)**

Delete `const ESTIMATED_SERVING_G = 250;` — no longer needed since it's a parameter with default.

**Step 4: Commit**

```bash
git add frontend/src/lib/contributions.ts
git commit -m "refactor: parameterize serving estimate in gap functions, add severity weighting"
```

---

### Task 2: Pass meal data to modal and compute per-food serving estimates

**Files:**
- Modify: `frontend/src/routes/+page.svelte:880-887` (modal invocation)
- Modify: `frontend/src/lib/components/AddIngredientModal.svelte:5-13,29-36,130`

**Step 1: Add `mealCalories` and `maxPerIngredient` props to modal invocation in `+page.svelte`**

Replace lines 880-887:

```svelte
{#if showAddModal}
	<AddIngredientModal
		{foods}
		{existingKeys}
		microResults={solution?.micros ?? {}}
		mealCalories={mealCal}
		maxPerIngredient={maxPerIngr}
		onselect={addIngredient}
		onclose={() => (showAddModal = false)}
	/>
{/if}
```

Note: `mealCal` is defined at line 168 as `$derived(dailyCal - (pinnedTotals.calories_kcal ?? 0))`. `maxPerIngr` — check the variable name for the global max-per-ingredient setting.

**Step 2: Find the `maxPerIngr` variable name**

Run: `grep -n 'maxPerIngr\|maxPerIng\|max_per\|defaultMax' frontend/src/routes/+page.svelte | head -10`

Use whatever variable holds the global "Max / ingr" value (visible in the UI at line ~107 of +page.svelte).

**Step 3: Update `AddIngredientModal.svelte` Props and add new props**

Update the Props interface (lines 5-11) to add the new props:

```typescript
interface Props {
	foods: Record<number, Food>;
	existingKeys: Set<number>;
	microResults: Record<string, MicroResult>;
	mealCalories: number;
	maxPerIngredient: number;
	onselect: (key: number) => void;
	onclose: () => void;
}

let { foods, existingKeys, microResults, mealCalories, maxPerIngredient, onselect, onclose }: Props = $props();
```

**Step 4: Add per-food serving estimate computation**

After the `hasMicroData` derived (line 26), add a helper function and update `gapScores` to use it:

```typescript
function estimateServingG(food: Food): number {
	const numIngredients = Math.max(existingKeys.size, 1);
	const calShareG = (mealCalories / (numIngredients + 1)) / (food.calories_kcal_per_100g / 100);
	return Math.min(maxPerIngredient, calShareG);
}
```

**Step 5: Update `gapScores` derived to pass serving estimate**

Replace the gapScores derived (lines 29-36):

```typescript
let gapScores = $derived.by(() => {
	if (!hasMicroData) return new Map<string, number>();
	const scores = new Map<string, number>();
	for (const [key, food] of Object.entries(foods)) {
		scores.set(key, computeGapScore(0, food, microResults, estimateServingG(food)));
	}
	return scores;
});
```

**Step 6: Update `countGapsFilled` call in template**

Replace line 130:

```svelte
{@const gaps = hasMicroData ? countGapsFilled(food, microResults, estimateServingG(food)) : 0}
```

**Step 7: Verify in browser**

1. Open the app (dev server should already be running)
2. Open Add Ingredient modal
3. Compare gap counts — calorie-dense foods (butter, oils) should show fewer gaps than before
4. Sort order should favor foods that help the worst nutrients

**Step 8: Commit**

```bash
git add frontend/src/lib/components/AddIngredientModal.svelte frontend/src/routes/+page.svelte
git commit -m "feat: calorie-aware serving estimates and severity-weighted gap ranking"
```
