<script lang="ts">
	import type { Food, MicroResult } from '$lib/api';
	import { computeGapScore, countGapsFilled } from '$lib/contributions';

	interface Props {
		foods: Record<number, Food>;
		existingKeys: Set<number>;
		microResults: Record<string, MicroResult>;
		onselect: (key: number) => void;
		onclose: () => void;
	}

	let { foods, existingKeys, microResults, onselect, onclose }: Props = $props();

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

	// Pre-compute gap scores once when microResults change, not inside sort
	let gapScores = $derived.by(() => {
		if (!hasMicroData) return new Map<string, number>();
		const scores = new Map<string, number>();
		for (const [key, food] of Object.entries(foods)) {
			scores.set(key, computeGapScore(0, food, microResults));
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

	let results = $derived.by(() => {
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
					const ac = a.commonness ?? 3;
					const bc = b.commonness ?? 3;
					if (ac !== bc) return bc - ac;
					if (hasMicroData) {
						return (gapScores.get(kb) ?? 0) - (gapScores.get(ka) ?? 0);
					}
					return 0;
				});
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

		return entries;
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
			<button class="close-btn" onclick={onclose}>×</button>
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
			{#each results as [key, food]}
				{@const gaps = hasMicroData ? countGapsFilled(food, microResults) : 0}
				<button class="result-item" onclick={() => onselect(Number(key))}>
					<span class="result-name">{food.name}</span>
					<span class="result-note">{food.subtitle}</span>
					<span class="result-macros">
						{food.calories_kcal_per_100g} kcal · {food.protein_g_per_100g}g pro · {food.fiber_g_per_100g}g fiber
					</span>
					<span class="result-meta">
						{#if gaps > 0}
							<span class="result-gaps">fills {gaps} gap{gaps !== 1 ? 's' : ''}</span>
						{/if}
						<span class="result-category">{food.category}</span>
					</span>
				</button>
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

	.result-name {
		font-weight: 500;
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
</style>
