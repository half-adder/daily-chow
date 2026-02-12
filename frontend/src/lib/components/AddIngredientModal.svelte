<script lang="ts">
	import type { Food, MicroResult } from '$lib/api';
	import { computeGapScore, countGapsFilled } from '$lib/contributions';

	interface Props {
		foods: Record<string, Food>;
		existingKeys: Set<string>;
		microResults: Record<string, MicroResult>;
		onselect: (key: string) => void;
		onclose: () => void;
	}

	let { foods, existingKeys, microResults, onselect, onclose }: Props = $props();

	let query = $state('');

	let hasMicroData = $derived(Object.keys(microResults).length > 0);

	let results = $derived.by(() => {
		const q = query.toLowerCase().trim();
		let entries = Object.entries(foods).filter(([k]) => !existingKeys.has(k));

		if (q) {
			entries = entries
				.filter(([key, food]) => {
					const searchable = `${food.name} ${food.unit_note} ${food.category} ${key}`.toLowerCase();
					return searchable.includes(q);
				})
				.sort(([, a], [, b]) => {
					const aStarts = a.name.toLowerCase().startsWith(q) ? 0 : 1;
					const bStarts = b.name.toLowerCase().startsWith(q) ? 0 : 1;
					if (aStarts !== bStarts) return aStarts - bStarts;
					// Tiebreak by gap score
					if (hasMicroData) {
						return computeGapScore('', b, microResults) - computeGapScore('', a, microResults);
					}
					return 0;
				});
		} else if (hasMicroData) {
			entries = entries.sort(([, a], [, b]) => {
				return computeGapScore('', b, microResults) - computeGapScore('', a, microResults);
			});
		}

		return entries.slice(0, 16);
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
			bind:value={query}
			autofocus
		/>

		<div class="results">
			{#each results as [key, food]}
				{@const gaps = hasMicroData ? countGapsFilled(food, microResults) : 0}
				<button class="result-item" onclick={() => onselect(key)}>
					<span class="result-name">{food.name}</span>
					<span class="result-note">{food.unit_note}</span>
					<span class="result-macros">
						{food.cal_per_100g} kcal · {food.protein_per_100g}g pro · {food.fiber_per_100g}g fiber
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
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
		backdrop-filter: blur(2px);
	}

	.modal {
		background: #0f172a;
		border: 1px solid #1e293b;
		border-radius: 12px;
		width: 500px;
		max-height: 80vh;
		display: flex;
		flex-direction: column;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 16px 20px 0;
	}

	h3 {
		margin: 0;
		color: #e2e8f0;
		font-size: 16px;
	}

	.close-btn {
		background: none;
		border: none;
		color: #64748b;
		font-size: 22px;
		cursor: pointer;
		padding: 0 4px;
	}

	.close-btn:hover {
		color: #e2e8f0;
	}

	.search-input {
		margin: 12px 20px;
		padding: 10px 14px;
		background: #1e1e2e;
		border: 1px solid #334155;
		border-radius: 8px;
		color: #e2e8f0;
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
		color: #e2e8f0;
	}

	.result-item:hover {
		background: #1e293b;
	}

	.result-name {
		font-weight: 500;
	}

	.result-note {
		font-size: 12px;
		color: #64748b;
	}

	.result-macros {
		font-size: 12px;
		color: #64748b;
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
		color: #475569;
	}
</style>
