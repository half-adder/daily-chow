<script lang="ts">
	import type { Food, MicroResult } from '$lib/api';
	import { computeGapScore, countGapsFilled } from '$lib/contributions';

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

	let query = $state('');
	let debouncedQuery = $state('');
	let debounceTimer: ReturnType<typeof setTimeout>;

	function onInput(e: Event) {
		const value = (e.target as HTMLInputElement).value;
		query = value;
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => { debouncedQuery = value; }, 120);
	}

	let hasMicroData = $derived(Object.keys(microResults).length > 0);

	function estimateServingG(food: Food): number {
		const numIngredients = Math.max(existingKeys.size, 1);
		const calShareG = (mealCalories / (numIngredients + 1)) / (food.calories_kcal_per_100g / 100);
		return Math.min(maxPerIngredient, calShareG);
	}

	// Pre-compute gap scores once when microResults change, not inside sort
	let gapScores = $derived.by(() => {
		if (!hasMicroData) return new Map<string, number>();
		const scores = new Map<string, number>();
		for (const [key, food] of Object.entries(foods)) {
			scores.set(key, computeGapScore(0, food, microResults, estimateServingG(food)));
		}
		return scores;
	});

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

	// Pre-compute similarity flags so we don't split strings inside the sort comparator
	let similarFlags = $derived.by(() => {
		const flags = new Map<string, boolean>();
		for (const [key, food] of Object.entries(foods)) {
			const isSimilar = food.name.toLowerCase()
				.split(/\s+/)
				.some((w) => w.length >= 3 && planWords.has(w));
			flags.set(key, isSimilar);
		}
		return flags;
	});

	interface FoodGroup {
		groupKey: string;
		representative: [string, Food];
		variants: [string, Food][];
	}

	let expandedGroups = $state(new Set<string>());

	function toggleGroup(groupKey: string, e: Event) {
		e.stopPropagation();
		if (expandedGroups.has(groupKey)) {
			expandedGroups.delete(groupKey);
		} else {
			expandedGroups.add(groupKey);
		}
		expandedGroups = new Set(expandedGroups);
	}

	function computeScore(key: string, food: Food): number {
		return (food.commonness ?? 3) + (gapScores.get(key) ?? 0);
	}

	let groupedResults = $derived.by(() => {
		const q = debouncedQuery.toLowerCase().trim();
		let entries = Object.entries(foods).filter(([k]) => !existingKeys.has(Number(k)));

		if (q) {
			entries = entries
				.filter(([, food]) => {
					const searchable = `${food.name} ${food.subtitle} ${food.usda_description} ${food.category}`.toLowerCase();
					return searchable.includes(q);
				})
				.sort(([ka, a], [kb, b]) => {
					const aStarts = a.name.toLowerCase().startsWith(q) ? 0 : 1;
					const bStarts = b.name.toLowerCase().startsWith(q) ? 0 : 1;
					if (aStarts !== bStarts) return aStarts - bStarts;
					return computeScore(kb, b) - computeScore(ka, a);
				});
		} else {
			entries = entries.sort(([ka, a], [kb, b]) => {
				const aSimilar = similarFlags.get(ka) ? 1 : 0;
				const bSimilar = similarFlags.get(kb) ? 1 : 0;
				if (aSimilar !== bSimilar) return aSimilar - bSimilar;
				return computeScore(kb, b) - computeScore(ka, a);
			});
		}

		// Group by food.group — entries are already sorted by score,
		// so the first entry per group is the representative.
		const groupMap = new Map<string, { representative: [string, Food]; variants: [string, Food][] }>();
		for (const entry of entries) {
			const [, food] = entry;
			const gk = food.group.toLowerCase();
			const existing = groupMap.get(gk);
			if (!existing) {
				groupMap.set(gk, { representative: entry, variants: [] });
			} else {
				existing.variants.push(entry);
			}
		}

		// Preserve order from sorted entries
		const groups: FoodGroup[] = [];
		const seen = new Set<string>();
		for (const entry of entries) {
			const gk = entry[1].group.toLowerCase();
			if (seen.has(gk)) continue;
			seen.add(gk);
			const g = groupMap.get(gk)!;
			groups.push({ groupKey: gk, representative: g.representative, variants: g.variants });
		}

		return groups;
	});

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onclose();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="modal-overlay" onclick={onclose}>
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<h3>Add Ingredient</h3>
			<button class="close-btn" onclick={onclose}>&times;</button>
		</div>

		<input
			type="text"
			class="search-input"
			placeholder="Search foods..."
			value={query}
			oninput={onInput}
			autofocus
		/>

		<div class="results">
			{#each groupedResults as { groupKey, representative, variants }}
				{@const [key, food] = representative}
				{@const gaps = hasMicroData ? countGapsFilled(food, microResults, estimateServingG(food)) : 0}
				<div class="group-row">
					<button class="result-item" onclick={() => onselect(Number(key))}>
						<span class="result-name">
							{food.name}
							{#if variants.length > 0}
								<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
								<span
									class="variant-toggle"
									onclick={(e) => toggleGroup(groupKey, e)}
									role="button"
									tabindex="0"
								>
									{#if expandedGroups.has(groupKey)}
										&minus;{variants.length} more
									{:else}
										+{variants.length} more
									{/if}
								</span>
							{/if}
						</span>
						<span class="result-note">{food.subtitle}</span>
						<span class="result-macros">
							{food.calories_kcal_per_100g} kcal &middot; {food.protein_g_per_100g}g pro &middot; {food.fiber_g_per_100g}g fiber
						</span>
						<span class="result-meta">
							{#if gaps > 0}
								<span class="result-gaps">fills {gaps} gap{gaps !== 1 ? 's' : ''}</span>
							{/if}
							<span class="result-category">{food.category}</span>
						</span>
					</button>
				</div>

				{#if expandedGroups.has(groupKey)}
					{#each variants as [vKey, vFood]}
						{@const vGaps = hasMicroData ? countGapsFilled(vFood, microResults, estimateServingG(vFood)) : 0}
						<button class="result-item variant-item" onclick={() => onselect(Number(vKey))}>
							<span class="result-name">{vFood.name}</span>
							<span class="result-note">{vFood.subtitle}</span>
							<span class="result-macros">
								{vFood.calories_kcal_per_100g} kcal &middot; {vFood.protein_g_per_100g}g pro &middot; {vFood.fiber_g_per_100g}g fiber
							</span>
							<span class="result-meta">
								{#if vGaps > 0}
									<span class="result-gaps">fills {vGaps} gap{vGaps !== 1 ? 's' : ''}</span>
								{/if}
								<span class="result-category">{vFood.category}</span>
							</span>
						</button>
					{/each}
				{/if}
			{:else}
				<div class="no-results">No matching foods</div>
			{/each}
		</div>
	</div>
</div>

<style>
	.modal-overlay {
		position: fixed;
		inset: 0;
		background: var(--shadow-overlay);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
		backdrop-filter: blur(2px);
	}

	.modal {
		background: var(--bg-panel);
		border: 1px solid var(--border);
		border-radius: 12px;
		width: 500px;
		max-height: 80vh;
		display: flex;
		flex-direction: column;
		box-shadow: 0 20px 60px var(--shadow-modal);
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 16px 20px 0;
	}

	h3 {
		margin: 0;
		color: var(--text-primary);
		font-size: 16px;
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--text-muted);
		font-size: 22px;
		cursor: pointer;
		padding: 0 4px;
	}

	.close-btn:hover {
		color: var(--text-primary);
	}

	.search-input {
		margin: 12px 20px;
		padding: 10px 14px;
		background: var(--bg-input);
		border: 1px solid var(--border-input);
		border-radius: 8px;
		color: var(--text-primary);
		font-size: 14px;
		outline: none;
	}

	.search-input:focus {
		border-color: #3b82f6;
	}

	.results {
		overflow-y: auto;
		padding: 0 8px 8px;
		flex: 1;
	}

	.group-row {
		position: relative;
	}

	.result-item {
		display: grid;
		grid-template-columns: 1fr auto;
		grid-template-rows: auto auto;
		gap: 2px 12px;
		width: 100%;
		padding: 10px 12px;
		background: none;
		border: none;
		border-radius: 8px;
		cursor: pointer;
		text-align: left;
		color: var(--text-primary);
	}

	.result-item:hover {
		background: var(--bg-hover);
	}

	.variant-item {
		padding-left: 28px;
		opacity: 0.75;
	}

	.variant-item:hover {
		opacity: 1;
	}

	.variant-toggle {
		display: inline-flex;
		align-items: center;
		margin-left: 6px;
		padding: 1px 8px;
		font-size: 11px;
		font-weight: 500;
		color: var(--accent);
		background: color-mix(in srgb, var(--accent) 12%, transparent);
		border-radius: 10px;
		cursor: pointer;
		vertical-align: middle;
		user-select: none;
	}

	.variant-toggle:hover {
		background: color-mix(in srgb, var(--accent) 22%, transparent);
	}

	.result-name {
		font-weight: 500;
		display: flex;
		align-items: center;
		gap: 0;
	}

	.result-note {
		font-size: 12px;
		color: var(--text-muted);
	}

	.result-macros {
		font-size: 12px;
		color: var(--text-muted);
	}

	.result-meta {
		display: flex;
		align-items: center;
		gap: 8px;
		justify-self: end;
	}

	.result-gaps {
		font-size: 11px;
		color: #22c55e;
		background: rgba(34, 197, 94, 0.1);
		padding: 1px 6px;
		border-radius: 8px;
	}

	.result-category {
		font-size: 11px;
		color: #3b82f6;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.no-results {
		padding: 20px;
		text-align: center;
		color: var(--text-dim);
	}

	@media (max-width: 768px) {
		.modal {
			width: 100vw;
			height: 100vh;
			max-width: none;
			max-height: none;
			border-radius: 0;
			margin: 0;
		}
	}
</style>
