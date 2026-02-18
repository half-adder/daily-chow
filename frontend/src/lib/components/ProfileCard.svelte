<script lang="ts">
	import Mars from 'lucide-svelte/icons/mars';
	import Venus from 'lucide-svelte/icons/venus';

	interface Props {
		sex: string;
		age: number;
		onsexchange: (val: string) => void;
		onagechange: (val: number) => void;
	}

	let { sex, age, onsexchange, onagechange }: Props = $props();

	function onAgeInput(e: Event) {
		const val = parseInt((e.target as HTMLInputElement).value);
		if (!isNaN(val) && val >= 1 && val <= 120) onagechange(val);
	}
</script>

<div class="card">
	<div class="card-header">
		<span class="card-label">Profile</span>
	</div>
	<div class="card-divider"></div>
	<div class="card-body">
		<button class="sex-toggle" class:male={sex === 'male'} class:female={sex === 'female'}
			onclick={() => onsexchange(sex === 'male' ? 'female' : 'male')}
			title={sex === 'male' ? 'Male' : 'Female'}>
			{#if sex === 'male'}<Mars size={20} strokeWidth={3.5} />{:else}<Venus size={20} strokeWidth={3.5} />{/if}
		</button>
		<div class="age-wrapper">
			<span class="age-label">Age</span>
			<input
				class="age-input"
				type="number"
				value={age}
				min="1"
				max="120"
				onchange={onAgeInput}
			/>
		</div>
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
		align-items: center;
		gap: 8px;
		min-width: 0;
		padding-top: 8px;
	}

	.sex-toggle {
		background: none;
		border: 1px solid var(--border-input);
		border-radius: 6px;
		cursor: pointer;
		line-height: 1;
		flex-shrink: 0;
		width: 42px;
		height: 42px;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		transition: color 0.15s, border-color 0.15s;
	}

	.sex-toggle.male {
		color: #60a5fa;
		border-color: #60a5fa;
	}

	.sex-toggle.female {
		color: #f472b6;
		border-color: #f472b6;
	}

	.age-wrapper {
		position: relative;
		flex: 1 1 0;
		min-width: 0;
	}

	.age-label {
		position: absolute;
		top: -1px;
		left: 6px;
		transform: translateY(-50%);
		font-size: 10px;
		font-weight: 600;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		background: var(--bg-panel);
		padding: 0 3px;
		line-height: 1;
		pointer-events: none;
	}

	.age-input {
		width: 100%;
		min-width: 0;
		box-sizing: border-box;
		background: var(--bg-input);
		color: var(--text-primary);
		border: 1px solid var(--border-input);
		border-radius: 6px;
		padding: 4px 6px;
		font-size: 28px;
		font-weight: 600;
		text-align: right;
		font-variant-numeric: tabular-nums;
		-moz-appearance: textfield;
	}

	.age-input::-webkit-outer-spin-button,
	.age-input::-webkit-inner-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}

</style>
