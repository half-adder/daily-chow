<script lang="ts">
	interface Props {
		min: number;
		max: number;
		absMin?: number;
		absMax?: number;
		solvedValue?: number | null;
		onchange?: (min: number, max: number) => void;
	}

	let {
		min = $bindable(0),
		max = $bindable(100),
		absMin = 0,
		absMax = 1000,
		solvedValue = null,
		onchange
	}: Props = $props();

	function pct(val: number): number {
		const span = absMax - absMin;
		if (span <= 0) return 0;
		return ((val - absMin) / span) * 100;
	}

	function handleMinInput(e: Event) {
		const val = parseInt((e.target as HTMLInputElement).value);
		if (!isNaN(val)) {
			min = Math.min(val, max);
			onchange?.(min, max);
		}
	}

	function handleMaxInput(e: Event) {
		const val = parseInt((e.target as HTMLInputElement).value);
		if (!isNaN(val)) {
			max = Math.max(val, min);
			onchange?.(min, max);
		}
	}
</script>

<div class="dual-range">
	<div class="track">
		<div
			class="range-fill"
			style="left: {pct(min)}%; width: {pct(max) - pct(min)}%"
		></div>
		{#if solvedValue != null && solvedValue >= min && solvedValue <= max}
			<div
				class="solved-marker"
				style="left: calc(8px + (100% - 16px) * {pct(solvedValue) / 100})"
				title="{solvedValue}g (solved)"
			></div>
		{/if}
		<input
			type="range"
			min={absMin}
			max={absMax}
			bind:value={min}
			oninput={() => { min = Math.min(min, max); onchange?.(min, max); }}
			class="thumb thumb-min"
		/>
		<input
			type="range"
			min={absMin}
			max={absMax}
			bind:value={max}
			oninput={() => { max = Math.max(max, min); onchange?.(min, max); }}
			class="thumb thumb-max"
		/>
	</div>
</div>

<style>
	.dual-range {
		position: relative;
		width: 100%;
		height: 32px;
		display: flex;
		align-items: center;
	}

	.track {
		position: relative;
		width: 100%;
		height: 6px;
		background: #2a2a2a;
		border-radius: 3px;
	}

	.range-fill {
		position: absolute;
		height: 100%;
		background: #3b82f6;
		border-radius: 3px;
		pointer-events: none;
	}

	.solved-marker {
		position: absolute;
		top: 50%;
		width: 12px;
		height: 12px;
		background: #22c55e;
		border: 2px solid #fff;
		border-radius: 50%;
		transform: translate(-50%, -50%);
		pointer-events: none;
		z-index: 3;
		box-shadow: 0 0 4px rgba(34, 197, 94, 0.5);
	}

	.thumb {
		position: absolute;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
		-webkit-appearance: none;
		appearance: none;
		background: none;
		pointer-events: none;
		margin: 0;
	}

	.thumb::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 16px;
		height: 16px;
		background: #3b82f6;
		border: 2px solid #fff;
		border-radius: 50%;
		cursor: pointer;
		pointer-events: all;
		position: relative;
		z-index: 2;
	}

	.thumb::-moz-range-thumb {
		width: 16px;
		height: 16px;
		background: #3b82f6;
		border: 2px solid #fff;
		border-radius: 50%;
		cursor: pointer;
		pointer-events: all;
	}

	.thumb:focus::-webkit-slider-thumb {
		box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.3);
	}
</style>
