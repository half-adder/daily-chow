<script lang="ts">
	interface Segment {
		key: string;
		label: string;
		value: string;
		pct: number;
		color: string;
	}

	interface Props {
		segments: Segment[];
		height?: number;
	}

	let { segments, height = 20 }: Props = $props();

	let hoveredKey = $state<string | null>(null);
	let tooltipX = $state(0);
	let tooltipY = $state(0);

	function handleMouseEnter(key: string, e: MouseEvent) {
		hoveredKey = key;
		tooltipX = e.clientX;
		tooltipY = e.clientY;
	}

	function handleMouseMove(e: MouseEvent) {
		tooltipX = e.clientX;
		tooltipY = e.clientY;
	}

	function handleMouseLeave() {
		hoveredKey = null;
	}

	let hoveredSegment = $derived(segments.find((s) => s.key === hoveredKey));
</script>

<div class="stacked-bar" style="height: {height}px">
	{#each segments as seg (seg.key)}
		{#if seg.pct > 0.5}
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class="segment"
				style="width: {seg.pct}%; background: {seg.color}"
				onmouseenter={(e) => handleMouseEnter(seg.key, e)}
				onmousemove={handleMouseMove}
				onmouseleave={handleMouseLeave}
			>
				{#if seg.pct >= 12}
					<span class="segment-label">{seg.label}</span>
				{/if}
			</div>
		{/if}
	{/each}
</div>

{#if hoveredSegment}
	<div class="tooltip" style="left: {tooltipX}px; top: {tooltipY}px">
		<span class="tooltip-swatch" style="background: {hoveredSegment.color}"></span>
		<span class="tooltip-name">{hoveredSegment.label}</span>
		<span class="tooltip-value">{hoveredSegment.value}</span>
	</div>
{/if}

<style>
	.stacked-bar {
		display: flex;
		border-radius: 6px;
		overflow: hidden;
		width: 100%;
	}

	.segment {
		display: flex;
		align-items: center;
		justify-content: center;
		min-width: 0;
		transition: opacity 0.15s;
		cursor: default;
	}

	.segment:last-of-type {
		border-top-right-radius: 6px;
		border-bottom-right-radius: 6px;
	}

	.segment:hover {
		opacity: 0.85;
	}

	.segment-label {
		font-size: 11px;
		font-weight: 600;
		color: var(--text-segment);
		text-shadow: 0 1px 2px var(--shadow-text);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		padding: 0 4px;
	}

	.tooltip {
		position: fixed;
		transform: translate(-50%, -100%);
		margin-top: -10px;
		background: var(--bg-panel);
		border: 1px solid var(--border-input);
		border-radius: 6px;
		padding: 6px 10px;
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 12px;
		color: var(--text-primary);
		pointer-events: none;
		z-index: 200;
		white-space: nowrap;
		box-shadow: 0 4px 12px var(--shadow-tooltip);
	}

	.tooltip-swatch {
		width: 10px;
		height: 10px;
		border-radius: 2px;
		flex-shrink: 0;
	}

	.tooltip-name {
		font-weight: 500;
	}

	.tooltip-value {
		color: var(--text-secondary);
	}
</style>
