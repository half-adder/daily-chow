<script lang="ts">
	interface Props {
		calories: number;
		oncalorieschange: (val: number) => void;
	}

	let { calories, oncalorieschange }: Props = $props();

	function onCalInput(e: Event) {
		const val = parseInt((e.target as HTMLInputElement).value);
		if (!isNaN(val) && val >= 0) oncalorieschange(val);
	}
</script>

<div class="card">
	<div class="card-header">
		<span class="card-label">Calories</span>
	</div>
	<div class="card-divider"></div>
	<div class="card-body">
		<input
			class="cal-input"
			type="number"
			value={calories}
			onchange={onCalInput}
		/>
		<span class="cal-unit">kcal</span>
	</div>
</div>

<style>
	.card {
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 10px 10px;
		display: flex;
		flex-direction: column;
		gap: 8px;
		background: var(--bg-panel);
		min-width: 0;
		overflow: hidden;
	}

	.card-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.card-label {
		font-size: 13px;
		font-weight: 600;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.card-divider {
		height: 1px;
		background: var(--border);
		margin: 0 -2px;
	}

	.card-body {
		display: flex;
		align-items: baseline;
		gap: 4px;
		min-width: 0;
	}

	.cal-input {
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

	.cal-input::-webkit-outer-spin-button,
	.cal-input::-webkit-inner-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}

	.cal-unit {
		font-size: 16px;
		color: var(--text-muted);
		font-weight: 500;
		flex-shrink: 0;
	}

</style>
