# Similar Ingredient De-ranking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** De-rank ingredients similar to those already in the plan when browsing the Add Ingredient modal (no search query).

**Architecture:** Add word-overlap similarity detection to `AddIngredientModal.svelte`. Build a set of significant words from plan ingredient names, flag candidates as similar, sort similar items to the bottom in browse mode only.

**Tech Stack:** Svelte 5, TypeScript

**Design doc:** `docs/plans/2026-02-16-similar-ingredient-deranking-design.md`

---

### Task 1: Add word-overlap similarity and de-ranking to browse sort

**Files:**
- Modify: `frontend/src/lib/components/AddIngredientModal.svelte:28-73`

**Step 1: Add the `planWords` derived set**

After `gapScores` (line 36), add a derived that extracts significant words from existing plan ingredients:

```typescript
// Significant words from plan ingredient names (for de-ranking similar items in browse)
let planWords = $derived.by(() => {
	const words = new Set<string>();
	for (const key of existingKeys) {
		const food = foods[key];
		if (!food) continue;
		for (const word of food.name.toLowerCase().split(/\s+/)) {
			if (word.length >= 3) words.add(word);
		}
	}
	return words;
});
```

**Step 2: Update the browse-mode sort (the `else` branch, lines 60-69)**

Replace the existing `else` block with a version that de-ranks similar items:

```typescript
} else {
	entries = entries.sort(([ka, a], [kb, b]) => {
		// De-rank items sharing significant name words with plan ingredients
		const aWords = a.name.toLowerCase().split(/\s+/);
		const bWords = b.name.toLowerCase().split(/\s+/);
		const aSimilar = aWords.some((w) => w.length >= 3 && planWords.has(w)) ? 1 : 0;
		const bSimilar = bWords.some((w) => w.length >= 3 && planWords.has(w)) ? 1 : 0;
		if (aSimilar !== bSimilar) return aSimilar - bSimilar;
		const ac = a.commonness ?? 3;
		const bc = b.commonness ?? 3;
		if (ac !== bc) return bc - ac;
		if (hasMicroData) {
			return (gapScores.get(kb) ?? 0) - (gapScores.get(ka) ?? 0);
		}
		return 0;
	});
}
```

**Step 3: Verify in browser**

1. Open the app (dev server should already be running)
2. Ensure "Egg" (or similar) is in the plan
3. Open Add Ingredient modal with empty search
4. Confirm "Fried Egg", "Scrambled Egg", etc. are sorted to the bottom
5. Type "egg" in search — confirm normal search ranking (no de-ranking)

**Step 4: Commit**

```bash
git add frontend/src/lib/components/AddIngredientModal.svelte
git commit -m "feat: de-rank similar ingredients in add-ingredient browse mode"
```

---

Plan complete and saved to `docs/plans/2026-02-16-similar-ingredient-deranking-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?