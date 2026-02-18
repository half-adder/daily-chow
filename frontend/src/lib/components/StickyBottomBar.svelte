<script lang="ts">
	import type { SolveResponse } from '$lib/api';

	interface Props {
		solution: SolveResponse | null;
		pinnedTotals: Record<string, number>;
		conflictReason: string | null;
		expanded: boolean;
		ontoggle: () => void;
	}

	let { solution, pinnedTotals, conflictReason, expanded, ontoggle }: Props = $props();

	let dayCal = $derived(
		solution ? Math.round(solution.meal_calories_kcal + (pinnedTotals.calories_kcal ?? 0)) : 0
	);
	let dayPro = $derived(
		solution ? Math.round(solution.meal_protein_g + (pinnedTotals.protein_g ?? 0)) : 0
	);
	let dayFib = $derived(
		solution ? Math.round(solution.meal_fiber_g + (pinnedTotals.fiber_g ?? 0)) : 0
	);
	let isFeasible = $derived(solution ? solution.status !== 'infeasible' : false);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
{#if solution}
	<div class="sticky-bar" onclick={ontoggle}>
		<span class="bar-cal">{dayCal} kcal</span>
		<span class="bar-pro">{dayPro}g pro</span>
		<span class="bar-fib">{dayFib}g fib</span>
		<span class="bar-status" class:feasible={isFeasible} class:infeasible={!isFeasible}>
			{isFeasible ? '✓' : '✗'}
		</span>
		<span class="bar-chevron" class:open={expanded}>▲</span>
	</div>
{/if}

{#if expanded}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="overlay" onclick={ontoggle}></div>
{/if}

<style>
	.sticky-bar {
		display: none;
	}

	.overlay {
		display: none;
	}

	@media (max-width: 768px) {
		.sticky-bar {
			display: flex;
			align-items: center;
			justify-content: center;
			gap: 12px;
			position: fixed;
			bottom: 0;
			left: 0;
			right: 0;
			z-index: 100;
			background: var(--bg-panel);
			border-top: 1px solid var(--border);
			padding: 10px 16px;
			font-size: 14px;
			font-weight: 500;
			font-variant-numeric: tabular-nums;
			cursor: pointer;
			-webkit-backdrop-filter: blur(12px);
			backdrop-filter: blur(12px);
		}

		.bar-cal { color: #f59e0b; }
		.bar-pro { color: #3b82f6; }
		.bar-fib { color: #22c55e; }

		.bar-status {
			font-weight: 700;
			font-size: 16px;
		}

		.bar-status.feasible { color: #22c55e; }
		.bar-status.infeasible { color: #ef4444; }

		.bar-chevron {
			font-size: 10px;
			color: var(--text-muted);
			transition: transform 0.2s;
		}

		.bar-chevron.open {
			transform: rotate(180deg);
		}

		.overlay {
			display: block;
			position: fixed;
			inset: 0;
			z-index: 90;
			background: rgba(0, 0, 0, 0.4);
		}
	}
</style>
