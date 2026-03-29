<script lang="ts">
	import type { Food, SolvedIngredient } from '$lib/api';
	import { jsPDF } from 'jspdf';

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
		weightLabel: string;
		category: string;
	}

	function formatWeight(g: number): { imperial: string; metric: string } {
		const lbs = g / 453.592;
		let imperial: string;
		if (lbs >= 1) {
			imperial = `${lbs.toFixed(1)} lb`;
		} else {
			imperial = `${Math.round(lbs * 16)} oz`;
		}
		const metric = g >= 1000 ? `${(g / 1000).toFixed(1)} kg` : `${Math.round(g)}g`;
		return { imperial, metric };
	}

	function formatQty(
		totalGrams: number,
		portion: { unit: string; g: number } | undefined
	): { qty: string; unit: string; weightLabel: string } {
		const { imperial, metric } = formatWeight(totalGrams);
		if (!portion) {
			return { qty: imperial, unit: '', weightLabel: `(${metric})` };
		}
		const count = totalGrams / portion.g;
		const rounded = Math.round(count * 2) / 2;
		if (rounded === 0) {
			return { qty: imperial, unit: '', weightLabel: `(${metric})` };
		}
		const qtyStr = rounded % 1 === 0 ? String(rounded) : rounded.toFixed(1);
		return { qty: qtyStr, unit: portion.unit, weightLabel: `(${metric} / ${imperial})` };
	}

	let groceryItems = $derived.by(() => {
		const items: GroceryItem[] = [];
		for (const ing of ingredients) {
			if (ing.grams <= 0) continue;
			const food = foods[ing.key];
			if (!food) continue;
			const totalGrams = ing.grams * days;
			const { qty, unit, weightLabel } = formatQty(totalGrams, food.portion);
			items.push({
				name: food.name,
				totalGrams,
				displayQty: qty,
				displayUnit: unit,
				weightLabel,
				category: food.category
			});
		}
		return items;
	});

	let grouped = $derived.by(() => {
		const groups = new Map<string, GroceryItem[]>();
		for (const item of groceryItems) {
			const cat = item.category || 'Other';
			if (!groups.has(cat)) groups.set(cat, []);
			groups.get(cat)!.push(item);
		}
		const sorted = [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
		for (const [, items] of sorted) {
			items.sort((a, b) => a.name.localeCompare(b.name));
		}
		return sorted;
	});

	let showMenu = $state(false);
	let copied = $state(false);
	let menuRef: HTMLDivElement | undefined = $state();

	function itemLine(item: GroceryItem): string {
		if (item.displayUnit) {
			return `${item.name} - ${item.displayQty} ${item.displayUnit} ${item.weightLabel}`;
		}
		return `${item.name} - ${item.displayQty} ${item.weightLabel}`;
	}

	function copyReminders() {
		const lines = groceryItems
			.slice()
			.sort((a, b) => a.name.localeCompare(b.name))
			.map(itemLine);
		navigator.clipboard.writeText(lines.join('\n'));
		flashCopied();
	}

	function copyFormatted() {
		let text = `Grocery List (${days} day${days === 1 ? '' : 's'})\n`;
		for (const [category, items] of grouped) {
			text += `\n${category}\n`;
			for (const item of items) {
				text += `  ${itemLine(item)}\n`;
			}
		}
		navigator.clipboard.writeText(text);
		flashCopied();
	}

	function flashCopied() {
		showMenu = false;
		copied = true;
		setTimeout(() => (copied = false), 2000);
	}

	function downloadMarkdown() {
		let md = `# Grocery List (${days} day${days === 1 ? '' : 's'})\n`;
		for (const [category, items] of grouped) {
			md += `\n## ${category}\n`;
			for (const item of items) {
				md += `- [ ] ${itemLine(item)}\n`;
			}
		}
		downloadFile(md, `grocery-list-${days}d.md`, 'text/markdown');
		showMenu = false;
	}

	function downloadPdf() {
		const doc = new jsPDF({ unit: 'pt', format: 'letter' });
		const pageWidth = doc.internal.pageSize.getWidth();
		const margin = 40;
		const maxWidth = pageWidth - margin * 2;
		let y = 50;

		doc.setFont('helvetica', 'bold');
		doc.setFontSize(18);
		doc.text(`Grocery List (${days} day${days === 1 ? '' : 's'})`, margin, y);
		y += 30;

		for (const [category, items] of grouped) {
			// Check if we need a new page (header + at least one item)
			if (y > 700) {
				doc.addPage();
				y = 50;
			}

			doc.setFont('helvetica', 'bold');
			doc.setFontSize(11);
			doc.setTextColor(120, 120, 120);
			doc.text(category.toUpperCase(), margin, y);
			y += 16;

			doc.setFont('helvetica', 'normal');
			doc.setFontSize(11);
			doc.setTextColor(30, 30, 30);

			for (const item of items) {
				if (y > 730) {
					doc.addPage();
					y = 50;
				}
				const line = itemLine(item);
				const lines = doc.splitTextToSize(line, maxWidth);
				doc.text(lines, margin + 8, y);
				y += lines.length * 14;
			}
			y += 8;
		}

		doc.save(`grocery-list-${days}d.pdf`);
		showMenu = false;
	}

	function downloadFile(content: string, filename: string, mime: string) {
		const blob = new Blob([content], { type: mime });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = filename;
		a.click();
		URL.revokeObjectURL(url);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			if (showMenu) {
				showMenu = false;
			} else {
				onclose();
			}
		}
	}

	function handleClickOutsideMenu(e: MouseEvent) {
		if (showMenu && menuRef && !menuRef.contains(e.target as Node)) {
			showMenu = false;
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="modal-overlay" onclick={onclose}>
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="modal" onclick={(e) => { e.stopPropagation(); handleClickOutsideMenu(e); }}>
		<div class="modal-header">
			<h3>Grocery List ({days} day{days === 1 ? '' : 's'})</h3>
			<div class="header-actions">
				<div class="export-wrapper" bind:this={menuRef}>
					<button class="export-btn" onclick={(e) => { e.stopPropagation(); showMenu = !showMenu; }}>
						{copied ? 'Copied!' : 'Export ▾'}
					</button>
					{#if showMenu}
						<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
						<div class="export-menu" onclick={(e) => e.stopPropagation()}>
							<button onclick={copyReminders}>Copy for Reminders</button>
							<button onclick={copyFormatted}>Copy formatted</button>
							<hr />
							<button onclick={downloadMarkdown}>Download Markdown</button>
							<button onclick={downloadPdf}>Download PDF</button>
						</div>
					{/if}
				</div>
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
									<span class="item-weight">{item.weightLabel}</span>
								{:else}
									<strong>{item.displayQty}</strong>
									<span class="item-weight">{item.weightLabel}</span>
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

	.export-wrapper {
		position: relative;
	}

	.export-btn {
		background: var(--accent);
		color: #fff;
		border: none;
		border-radius: 6px;
		padding: 5px 12px;
		font-size: 12px;
		font-weight: 500;
		cursor: pointer;
	}

	.export-btn:hover {
		filter: brightness(1.1);
	}

	.export-menu {
		position: absolute;
		top: 100%;
		right: 0;
		margin-top: 4px;
		background: var(--bg-panel);
		border: 1px solid var(--border);
		border-radius: 8px;
		box-shadow: 0 8px 24px var(--shadow-modal);
		min-width: 180px;
		z-index: 110;
		overflow: hidden;
	}

	.export-menu button {
		display: block;
		width: 100%;
		padding: 8px 14px;
		border: none;
		background: none;
		color: var(--text-primary);
		font-size: 13px;
		text-align: left;
		cursor: pointer;
	}

	.export-menu button:hover {
		background: var(--bg-hover);
	}

	.export-menu hr {
		margin: 0;
		border: none;
		border-top: 1px solid var(--border);
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

	.item-weight {
		color: var(--text-muted);
		font-size: 12px;
	}
</style>
