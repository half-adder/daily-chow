<script lang="ts">
	import { tick } from 'svelte';

	interface Props {
		label: string;
		mode: 'gte' | 'lte' | 'eq' | 'none';
		grams: number;
		hard: boolean;
		onchange: (mode: string, grams: number, hard: boolean) => void;
	}

	let { label, mode, grams, hard, onchange }: Props = $props();

	const MODES: readonly string[] = ['gte', 'lte', 'eq', 'none'];
	const SYMBOLS: Record<string, string> = { gte: '\u2265', lte: '\u2264', eq: '=', none: '\u2014' };

	let animating = $state(false);
	let trackEl = $state<HTMLDivElement | null>(null);

	function currentIndex(): number {
		return MODES.indexOf(mode);
	}

	function prevSymbol(): string {
		return SYMBOLS[MODES[(currentIndex() - 1 + MODES.length) % MODES.length]];
	}

	function nextSymbol(): string {
		return SYMBOLS[MODES[(currentIndex() + 1) % MODES.length]];
	}

	async function cycleMode() {
		if (animating || !trackEl) return;
		animating = true;

		const nextIdx = (currentIndex() + 1) % MODES.length;

		// Instantly position new items shifted down (no transition)
		trackEl.style.transition = 'none';
		trackEl.style.transform = 'translateY(20px)';

		// Change mode — new items render
		onchange(MODES[nextIdx], grams, hard);
		await tick();

		// Force reflow so browser registers the shifted position
		trackEl.offsetHeight;

		// Animate from shifted position to center
		trackEl.style.transition = '';
		trackEl.style.transform = '';

		setTimeout(() => { animating = false; }, 200);
	}

	function toggleHard() {
		if (mode === 'none') return;
		onchange(mode, grams, !hard);
	}

	function onGramsInput(e: Event) {
		const val = parseInt((e.target as HTMLInputElement).value);
		if (!isNaN(val) && val >= 0) {
			onchange(mode, val, hard);
		}
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="mc-row" class:disabled={mode === 'none'}>
	<span class="mc-label">{label}</span>
	<div class="wheel-container" onclick={cycleMode}>
		<div class="wheel-track" bind:this={trackEl}>
			<span class="wheel-item">{prevSymbol()}</span>
			<span class="wheel-item">{SYMBOLS[mode]}</span>
			<span class="wheel-item">{nextSymbol()}</span>
		</div>
	</div>
	<span
		class="lock-icon"
		class:locked={hard}
		class:unlocked={!hard}
		class:lock-disabled={mode === 'none'}
		onclick={toggleHard}
		title={mode === 'none' ? 'No constraint' : hard ? 'Hard constraint (click for loose)' : 'Loose constraint (click for hard)'}
	>
		{#if hard}
			<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
				<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
				<path d="M7 11V7a5 5 0 0 1 10 0v4"/>
			</svg>
		{:else}
			<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
				<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
				<path d="M7 11V7a5 5 0 0 1 9.9-1"/>
			</svg>
		{/if}
	</span>
	<input
		class="mc-input"
		type="number"
		value={grams}
		disabled={mode === 'none'}
		onchange={onGramsInput}
	/>
	<span class="mc-unit">g</span>
</div>

<style>
	.mc-row {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.mc-row.disabled .mc-input,
	.mc-row.disabled .mc-unit {
		opacity: 0.3;
	}

	.mc-label {
		font-size: 12px;
		color: var(--text-muted, #a3a3a3);
		min-width: 52px;
		font-weight: 500;
		text-align: right;
	}

	.wheel-container {
		width: 24px;
		height: 60px;
		overflow: hidden;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		position: relative;
		user-select: none;
		-webkit-mask-image: linear-gradient(to bottom, transparent 0%, black 25%, black 75%, transparent 100%);
		mask-image: linear-gradient(to bottom, transparent 0%, black 25%, black 75%, transparent 100%);
	}

	.wheel-track {
		display: flex;
		flex-direction: column;
		align-items: center;
		transition: transform 0.2s ease-out;
	}

	.wheel-item {
		font-weight: 700;
		font-size: 16px;
		height: 20px;
		line-height: 20px;
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--text, #e5e5e5);
	}

	.lock-icon {
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
	}

	.lock-icon.locked {
		color: #22c55e;
	}

	.lock-icon.unlocked {
		color: #f59e0b;
	}

	.lock-icon.lock-disabled {
		opacity: 0.3;
		pointer-events: none;
	}

	.mc-input {
		width: 52px;
		background: var(--input-bg, #27272a);
		color: var(--text, #e5e5e5);
		border: 1px solid var(--border, #3f3f46);
		border-radius: 4px;
		padding: 2px 4px;
		font-size: 13px;
		text-align: right;
		-moz-appearance: textfield;
	}

	.mc-input::-webkit-outer-spin-button,
	.mc-input::-webkit-inner-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}

	.mc-input:disabled {
		cursor: not-allowed;
	}

	.mc-unit {
		font-size: 12px;
		color: var(--text-muted, #a3a3a3);
	}
</style>
