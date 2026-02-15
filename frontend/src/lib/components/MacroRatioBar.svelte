<script lang="ts">
	interface Props {
		carbPct: number;
		proteinPct: number;
		fatPct: number;
		disabledSegments?: Set<string>;
		onchange: (carb: number, protein: number, fat: number) => void;
	}

	let { carbPct, proteinPct, fatPct, disabledSegments = new Set(), onchange }: Props = $props();

	let barEl = $state<HTMLDivElement | null>(null);
	let dragging = $state<'cp' | 'pf' | null>(null);
	let editingSegment = $state<'carb' | 'protein' | 'fat' | null>(null);
	let editValue = $state('');

	const MIN_PCT = 5;

	function clamp(v: number, min: number, max: number) {
		return Math.max(min, Math.min(max, v));
	}

	function startDrag(handle: 'cp' | 'pf', e: PointerEvent) {
		if (handle === 'cp' && (disabledSegments.has('carbs') || disabledSegments.has('protein'))) return;
		if (handle === 'pf' && (disabledSegments.has('protein') || disabledSegments.has('fat'))) return;
		dragging = handle;
		(e.target as HTMLElement).setPointerCapture(e.pointerId);
		e.preventDefault();
	}

	function onPointerMove(e: PointerEvent) {
		if (!dragging || !barEl) return;
		const rect = barEl.getBoundingClientRect();
		const pct = clamp(((e.clientX - rect.left) / rect.width) * 100, 0, 100);

		if (dragging === 'cp') {
			const newCarb = clamp(Math.round(pct), MIN_PCT, 100 - fatPct - MIN_PCT);
			const newProtein = 100 - newCarb - fatPct;
			if (newProtein >= MIN_PCT) {
				onchange(newCarb, newProtein, fatPct);
			}
		} else {
			const newFat = clamp(Math.round(100 - pct), MIN_PCT, 100 - carbPct - MIN_PCT);
			const newProtein = 100 - carbPct - newFat;
			if (newProtein >= MIN_PCT) {
				onchange(carbPct, newProtein, newFat);
			}
		}
	}

	function onPointerUp() {
		dragging = null;
	}

	function startEdit(segment: 'carb' | 'protein' | 'fat') {
		const nutrientName = segment === 'carb' ? 'carbs' : segment;
		if (disabledSegments.has(nutrientName)) return;
		editingSegment = segment;
		if (segment === 'carb') editValue = String(carbPct);
		else if (segment === 'protein') editValue = String(proteinPct);
		else editValue = String(fatPct);
	}

	function commitEdit() {
		if (!editingSegment) return;
		const val = parseInt(editValue);
		if (isNaN(val) || val < MIN_PCT) { editingSegment = null; return; }

		if (editingSegment === 'carb') {
			const newCarb = clamp(val, MIN_PCT, 100 - MIN_PCT * 2);
			const newProtein = clamp(100 - newCarb - fatPct, MIN_PCT, 100 - newCarb - MIN_PCT);
			const newFat = 100 - newCarb - newProtein;
			onchange(newCarb, newProtein, newFat);
		} else if (editingSegment === 'protein') {
			const newProtein = clamp(val, MIN_PCT, 100 - MIN_PCT * 2);
			const newFat = clamp(100 - carbPct - newProtein, MIN_PCT, 100 - carbPct - MIN_PCT);
			const newCarb = 100 - newProtein - newFat;
			onchange(newCarb, newProtein, newFat);
		} else {
			const newFat = clamp(val, MIN_PCT, 100 - MIN_PCT * 2);
			const newProtein = clamp(100 - carbPct - newFat, MIN_PCT, 100 - carbPct - MIN_PCT);
			const newCarb = 100 - newProtein - newFat;
			onchange(newCarb, newProtein, newFat);
		}
		editingSegment = null;
	}

	function onEditKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') commitEdit();
		if (e.key === 'Escape') editingSegment = null;
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="ratio-bar"
	bind:this={barEl}
	onpointermove={onPointerMove}
	onpointerup={onPointerUp}
