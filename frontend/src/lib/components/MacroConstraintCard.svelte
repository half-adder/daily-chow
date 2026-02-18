<script lang="ts">
	interface Props {
		label: string;
		mode: 'gte' | 'lte' | 'eq' | 'none';
		grams: number;
		hard: boolean;
		onchange: (mode: string, grams: number, hard: boolean) => void;
	}

	let { label, mode, grams, hard, onchange }: Props = $props();

	const SYMBOLS: Record<string, string> = { gte: '≥', lte: '≤', eq: '=' };
	const CYCLE: Array<'gte' | 'lte' | 'eq'> = ['gte', 'lte', 'eq'];

	let lastActiveMode = $state<'gte' | 'lte' | 'eq'>('gte');

	$effect(() => {
		if (mode !== 'none') {
			lastActiveMode = mode as 'gte' | 'lte' | 'eq';
		}
	});

	function toggleOn(checked: boolean) {
		if (!checked) {
			onchange('none', grams, hard);
		} else {
			onchange(lastActiveMode, grams, hard);
		}
	}

	function cycleMode() {
		if (mode === 'none') return;
		const idx = CYCLE.indexOf(mode as 'gte' | 'lte' | 'eq');
		const next = CYCLE[(idx + 1) % CYCLE.length];
		onchange(next, grams, hard);
	}

	function onGramsInput(e: Event) {
		const val = parseInt((e.target as HTMLInputElement).value);
		if (!isNaN(val) && val >= 0) {
			onchange(mode, val, hard);
		}
	}

	function toggleHard(checked: boolean) {
		onchange(mode, grams, checked);
	}
</script>

<div class="mc-card" class:disabled={mode === 'none'}>
	<!-- Header -->
	<div class="mc-header">
		<span class="mc-label">{label}</span>
		<label class="toggle-switch">
			<input
				type="checkbox"
				checked={mode !== 'none'}
				onchange={(e) => toggleOn((e.target as HTMLInputElement).checked)}
			/>
			<span class="toggle-track">
				<span class="toggle-thumb"></span>
			</span>
			<span class="toggle-label">{mode !== 'none' ? 'ON' : 'OFF'}</span>
		</label>
	</div>

	<div class="mc-divider"></div>

	<!-- Body -->
	<div class="mc-body">
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
		<span class="mc-symbol" onclick={cycleMode} title="Tap to cycle: ≥ → ≤ → =">
			{mode === 'none' ? '–' : SYMBOLS[mode]}
		</span>
		<div class="mc-value">
			<input
				class="mc-input"
				type="number"
				value={grams}
				disabled={mode === 'none'}
				onchange={onGramsInput}
			/>
			<span class="mc-unit">g</span>
		</div>
	</div>

	<!-- Footer -->
	<div class="mc-footer">
		<label class="toggle-switch hard-toggle">
			<input
				type="checkbox"
				checked={hard}
				disabled={mode === 'none'}
				onchange={(e) => toggleHard((e.target as HTMLInputElement).checked)}
			/>
			<span class="toggle-track hard-track">
				<span class="toggle-thumb"></span>
			</span>
			<span class="toggle-label hard-label">{hard ? 'Hard' : 'Soft'}</span>
		</label>
	</div>
</div>

<style>
	.mc-card {
		border: 1px solid var(--border-subtle, #2a2a2a);
		border-radius: 12px;
		padding: 10px 10px;
		display: flex;
		flex-direction: column;
		gap: 8px;
		background: var(--bg-card, #1a1a1a);
		transition: opacity 0.15s;
		/* Prevent grid blowout */
		min-width: 0;
		overflow: hidden;
	}

	.mc-card.disabled {
		opacity: 0.5;
	}

	.mc-card.disabled .mc-body,
	.mc-card.disabled .mc-footer {
		opacity: 0.4;
	}

	/* Header */
	.mc-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.mc-label {
		font-size: 13px;
		font-weight: 600;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.mc-divider {
		height: 1px;
		background: var(--border-subtle, #2a2a2a);
		margin: 0 -2px;
	}

	/* Body */
	.mc-body {
		display: flex;
		align-items: center;
		gap: 4px;
		min-width: 0;
	}

	.mc-symbol {
		font-size: 32px;
		font-weight: 700;
		color: var(--accent, #7c6cf0);
		cursor: pointer;
		line-height: 1;
		flex: 0 0 auto;
		text-align: center;
		user-select: none;
		-webkit-tap-highlight-color: transparent;
		padding: 4px;
		border-radius: 8px;
		transition: background 0.1s;
	}

	.mc-symbol:active {
		background: var(--bg-hover, rgba(124, 108, 240, 0.15));
	}

	.mc-value {
		display: flex;
		align-items: baseline;
		gap: 2px;
		flex: 1 1 0;
		min-width: 0;
		justify-content: flex-end;
	}

	.mc-input {
		width: 100%;
		min-width: 0;
		background: var(--bg-input);
		color: var(--text-primary);
		border: 1px solid var(--border-input);
		border-radius: 6px;
		padding: 4px 6px;
		font-size: 28px;
		font-weight: 600;
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
		font-size: 16px;
		color: var(--text-muted);
		font-weight: 500;
	}

	/* Footer */
	.mc-footer {
		display: flex;
		align-items: center;
		justify-content: flex-end;
	}

	/* Toggle switch */
	.toggle-switch {
		display: flex;
		align-items: center;
		gap: 6px;
		cursor: pointer;
		user-select: none;
	}

	.toggle-switch input {
		display: none;
	}

	.toggle-track {
		position: relative;
		width: 36px;
		height: 20px;
		background: var(--border-input, #444);
		border-radius: 10px;
		transition: background 0.2s;
		flex-shrink: 0;
	}

	.toggle-switch input:checked ~ .toggle-track {
		background: var(--accent, #7c6cf0);
	}

	.hard-track {
		width: 36px;
		height: 20px;
	}

	.toggle-switch input:checked ~ .hard-track {
		background: #22c55e;
	}

	.toggle-thumb {
		position: absolute;
		top: 2px;
		left: 2px;
		width: 16px;
		height: 16px;
		background: #fff;
		border-radius: 50%;
		transition: transform 0.2s;
	}

	.toggle-switch input:checked ~ .toggle-track .toggle-thumb {
		transform: translateX(16px);
	}

	.toggle-label {
		font-size: 11px;
		font-weight: 600;
		color: var(--text-muted);
		min-width: 22px;
	}

	.hard-label {
		min-width: 28px;
	}

	.toggle-switch input:disabled ~ .toggle-track {
		opacity: 0.5;
		cursor: not-allowed;
	}
</style>
