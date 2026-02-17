<script lang="ts">
	import DualRangeSlider from './DualRangeSlider.svelte';
	import type { Food, SolvedIngredient } from '$lib/api';
	import type { IngredientContribution } from '$lib/contributions';

	interface Props {
		ingredientKey: number;
		food: Food;
		color: string;
		enabled: boolean;
		minG: number;
		maxG: number;
		absMax?: number;
		solved?: SolvedIngredient | null;
		contribution?: IngredientContribution | null;
		expanded?: boolean;
		onchange?: () => void;
		onremove?: () => void;
		ontoggle?: (enabled: boolean) => void;
		onexpand?: () => void;
	}

	let {
		ingredientKey,
		food,
		color,
		enabled = $bindable(true),
		minG = $bindable(0),
		maxG = $bindable(500),
		absMax = 500,
		solved = null,
		contribution = null,
		expanded = false,
		onchange,
		onremove,
		ontoggle,
		onexpand
	}: Props = $props();

	// Top micro contributions (>10% DRI) sorted descending
	let topMicros = $derived.by(() => {
		if (!contribution) return [];
		return Object.entries(contribution.micros)
			.filter(([, mc]) => mc.driPct > 10)
			.sort(([, a], [, b]) => b.driPct - a.driPct)
			.slice(0, 8);
	});

	const MICRO_NAMES: Record<string, string> = {
		calcium_mg: 'Calcium',
		iron_mg: 'Iron',
		magnesium_mg: 'Magnesium',
		phosphorus_mg: 'Phosphorus',
		potassium_mg: 'Potassium',
		zinc_mg: 'Zinc',
		copper_mg: 'Copper',
		manganese_mg: 'Manganese',
		selenium_mcg: 'Selenium',
		vitamin_c_mg: 'Vitamin C',
		thiamin_mg: 'B1',
		riboflavin_mg: 'B2',
		niacin_mg: 'B3',
		vitamin_b6_mg: 'B6',
		folate_mcg: 'Folate',
		vitamin_b12_mcg: 'B12',
		vitamin_a_mcg: 'Vit A',
		vitamin_d_mcg: 'Vit D',
		vitamin_e_mg: 'Vit E',
		vitamin_k_mcg: 'Vit K'
	};

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
		if (!isNaN(val)) {
			minG = Math.min(Math.max(val, 0), maxG);
			onchange?.();
		}
	}

	function handleMaxInput(e: Event) {
		const val = parseInt((e.target as HTMLInputElement).value);
		if (!isNaN(val)) {
			maxG = Math.max(val, minG, 0);
			onchange?.();
		}
	}

	function handleRowClick(e: MouseEvent) {
		// Don't expand if clicking interactive elements
		const target = e.target as HTMLElement;
		if (target.closest('input') || target.closest('button') || target.closest('.slider-cell')) return;
		onexpand?.();
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="ingredient-wrapper">
	<div class="ingredient-row" class:disabled={!enabled} class:expanded onclick={handleRowClick}>
		<label class="checkbox-cell">
			<input type="checkbox" checked={enabled} onchange={handleToggle} />
		</label>

		<div class="name-cell">
			<div class="name-row">
				<span class="color-swatch" style="background: {color}"></span>
				<span class="name">{food.name}</span>
			</div>
			{#if food.subtitle}<span class="unit-note">{food.subtitle}</span>{/if}
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
				{absMax}
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
				<span class="solved-grams">{Math.round(solved.grams)}g</span>
			{:else}
				<span class="solved-none">—</span>
			{/if}
		</div>

		<div class="macros-cell">
			{#if solved}
				<span class="macro-cal">{Math.round(solved.calories_kcal)}</span>
				<span class="macro-sep">/</span>
				<span class="macro-pro">{Math.round(solved.protein_g)}g</span>
			{/if}
		</div>

		<button class="remove-btn" onclick={onremove} title="Remove ingredient">×</button>
	</div>

	{#if expanded && contribution && solved}
		<div class="detail-panel">
			<div class="detail-macros">
				<h4>Macro Contribution</h4>
				{#each [
					{ label: 'Calories', pct: contribution.macroPcts.cal, color: '#f59e0b' },
					{ label: 'Protein', pct: contribution.macroPcts.pro, color: '#3b82f6' },
					{ label: 'Fat', pct: contribution.macroPcts.fat, color: '#a855f7' },
					{ label: 'Carbs', pct: contribution.macroPcts.carb, color: '#f59e0b' },
					{ label: 'Fiber', pct: contribution.macroPcts.fiber, color: '#22c55e' },
				] as row}
					<div class="detail-bar-row">
						<span class="detail-bar-label">{row.label}</span>
						<div class="detail-bar-track">
							<div class="detail-bar-fill" style="width: {Math.min(row.pct, 100)}%; background: {row.color}"></div>
						</div>
						<span class="detail-bar-pct">{Math.round(row.pct)}%</span>
					</div>
				{/each}
			</div>
			{#if topMicros.length > 0}
				<div class="detail-micros">
					<h4>Top Micronutrients</h4>
					{#each topMicros as [key, mc]}
						<div class="detail-bar-row">
							<span class="detail-bar-label">{MICRO_NAMES[key] ?? key}</span>
							<div class="detail-bar-track">
								<div class="detail-bar-fill" style="width: {Math.min(mc.driPct, 100)}%; background: {mc.driPct >= 50 ? '#22c55e' : '#f59e0b'}"></div>
							</div>
							<span class="detail-bar-pct">{Math.round(mc.driPct)}%</span>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.ingredient-wrapper {
		border-bottom: 1px solid var(--border-row);
	}

	.ingredient-row {
		display: grid;
		grid-template-columns: 32px 180px 64px 1fr 64px 72px 100px 32px;
		align-items: center;
		gap: 8px;
		padding: 8px 12px;
		transition: opacity 0.15s;
		cursor: pointer;
	}

	.ingredient-row:hover {
		background: var(--bg-hover);
	}

	.ingredient-row.disabled {
		opacity: 0.4;
	}

	.ingredient-row.expanded {
		background: var(--bg-hover);
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

	.name-row {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.color-swatch {
		width: 10px;
		height: 10px;
		border-radius: 3px;
		flex-shrink: 0;
	}

	.name {
		font-weight: 500;
		color: var(--text-primary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.unit-note {
		font-size: 11px;
		color: var(--text-muted);
		padding-left: 16px;
	}

	.bound-input {
		box-sizing: border-box;
		width: 100%;
		padding: 4px 6px;
		background: var(--bg-input);
		border: 1px solid var(--border-input);
		border-radius: 4px;
		color: var(--text-secondary);
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
		color: var(--text-dim);
	}

	.macros-cell {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		font-size: 13px;
		font-variant-numeric: tabular-nums;
		color: var(--text-muted);
	}

	.macro-cal {
		color: #f59e0b;
		text-align: right;
	}

	.macro-sep {
		color: var(--border-input);
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
		color: var(--text-dim);
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

	/* ── Detail panel ─────────────────────────────── */

	.detail-panel {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 20px;
		padding: 12px 20px 16px 52px;
		background: var(--bg-detail);
		border-top: 1px solid var(--border);
	}

	.detail-panel h4 {
		margin: 0 0 8px;
		font-size: 11px;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.detail-bar-row {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 2px 0;
	}

	.detail-bar-label {
		font-size: 12px;
		color: var(--text-secondary);
		width: 60px;
		flex-shrink: 0;
	}

	.detail-bar-track {
		flex: 1;
		height: 6px;
		background: var(--bg-track);
		border-radius: 3px;
		overflow: hidden;
	}

	.detail-bar-fill {
		height: 100%;
		border-radius: 3px;
		transition: width 0.3s ease;
		min-width: 1px;
	}

	.detail-bar-pct {
		font-size: 12px;
		font-weight: 600;
		color: var(--text-secondary);
		width: 32px;
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
</style>
