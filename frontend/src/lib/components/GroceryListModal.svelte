<script lang="ts">
	import type { Food, SolvedIngredient } from '$lib/api';

	interface Props {
		ingredients: SolvedIngredient[];
		foods: Record<number, Food>;
		days: number;
		onclose: () => void;
	}

	let { ingredients, foods, days, onclose }: Props = $props();

	interface GroceryItem {
		name: string;
		totalGrams: number;
		displayQty: string;
		displayUnit: string;
		category: string;
	}

	function formatGrams(g: number): string {
		const lbs = g / 453.592;
		if (lbs >= 1) return `${lbs.toFixed(1)} lb`;
		const oz = lbs * 16;
		return `${Math.round(oz)} oz`;
	}

	function formatQty(totalGrams: number, portion: { unit: string; g: number } | undefined): { qty: string; unit: string } {
		if (!portion) {
			return { qty: formatGrams(totalGrams), unit: '' };
		}
		const count = totalGrams / portion.g;
		// Round to nearest 0.5
		const rounded = Math.round(count * 2) / 2;
		if (rounded === 0) return { qty: formatGrams(totalGrams), unit: '' };
		const qtyStr = rounded % 1 === 0 ? String(rounded) : rounded.toFixed(1);
		return { qty: qtyStr, unit: portion.unit };
	}

	let groceryItems = $derived.by(() => {
		const items: GroceryItem[] = [];
		for (const ing of ingredients) {
			if (ing.grams <= 0) continue;
			const food = foods[ing.key];
			if (!food) continue;
			const totalGrams = ing.grams * days;
			const { qty, unit } = formatQty(totalGrams, food.portion);
			items.push({
				name: food.name,
				totalGrams,
				displayQty: qty,
				displayUnit: unit,
				category: food.category,
			});
		}
		return items;
	});

	// Group by category
	let grouped = $derived.by(() => {
		const groups = new Map<string, GroceryItem[]>();
		for (const item of groceryItems) {
			const cat = item.category || 'Other';
			if (!groups.has(cat)) groups.set(cat, []);
			groups.get(cat)!.push(item);
		}
		// Sort categories alphabetically, sort items within each category by name
		const sorted = [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
		for (const [, items] of sorted) {
			items.sort((a, b) => a.name.localeCompare(b.name));
		}
		return sorted;
	});

	let copied = $state(false);

	function copyToClipboard() {
		let text = `Grocery List (${days} day${days === 1 ? '' : 's'})\n`;
		for (const [category, items] of grouped) {
			text += `\n${category}\n`;
			for (const item of items) {
				if (item.displayUnit) {
					text += `  ${item.name} - ${item.displayQty} ${item.displayUnit} (${formatGrams(item.totalGrams)})\n`;
				} else {
					text += `  ${item.name} - ${item.displayQty}\n`;
				}
			}
		}
		navigator.clipboard.writeText(text);
		copied = true;
		setTimeout(() => (copied = false), 2000);
	}

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
			<h3>Grocery List ({days} day{days === 1 ? '' : 's'})</h3>
			<div class="header-actions">
				<button class="copy-btn" onclick={copyToClipboard}>
					{copied ? 'Copied!' : 'Copy'}
				</button>
				<button class="close-btn" onclick={onclose}>&times;</button>
			</div>
		</div>

		<div class="modal-body">
			{#each grouped as [category, items]}
				<div class="category-group">
					<h4>{category}</h4>
					{#each items as item}
						<div class="grocery-item">
							<span class="item-name">{item.name}</span>
							<span class="item-qty">
								{#if item.displayUnit}
									<strong>{item.displayQty}</strong> {item.displayUnit}
									<span class="item-grams">({formatGrams(item.totalGrams)})</span>
								{:else}
									<strong>{item.displayQty}</strong>
								{/if}
							</span>
						</div>
					{/each}
				</div>
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
		width: 480px;
		max-width: 95vw;
		max-height: 80vh;
		display: flex;
		flex-direction: column;
		box-shadow: 0 20px 60px var(--shadow-modal);
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 16px 20px 12px;
		border-bottom: 1px solid var(--border);
	}

	h3 {
		margin: 0;
		color: var(--text-primary);
		font-size: 16px;
	}

	.header-actions {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.copy-btn {
		background: var(--accent);
		color: #fff;
		border: none;
		border-radius: 6px;
		padding: 5px 12px;
		font-size: 12px;
		font-weight: 500;
		cursor: pointer;
	}

	.copy-btn:hover {
		filter: brightness(1.1);
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

	.modal-body {
		padding: 12px 20px 20px;
		overflow-y: auto;
	}

	.category-group {
		margin-bottom: 16px;
	}

	.category-group:last-child {
		margin-bottom: 0;
	}

	h4 {
		margin: 0 0 6px;
		font-size: 12px;
		font-weight: 600;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.grocery-item {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		padding: 4px 0;
		font-size: 14px;
	}

	.item-name {
		color: var(--text-primary);
	}

	.item-qty {
		color: var(--text-secondary);
		font-size: 13px;
		text-align: right;
		white-space: nowrap;
	}

	.item-qty strong {
		color: var(--text-primary);
	}

	.item-grams {
		color: var(--text-muted);
		font-size: 12px;
	}
</style>
