# Draggable Priority Cards Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the small up/down arrow buttons for solve priorities with touch drag-and-drop cards on mobile (≤640px), using SortableJS.

**Architecture:** New `PriorityCards.svelte` component wraps the priority list and initializes SortableJS on mobile. Desktop keeps the existing up/down button UI in `+page.svelte` unchanged. The component receives `priorities` and `onreorder` as props.

**Tech Stack:** SortableJS, Svelte 5 (runes), TypeScript

---

### Task 1: Install SortableJS

**Step 1: Install the package and types**

Run:
```bash
cd frontend && bun add sortablejs && bun add -d @types/sortablejs
```

**Step 2: Verify installation**

Run:
```bash
grep sortablejs frontend/package.json
```
Expected: `"sortablejs": "^1.x.x"` in dependencies

**Step 3: Commit**

```bash
git add frontend/package.json frontend/bun.lock
git commit -m "feat: add sortablejs dependency for draggable priority cards"
```

---

### Task 2: Create PriorityCards component

**Files:**
- Create: `frontend/src/lib/components/PriorityCards.svelte`

**Step 1: Create the component**

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import Sortable from 'sortablejs';

	const LABELS: Record<string, string> = {
		micros: 'Micronutrient coverage',
		macro_ratio: 'Macro ratio target',
		ingredient_diversity: 'Ingredient diversity',
		total_weight: 'Minimize total weight'
	};

	interface Props {
		priorities: string[];
		onreorder: (newOrder: string[]) => void;
	}

	let { priorities, onreorder }: Props = $props();
	let listEl = $state<HTMLDivElement | null>(null);

	onMount(() => {
		if (!listEl) return;
		const sortable = Sortable.create(listEl, {
			animation: 150,
			handle: '.drag-handle',
			ghostClass: 'priority-card-ghost',
			chosenClass: 'priority-card-chosen',
			dragClass: 'priority-card-drag',
			onEnd: () => {
				const newOrder = Array.from(listEl!.children).map(
					(el) => (el as HTMLElement).dataset.key!
				);
				onreorder(newOrder);
			}
		});
		return () => sortable.destroy();
	});
</script>

<div class="priority-cards" bind:this={listEl}>
	{#each priorities as p, i (p)}
		<div class="priority-card" data-key={p}>
			<span class="drag-handle">⠿</span>
			<span class="priority-card-rank">{i + 1}.</span>
			<span class="priority-card-label">{LABELS[p] ?? p}</span>
		</div>
	{/each}
</div>

<style>
	.priority-cards {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.priority-card {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 12px;
		background: var(--bg-card);
		border: 1px solid var(--border-input);
		border-radius: 8px;
		font-size: 14px;
		touch-action: none;
		user-select: none;
	}

	.drag-handle {
		cursor: grab;
		color: var(--text-muted);
		font-size: 18px;
		line-height: 1;
		padding: 4px 0;
	}

	.priority-card-rank {
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
		min-width: 18px;
		text-align: right;
	}

	.priority-card-label {
		color: var(--text-primary);
	}

	.priority-card-ghost {
		opacity: 0.4;
	}

	.priority-card-chosen {
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
	}

	:global(.priority-card-drag) {
		opacity: 0.9;
	}
</style>
```

**Step 2: Verify it compiles**

Run:
```bash
cd frontend && bun run check
```
Expected: No errors related to PriorityCards

**Step 3: Commit**

```bash
git add frontend/src/lib/components/PriorityCards.svelte
git commit -m "feat: add PriorityCards component with SortableJS drag-and-drop"
```

---

### Task 3: Integrate into +page.svelte (mobile only)

**Files:**
- Modify: `frontend/src/routes/+page.svelte`

**Step 1: Add mobile detection state and import**

At the top of the `<script>` block (after the other imports, around line 11), add:

```typescript
import PriorityCards from '$lib/components/PriorityCards.svelte';
```

Add a mobile state variable near the other state declarations (around line 72):

```typescript
let isMobile = $state(false);
```

Add a `$effect` to track the media query (after the existing `$effect` blocks):

```typescript
$effect(() => {
	const mql = window.matchMedia('(max-width: 640px)');
	isMobile = mql.matches;
	const handler = () => { isMobile = mql.matches; };
	mql.addEventListener('change', handler);
	return () => mql.removeEventListener('change', handler);
});
```

**Step 2: Replace the priority list markup with conditional rendering**

Replace the priority list block at lines 612-624 with:

```svelte
<div class="target-group priority-group">
	<label>Solve priorities</label>
	{#if isMobile}
		<PriorityCards {priorities} onreorder={(newOrder) => { priorities = newOrder; triggerSolve(); }} />
	{:else}
		<div class="priority-list">
			{#each priorities as p, i}
				<div class="priority-row">
					<span class="priority-rank">{i + 1}.</span>
					<button class="priority-btn" disabled={i === 0} onclick={() => { [priorities[i - 1], priorities[i]] = [priorities[i], priorities[i - 1]]; priorities = [...priorities]; triggerSolve(); }} title="Move up">&#9650;</button>
					<button class="priority-btn" disabled={i === priorities.length - 1} onclick={() => { [priorities[i], priorities[i + 1]] = [priorities[i + 1], priorities[i]]; priorities = [...priorities]; triggerSolve(); }} title="Move down">&#9660;</button>
					<span class="priority-label">{p === 'micros' ? 'Micronutrient coverage' : p === 'macro_ratio' ? 'Macro ratio target' : p === 'ingredient_diversity' ? 'Ingredient diversity' : 'Minimize total weight'}</span>
				</div>
			{/each}
		</div>
	{/if}
</div>
```

**Step 3: Verify it compiles**

Run:
```bash
cd frontend && bun run check
```
Expected: No errors

**Step 4: Manual test**

Open the app on mobile (or use Chrome DevTools mobile emulation at 375px width):
1. The priority cards should show as draggable cards with grip handles
2. Drag a card to reorder — the solver should re-run immediately
3. Resize to desktop — the old up/down button UI should appear

**Step 5: Commit**

```bash
git add frontend/src/routes/+page.svelte
git commit -m "feat: use draggable PriorityCards on mobile, keep buttons on desktop"
```

---

### Task 4: Polish and edge cases

**Files:**
- Modify: `frontend/src/lib/components/PriorityCards.svelte`

**Step 1: Fix rank numbers after drag**

SortableJS reorders DOM elements directly, but Svelte's `{#each}` keyed by `(p)` won't re-render rank numbers. After `onEnd`, we need to force Svelte to see the new order. The `onreorder` callback already updates `priorities` in the parent which will cause a re-render with correct rank numbers. Verify this works — if the rank numbers don't update after dragging, the fix is to add a `{#key priorities}` wrapper or ensure the parent passes the updated array back down.

Test: Drag "Minimize total weight" from position 4 to position 1. Verify rank numbers show 1, 2, 3, 4 correctly (not stuck at old values).

**Step 2: Ensure scroll container doesn't interfere**

The priority cards live inside the mobile slide-up panel (`.right-column` with `overflow-y: auto`). SortableJS should handle this, but verify that dragging cards doesn't cause the panel to scroll simultaneously. If it does, the `handle` option already limits drag to the grip icon, which should prevent scroll conflicts.

Test: With several items visible in the panel, drag a priority card. The panel should not scroll during the drag.

**Step 3: Commit any fixes**

```bash
git add -u
git commit -m "fix: polish draggable priority cards edge cases"
```