>
	<div class="ratio-segment carb" class:segment-disabled={disabledSegments.has('carbs')} style="width: {carbPct}%">
		{#if editingSegment === 'carb'}
			<!-- svelte-ignore a11y_autofocus -->
			<input
				class="ratio-edit"
				type="number"
				bind:value={editValue}
				onblur={commitEdit}
				onkeydown={onEditKeydown}
				autofocus
			/>
		{:else if carbPct >= 15}
			<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
			<span class="ratio-label" onclick={() => startEdit('carb')}>Carb: {carbPct}%</span>
		{/if}
	</div>

	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="ratio-grip" onpointerdown={(e) => startDrag('cp', e)}>
		<div class="grip-lines"><div></div><div></div></div>
	</div>

	<div class="ratio-segment protein" class:segment-disabled={disabledSegments.has('protein')} style="width: {proteinPct}%">
		{#if editingSegment === 'protein'}
			<!-- svelte-ignore a11y_autofocus -->
			<input
				class="ratio-edit"
				type="number"
				bind:value={editValue}
				onblur={commitEdit}
				onkeydown={onEditKeydown}
				autofocus
			/>
		{:else if proteinPct >= 15}
			<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
			<span class="ratio-label" onclick={() => startEdit('protein')}>Pro: {proteinPct}%</span>
		{/if}
	</div>

	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="ratio-grip" onpointerdown={(e) => startDrag('pf', e)}>
		<div class="grip-lines"><div></div><div></div></div>
	</div>

	<div class="ratio-segment fat" class:segment-disabled={disabledSegments.has('fat')} style="width: {fatPct}%">
		{#if editingSegment === 'fat'}
			<!-- svelte-ignore a11y_autofocus -->
			<input
				class="ratio-edit"
				type="number"
				bind:value={editValue}
				onblur={commitEdit}
				onkeydown={onEditKeydown}
				autofocus
			/>
		{:else if fatPct >= 15}
			<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
			<span class="ratio-label" onclick={() => startEdit('fat')}>Fat: {fatPct}%</span>
		{/if}
	</div>
</div>

<style>
	.ratio-bar {
		display: flex;
		align-items: center;
		height: 32px;
		border-radius: 6px;
		overflow: visible;
		width: 100%;
		position: relative;
		user-select: none;
		touch-action: none;
	}

	.ratio-segment {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
		min-width: 0;
		transition: width 0.1s ease;
		position: relative;
	}

	.ratio-segment.segment-disabled {
		opacity: 0.35;
		filter: grayscale(0.8);
	}

	.ratio-segment.carb {
		background: #f59e0b;
		border-radius: 6px 0 0 6px;
	}

	.ratio-segment.protein {
		background: #3b82f6;
	}

	.ratio-segment.fat {
		background: #a855f7;
		border-radius: 0 6px 6px 0;
	}

	.ratio-label {
		font-size: 12px;
		font-weight: 600;
		color: #fff;
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
		cursor: text;
		white-space: nowrap;
		padding: 0 4px;
	}

	.ratio-edit {
		width: 40px;
		font-size: 12px;
		font-weight: 600;
		text-align: center;
		border: 1px solid rgba(255, 255, 255, 0.5);
		border-radius: 3px;
		background: rgba(0, 0, 0, 0.2);
		color: #fff;
		outline: none;
		padding: 1px 2px;
		-moz-appearance: textfield;
	}

	.ratio-edit::-webkit-outer-spin-button,
	.ratio-edit::-webkit-inner-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}

	.ratio-grip {
		width: 12px;
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: col-resize;
		z-index: 2;
		flex-shrink: 0;
		margin: 0 -6px;
		position: relative;
	}

	.grip-lines {
		display: flex;
		gap: 2px;
		pointer-events: none;
	}

	.grip-lines div {
		width: 2px;
		height: 16px;
		background: rgba(255, 255, 255, 0.7);
		border-radius: 1px;
	}
</style>
