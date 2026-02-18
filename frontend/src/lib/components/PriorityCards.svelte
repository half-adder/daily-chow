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
			onEnd: (evt) => {
				const newOrder = Array.from(listEl!.children).map(
					(el) => (el as HTMLElement).dataset.key!
				);
				// Revert SortableJS DOM mutation so Svelte can reconcile cleanly
				if (evt.oldIndex !== undefined && evt.newIndex !== undefined && evt.item.parentNode) {
					const parent = evt.item.parentNode;
					parent.removeChild(evt.item);
					const ref = parent.children[evt.oldIndex];
					if (ref) {
						parent.insertBefore(evt.item, ref);
					} else {
						parent.appendChild(evt.item);
					}
				}
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
			<span class="priority-card-label">{LABELS[p] ?? p}</span>
		</div>
	{/each}
</div>

<style>
	.priority-cards {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.priority-card {
		display: flex;
		align-items: center;
		gap: 4px;
		padding: 3px 5px;
		background: var(--bg-panel);
		border: 1px solid var(--border-input);
		border-radius: 4px;
		font-size: 11px;
		touch-action: none;
		user-select: none;
	}

	.drag-handle {
		cursor: grab;
		color: var(--text-muted);
		font-size: 11px;
		line-height: 1;
		flex-shrink: 0;
	}

	@media (min-width: 1200px) {
		.priority-cards { gap: 6px; }
		.priority-card { gap: 6px; padding: 8px 10px; border-radius: 6px; font-size: 13px; }
		.drag-handle { font-size: 14px; }
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
		background: var(--bg-panel) !important;
	}
</style>
