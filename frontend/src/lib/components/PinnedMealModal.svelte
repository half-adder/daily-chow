<script lang="ts">
	import type { PinnedMeal } from '$lib/api';

	interface Props {
		meal?: PinnedMeal | null;
		onsave: (meal: PinnedMeal) => void;
		onclose: () => void;
	}

	let { meal = null, onsave, onclose }: Props = $props();

	const MACRO_KEYS = ['calories_kcal', 'protein_g', 'fat_g', 'carbs_g', 'fiber_g'] as const;

	const MACRO_LABELS: Record<string, string> = {
		calories_kcal: 'Calories (kcal)',
		protein_g: 'Protein (g)',
		fat_g: 'Fat (g)',
		carbs_g: 'Carbs (g)',
		fiber_g: 'Fiber (g)'
	};

	const MICRO_TIERS = [
		{
			name: 'Major Minerals',
			keys: ['calcium_mg', 'iron_mg', 'magnesium_mg', 'phosphorus_mg', 'potassium_mg', 'zinc_mg', 'copper_mg', 'manganese_mg', 'selenium_mcg']
		},
		{
			name: 'B-Vitamins + C',
			keys: ['vitamin_c_mg', 'thiamin_mg', 'riboflavin_mg', 'niacin_mg', 'vitamin_b6_mg', 'folate_mcg', 'vitamin_b12_mcg']
		},
		{
			name: 'Fat-Soluble Vitamins',
			keys: ['vitamin_a_mcg', 'vitamin_d_mcg', 'vitamin_e_mg', 'vitamin_k_mcg']
		}
	];

	const MICRO_NAMES: Record<string, string> = {
		calcium_mg: 'Calcium (mg)',
		iron_mg: 'Iron (mg)',
		magnesium_mg: 'Magnesium (mg)',
		phosphorus_mg: 'Phosphorus (mg)',
		potassium_mg: 'Potassium (mg)',
		zinc_mg: 'Zinc (mg)',
		copper_mg: 'Copper (mg)',
		manganese_mg: 'Manganese (mg)',
		selenium_mcg: 'Selenium (mcg)',
		vitamin_c_mg: 'Vitamin C (mg)',
		thiamin_mg: 'Thiamin B1 (mg)',
		riboflavin_mg: 'Riboflavin B2 (mg)',
		niacin_mg: 'Niacin B3 (mg)',
		vitamin_b6_mg: 'Vitamin B6 (mg)',
		folate_mcg: 'Folate (mcg)',
		vitamin_b12_mcg: 'Vitamin B12 (mcg)',
		vitamin_a_mcg: 'Vitamin A (mcg)',
		vitamin_d_mcg: 'Vitamin D (mcg)',
		vitamin_e_mg: 'Vitamin E (mg)',
		vitamin_k_mcg: 'Vitamin K (mcg)'
	};

	const ALL_MICRO_KEYS = MICRO_TIERS.flatMap((t) => t.keys);

	let name = $state(meal?.name ?? '');
	let macros = $state<Record<string, string>>(
		Object.fromEntries(MACRO_KEYS.map((k) => [k, meal?.nutrients[k]?.toString() ?? '']))
	);
	let micros = $state<Record<string, string>>(
		Object.fromEntries(ALL_MICRO_KEYS.map((k) => [k, meal?.nutrients[k]?.toString() ?? '']))
	);
	let microsExpanded = $state(false);
	let validationError = $state('');
	let importError = $state('');

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onclose();
	}

	function validate(): boolean {
		if (!name.trim()) {
			validationError = 'Name is required.';
			return false;
		}
		for (const key of MACRO_KEYS) {
			const val = parseFloat(macros[key]);
			if (isNaN(val) || val < 0) {
				validationError = `${MACRO_LABELS[key]} must be a number >= 0.`;
				return false;
			}
		}
		validationError = '';
		return true;
	}

	function handleSave() {
		if (!validate()) return;

		const nutrients: Record<string, number> = {};
		for (const key of MACRO_KEYS) {
			nutrients[key] = parseFloat(macros[key]);
		}
		for (const key of ALL_MICRO_KEYS) {
			const val = parseFloat(micros[key]);
			if (!isNaN(val) && val >= 0) {
				nutrients[key] = val;
			}
		}

		onsave({
			id: meal?.id ?? crypto.randomUUID(),
			name: name.trim(),
			nutrients
		});
	}

	function handleImport(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		const reader = new FileReader();
		reader.onload = () => {
			try {
				let data = JSON.parse(reader.result as string);

				// Accept array format — use first element
				if (Array.isArray(data)) {
					data = data[0];
				}

				if (!data || typeof data !== 'object') {
					importError = 'Invalid JSON: expected an object.';
					return;
				}

				if (!data.name || typeof data.name !== 'string') {
					importError = 'Invalid JSON: missing "name" string.';
					return;
				}

				if (!data.nutrients || typeof data.nutrients !== 'object') {
					importError = 'Invalid JSON: missing "nutrients" object.';
					return;
				}

				// Validate required macro keys
				for (const key of MACRO_KEYS) {
					if (!(key in data.nutrients)) {
						importError = `Invalid JSON: missing required nutrient "${key}".`;
						return;
					}
				}

				// Validate all values are numbers >= 0
				for (const [key, val] of Object.entries(data.nutrients)) {
					if (typeof val !== 'number' || val < 0) {
						importError = `Invalid JSON: nutrient "${key}" must be a number >= 0.`;
						return;
					}
				}

				// Fill the form
				name = data.name;
				for (const key of MACRO_KEYS) {
					macros[key] = data.nutrients[key].toString();
				}
				for (const key of ALL_MICRO_KEYS) {
					if (key in data.nutrients) {
						micros[key] = data.nutrients[key].toString();
					}
				}

				importError = '';
			} catch {
				importError = 'Failed to parse JSON file.';
			}
		};
		reader.readAsText(file);

		// Reset input so the same file can be re-imported
		input.value = '';
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="modal-overlay" onclick={onclose}>
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<h3>{meal ? 'Edit Pinned Meal' : 'Add Pinned Meal'}</h3>
			<button class="close-btn" onclick={onclose}>&times;</button>
		</div>

		<div class="modal-body">
			<!-- Name -->
			<label class="field-label">
				Name
				<input type="text" class="text-input" bind:value={name} placeholder="e.g. Morning Smoothie" />
			</label>

			<!-- Macros -->
			<div class="section-label">Macros</div>
			<div class="macro-row">
				{#each MACRO_KEYS as key}
					<label class="macro-field">
						<span class="macro-label">{MACRO_LABELS[key]}</span>
						<input type="number" class="number-input" bind:value={macros[key]} min="0" step="any" />
					</label>
				{/each}
			</div>

			<!-- Micros -->
			<button class="section-toggle" onclick={() => (microsExpanded = !microsExpanded)}>
				<span class="toggle-arrow" class:expanded={microsExpanded}>&#9654;</span>
				Micronutrients
			</button>

			{#if microsExpanded}
				<div class="micros-section">
					{#each MICRO_TIERS as tier}
						<div class="micro-group">
							<div class="micro-group-label">{tier.name}</div>
							<div class="micro-grid">
								{#each tier.keys as key}
									<label class="micro-field">
										<span class="micro-label">{MICRO_NAMES[key]}</span>
										<input type="number" class="number-input micro-input" bind:value={micros[key]} min="0" step="any" />
									</label>
								{/each}
							</div>
						</div>
					{/each}
				</div>
			{/if}

			<!-- Import JSON -->
			<div class="import-section">
				<label class="import-btn">
					Import JSON
					<input type="file" accept=".json,application/json" onchange={handleImport} hidden />
				</label>
				{#if importError}
					<div class="error-msg">{importError}</div>
				{/if}
			</div>

			<!-- Validation error -->
			{#if validationError}
				<div class="error-msg">{validationError}</div>
			{/if}
		</div>

		<!-- Footer -->
		<div class="modal-footer">
			<button class="btn btn-cancel" onclick={onclose}>Cancel</button>
			<button class="btn btn-save" onclick={handleSave}>Save</button>
		</div>
	</div>
</div>

<style>
	.modal-overlay {
		position: fixed;
		inset: 0;
		background: var(--shadow-overlay);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
		backdrop-filter: blur(2px);
	}

	.modal {
		background: var(--bg-panel);
		border: 1px solid var(--border);
		border-radius: 12px;
		width: 540px;
		max-height: 85vh;
		display: flex;
		flex-direction: column;
		box-shadow: 0 20px 60px var(--shadow-modal);
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 16px 20px 0;
	}

	h3 {
		margin: 0;
		color: var(--text-primary);
		font-size: 16px;
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--text-muted);
		font-size: 22px;
		cursor: pointer;
		padding: 0 4px;
	}

	.close-btn:hover {
		color: var(--text-primary);
	}

	.modal-body {
		padding: 16px 20px;
		overflow-y: auto;
		flex: 1;
	}

	.field-label {
		display: flex;
		flex-direction: column;
		gap: 4px;
		color: var(--text-primary);
		font-size: 13px;
		font-weight: 500;
	}

	.text-input {
		padding: 8px 12px;
		background: var(--bg-input);
		border: 1px solid var(--border-input);
		border-radius: 8px;
		color: var(--text-primary);
		font-size: 14px;
		outline: none;
	}

	.text-input:focus {
		border-color: #3b82f6;
	}

	.section-label {
		margin-top: 16px;
		margin-bottom: 6px;
		color: var(--text-muted);
		font-size: 12px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.macro-row {
		display: flex;
		gap: 8px;
	}

	.macro-field {
		display: flex;
		flex-direction: column;
		gap: 2px;
		flex: 1;
		min-width: 0;
	}

	.macro-label {
		font-size: 11px;
		color: var(--text-muted);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.number-input {
		padding: 6px 8px;
		background: var(--bg-input);
		border: 1px solid var(--border-input);
		border-radius: 6px;
		color: var(--text-primary);
		font-size: 13px;
		outline: none;
		width: 100%;
		box-sizing: border-box;
	}

	.number-input:focus {
		border-color: #3b82f6;
	}

	/* Hide number input spinners */
	.number-input::-webkit-outer-spin-button,
	.number-input::-webkit-inner-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}

	.number-input {
		-moz-appearance: textfield;
	}

	.section-toggle {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-top: 16px;
		background: none;
		border: none;
		color: var(--text-primary);
		font-size: 13px;
		font-weight: 500;
		cursor: pointer;
		padding: 4px 0;
	}

	.section-toggle:hover {
		color: #3b82f6;
	}

	.toggle-arrow {
		font-size: 10px;
		transition: transform 0.15s ease;
		display: inline-block;
	}

	.toggle-arrow.expanded {
		transform: rotate(90deg);
	}

	.micros-section {
		margin-top: 8px;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.micro-group-label {
		font-size: 11px;
		color: var(--text-muted);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin-bottom: 4px;
	}

	.micro-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 6px 12px;
	}

	.micro-field {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.micro-label {
		font-size: 12px;
		color: var(--text-primary);
		flex: 1;
		white-space: nowrap;
	}

	.micro-input {
		width: 80px;
		flex: 0 0 80px;
	}

	.import-section {
		margin-top: 16px;
	}

	.import-btn {
		display: inline-flex;
		align-items: center;
		padding: 6px 14px;
		background: var(--bg-input);
		border: 1px solid var(--border-input);
		border-radius: 6px;
		color: var(--text-primary);
		font-size: 13px;
		cursor: pointer;
	}

	.import-btn:hover {
		background: var(--bg-hover);
	}

	.error-msg {
		margin-top: 8px;
		color: #ef4444;
		font-size: 12px;
	}

	.modal-footer {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
		padding: 12px 20px;
		border-top: 1px solid var(--border);
	}

	.btn {
		padding: 8px 18px;
		border: none;
		border-radius: 8px;
		font-size: 13px;
		font-weight: 500;
		cursor: pointer;
	}

	.btn-cancel {
		background: var(--bg-input);
		color: var(--text-primary);
		border: 1px solid var(--border-input);
	}

	.btn-cancel:hover {
		background: var(--bg-hover);
	}

	.btn-save {
		background: #3b82f6;
		color: #fff;
	}

	.btn-save:hover {
		background: #2563eb;
	}

	@media (max-width: 640px) {
		.modal {
			width: 100vw;
			height: 100vh;
			max-width: none;
			max-height: none;
			border-radius: 0;
			margin: 0;
		}
	}
</style>
