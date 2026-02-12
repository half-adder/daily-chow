<script lang="ts">
	import DualRangeSlider from './DualRangeSlider.svelte';
	import type { Food, SolvedIngredient } from '$lib/api';

	interface Props {
		ingredientKey: string;
		food: Food;
		enabled: boolean;
		minG: number;
		maxG: number;
		solved?: SolvedIngredient | null;
		onchange?: () => void;
		onremove?: () => void;
		ontoggle?: (enabled: boolean) => void;
	}

	let {
		ingredientKey,
		food,
		enabled = $bindable(true),
		minG = $bindable(0),
		maxG = $bindable(500),
		solved = null,
		onchange,
		onremove,
		ontoggle
	}: Props = $props();

	function handleToggle() {
		enabled = !enabled;
		ontoggle?.(enabled);
	}

	function handleSliderChange(newMin: number, newMax: number) {
		minG = newMin;
		maxG = newMax;
		onchange?.();
	}

	function handleMinInput(e: Event) {
		const val = parseInt((e.target as HTMLInputElement).value);
		if (!isNaN(val) && val >= 0) {
			minG = Math.min(val, maxG);
			onchange?.();
		}
	}

	function handleMaxInput(e: Event) {
		const val = parseInt((e.target as HTMLInputElement).value);
		if (!isNaN(val) && val >= 0) {
			maxG = Math.max(val, minG);
			onchange?.();
		}
	}
</script>

<div class="ingredient-row" class:disabled={!enabled}>
	<label class="checkbox-cell">
		<input type="checkbox" checked={enabled} onchange={handleToggle} />
	</label>

	<div class="name-cell">
		<span class="name">{food.name}</span>
		<span class="unit-note">{food.unit_note}</span>
	</div>

	<input
		type="number"
		class="bound-input"
		value={minG}
		onchange={handleMinInput}
		min="0"
		disabled={!enabled}
	/>

	<div class="slider-cell">
		<DualRangeSlider
			bind:min={minG}
			bind:max={maxG}
			absMin={0}
			absMax={food.default_max}
			solvedValue={solved?.grams ?? null}
			onchange={handleSliderChange}
		/>
	</div>

	<input
		type="number"
		class="bound-input"
		value={maxG}
		onchange={handleMaxInput}
		min="0"
		disabled={!enabled}
	/>

	<div class="solved-cell">
		{#if solved}
			<span class="solved-grams">{solved.grams}g</span>
		{:else}
			<span class="solved-none">—</span>
		{/if}
	</div>

	<div class="macros-cell">
		{#if solved}
			<span class="macro-cal">{Math.round(solved.calories)}</span>
			<span class="macro-sep">/</span>
			<span class="macro-pro">{Math.round(solved.protein)}g</span>
		{/if}
	</div>

	<button class="remove-btn" onclick={onremove} title="Remove ingredient">×</button>
</div>

<style>
	.ingredient-row {
		display: grid;
		grid-template-columns: 32px 180px 64px 1fr 64px 72px 100px 32px;
		align-items: center;
		gap: 8px;
		padding: 8px 12px;
		border-bottom: 1px solid #1e1e1e;
		transition: opacity 0.15s;
	}

	.ingredient-row:hover {
		background: #1a1a2e;
	}

	.ingredient-row.disabled {
		opacity: 0.4;
	}

	.checkbox-cell {
		display: flex;
		justify-content: center;
	}

	input[type='checkbox'] {
		width: 16px;
		height: 16px;
		accent-color: #3b82f6;
		cursor: pointer;
	}

	.name-cell {
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.name {
		font-weight: 500;
		color: #e2e8f0;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.unit-note {
		font-size: 11px;
		color: #64748b;
	}

	.bound-input {
		box-sizing: border-box;
		width: 100%;
		padding: 4px 6px;
		background: #1e1e1e;
		border: 1px solid #333;
		border-radius: 4px;
		color: #94a3b8;
		font-size: 13px;
		font-variant-numeric: tabular-nums;
		text-align: right;
	}

	.bound-input:focus {
		border-color: #3b82f6;
		outline: none;
	}

	.bound-input:disabled {
		opacity: 0.3;
	}

	/* Hide number input spinners */
	.bound-input::-webkit-inner-spin-button,
	.bound-input::-webkit-outer-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}
	.bound-input {
		-moz-appearance: textfield;
	}

	.slider-cell {
		min-width: 0;
		padding: 0 10px;
	}

	.solved-cell {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}

	.solved-grams {
		font-weight: 700;
		color: #22c55e;
		font-size: 15px;
	}

	.solved-none {
		color: #475569;
	}

	.macros-cell {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		font-size: 13px;
		font-variant-numeric: tabular-nums;
		color: #64748b;
	}

	.macro-cal {
		color: #f59e0b;
		text-align: right;
	}

	.macro-sep {
		color: #334155;
		text-align: center;
		padding: 0 4px;
	}

	.macro-pro {
		color: #3b82f6;
		text-align: left;
	}

	.remove-btn {
		background: none;
		border: none;
		color: #475569;
		font-size: 18px;
		cursor: pointer;
		padding: 0;
		line-height: 1;
		border-radius: 4px;
	}

	.remove-btn:hover {
		color: #ef4444;
		background: rgba(239, 68, 68, 0.1);
	}
</style>
