<script lang="ts">
	import type { Food, MicroResult } from '$lib/api';
	import { computeGapScore, countGapsFilled } from '$lib/contributions';
	import { loadCustomFoods, saveCustomFoods, nextCustomId, exportCustomFoods, validateImportedFoods } from '$lib/customFoods';

	type ModalView = 'search' | 'create' | 'manage';

	interface Props {
		foods: Record<number, Food>;
		existingKeys: Set<number>;
		microResults: Record<string, MicroResult>;
		mealCalories: number;
		maxPerIngredient: number;
		customFoods: Food[];
		onselect: (key: number) => void;
		onclose: () => void;
		oncustomchange: () => void;
	}

	let { foods, existingKeys, microResults, mealCalories, maxPerIngredient, customFoods, onselect, onclose, oncustomchange }: Props = $props();

	let query = $state('');
	let debouncedQuery = $state('');
	let debounceTimer: ReturnType<typeof setTimeout>;
	let view = $state<ModalView>('search');

	function onInput(e: Event) {
		const value = (e.target as HTMLInputElement).value;
		query = value;
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => { debouncedQuery = value; }, 120);
	}

	let hasMicroData = $derived(Object.keys(microResults).length > 0);

	function estimateServingG(food: Food): number {
		const numIngredients = Math.max(existingKeys.size, 1);
		const calShareG = (mealCalories / (numIngredients + 1)) / (food.calories_kcal_per_100g / 100);
		return Math.min(maxPerIngredient, calShareG);
	}

	// Pre-compute gap scores once when microResults change, not inside sort
	let gapScores = $derived.by(() => {
		if (!hasMicroData) return new Map<string, number>();
		const scores = new Map<string, number>();
		for (const [key, food] of Object.entries(foods)) {
			scores.set(key, computeGapScore(0, food, microResults, estimateServingG(food)));
		}
		return scores;
	});

	// Significant words from plan ingredient names (for de-ranking similar items in browse)
	let planWords = $derived.by(() => {
		const words = new Set<string>();
		for (const key of existingKeys) {
			const food = foods[key];
			if (!food) continue;
			for (const word of food.name.toLowerCase().split(/\s+/)) {
				if (word.length >= 3) words.add(word);
			}
		}
		return words;
	});

	// Pre-compute similarity flags so we don't split strings inside the sort comparator
	let similarFlags = $derived.by(() => {
		const flags = new Map<string, boolean>();
		for (const [key, food] of Object.entries(foods)) {
			const isSimilar = food.name.toLowerCase()
				.split(/\s+/)
				.some((w) => w.length >= 3 && planWords.has(w));
			flags.set(key, isSimilar);
		}
		return flags;
	});

	interface FoodGroup {
		groupKey: string;
		representative: [string, Food];
		variants: [string, Food][];
	}

	let expandedGroups = $state(new Set<string>());

	function toggleGroup(groupKey: string, e: Event) {
		e.stopPropagation();
		if (expandedGroups.has(groupKey)) {
			expandedGroups.delete(groupKey);
		} else {
			expandedGroups.add(groupKey);
		}
		expandedGroups = new Set(expandedGroups);
	}

	function computeScore(key: string, food: Food): number {
		return (food.commonness ?? 3) + (gapScores.get(key) ?? 0);
	}

	let groupedResults = $derived.by(() => {
		const q = debouncedQuery.toLowerCase().trim();
		let entries = Object.entries(foods).filter(([k]) => !existingKeys.has(Number(k)));

		if (q) {
			entries = entries
				.filter(([, food]) => {
					const searchable = `${food.name} ${food.subtitle} ${food.usda_description} ${food.category}`.toLowerCase();
					return searchable.includes(q);
				})
				.sort(([ka, a], [kb, b]) => {
					const aStarts = a.name.toLowerCase().startsWith(q) ? 0 : 1;
					const bStarts = b.name.toLowerCase().startsWith(q) ? 0 : 1;
					if (aStarts !== bStarts) return aStarts - bStarts;
					return computeScore(kb, b) - computeScore(ka, a);
				});
		} else {
			entries = entries.sort(([ka, a], [kb, b]) => {
				const aSimilar = similarFlags.get(ka) ? 1 : 0;
				const bSimilar = similarFlags.get(kb) ? 1 : 0;
				if (aSimilar !== bSimilar) return aSimilar - bSimilar;
				return computeScore(kb, b) - computeScore(ka, a);
			});
		}

		// Group by food.group — entries are already sorted by score,
		// so the first entry per group is the representative.
		const groupMap = new Map<string, { representative: [string, Food]; variants: [string, Food][] }>();
		for (const entry of entries) {
			const [, food] = entry;
			const gk = food.group.toLowerCase();
			const existing = groupMap.get(gk);
			if (!existing) {
				groupMap.set(gk, { representative: entry, variants: [] });
			} else {
				existing.variants.push(entry);
			}
		}

		// Preserve order from sorted entries
		const groups: FoodGroup[] = [];
		const seen = new Set<string>();
		for (const entry of entries) {
			const gk = entry[1].group.toLowerCase();
			if (seen.has(gk)) continue;
			seen.add(gk);
			const g = groupMap.get(gk)!;
			groups.push({ groupKey: gk, representative: g.representative, variants: g.variants });
		}

		return groups;
	});

	// --- Custom ingredient form state ---
	let editingFood = $state<Food | null>(null);
	let formName = $state('');
	let formSubtitle = $state('');
	let formCalories = $state('');
	let formProtein = $state('');
	let formFat = $state('');
	let formCarbs = $state('');
	let formFiber = $state('');
	let formPortionUnit = $state('');
	let formPortionG = $state('');
	let showMicros = $state(false);
	let formMicros = $state<Record<string, string>>({});
	let formError = $state('');

	const MICRO_LABELS: Record<string, { name: string; unit: string }> = {
		calcium_mg: { name: 'Calcium', unit: 'mg' },
		iron_mg: { name: 'Iron', unit: 'mg' },
		magnesium_mg: { name: 'Magnesium', unit: 'mg' },
		phosphorus_mg: { name: 'Phosphorus', unit: 'mg' },
		potassium_mg: { name: 'Potassium', unit: 'mg' },
		zinc_mg: { name: 'Zinc', unit: 'mg' },
		copper_mg: { name: 'Copper', unit: 'mg' },
		manganese_mg: { name: 'Manganese', unit: 'mg' },
		selenium_mcg: { name: 'Selenium', unit: 'mcg' },
		vitamin_c_mg: { name: 'Vitamin C', unit: 'mg' },
		thiamin_mg: { name: 'Thiamin (B1)', unit: 'mg' },
		riboflavin_mg: { name: 'Riboflavin (B2)', unit: 'mg' },
		niacin_mg: { name: 'Niacin (B3)', unit: 'mg' },
		vitamin_b6_mg: { name: 'Vitamin B6', unit: 'mg' },
		folate_mcg: { name: 'Folate', unit: 'mcg' },
		vitamin_b12_mcg: { name: 'Vitamin B12', unit: 'mcg' },
		vitamin_a_mcg: { name: 'Vitamin A', unit: 'mcg' },
		vitamin_d_mcg: { name: 'Vitamin D', unit: 'mcg' },
		vitamin_e_mg: { name: 'Vitamin E', unit: 'mg' },
		vitamin_k_mcg: { name: 'Vitamin K', unit: 'mcg' },
	};

	function resetForm() {
		formName = '';
		formSubtitle = '';
		formCalories = '';
		formProtein = '';
		formFat = '';
		formCarbs = '';
		formFiber = '';
		formPortionUnit = '';
		formPortionG = '';
		showMicros = false;
		formMicros = {};
		formError = '';
		editingFood = null;
	}

	function populateForm(food: Food) {
		editingFood = food;
		formName = food.name;
		formSubtitle = food.subtitle;
		formCalories = String(food.calories_kcal_per_100g);
		formProtein = String(food.protein_g_per_100g);
		formFat = String(food.fat_g_per_100g);
		formCarbs = String(food.carbs_g_per_100g);
		formFiber = String(food.fiber_g_per_100g);
		formPortionUnit = food.portion?.unit ?? '';
		formPortionG = food.portion ? String(food.portion.g) : '';
		const micros: Record<string, string> = {};
		for (const [k, v] of Object.entries(food.micros)) {
			if (v > 0) micros[k] = String(v);
		}
		formMicros = micros;
		showMicros = Object.keys(micros).length > 0;
		formError = '';
	}

	function saveForm() {
		if (!formName.trim()) { formError = 'Name is required'; return; }
		const cal = Number(formCalories);
		const pro = Number(formProtein);
		const fat = Number(formFat);
		const carb = Number(formCarbs);
		const fib = Number(formFiber);
		if ([cal, pro, fat, carb, fib].some((v) => isNaN(v) || v < 0)) {
			formError = 'All macro values must be non-negative numbers';
			return;
		}

		const micros: Record<string, number> = {};
		for (const [k, v] of Object.entries(formMicros)) {
			if (v.trim() === '') continue;
			const num = Number(v);
			if (isNaN(num) || num < 0) {
				formError = `Invalid value for ${MICRO_LABELS[k]?.name ?? k}`;
				return;
			}
			micros[k] = num;
		}

		const existing = loadCustomFoods();
		const food: Food = {
			fdc_id: editingFood ? editingFood.fdc_id : nextCustomId(existing),
			name: formName.trim(),
			subtitle: formSubtitle.trim(),
			usda_description: formName.trim(),
			category: 'Custom',
			commonness: 5,
			group: formName.trim(),
			calories_kcal_per_100g: cal,
			protein_g_per_100g: pro,
			fat_g_per_100g: fat,
			carbs_g_per_100g: carb,
			fiber_g_per_100g: fib,
			micros,
		};
		if (formPortionUnit.trim() && formPortionG.trim()) {
			const pg = Number(formPortionG);
			if (!isNaN(pg) && pg > 0) {
				food.portion = { unit: formPortionUnit.trim(), g: pg };
			}
		}

		if (editingFood) {
			const idx = existing.findIndex((f) => f.fdc_id === editingFood!.fdc_id);
			if (idx >= 0) existing[idx] = food;
			else existing.push(food);
		} else {
			existing.push(food);
		}
		saveCustomFoods(existing);
		oncustomchange();
		resetForm();
		view = 'search';
	}

	function deleteCustomFood(fdcId: number) {
		if (!confirm('Delete this custom ingredient?')) return;
		const existing = loadCustomFoods();
		const updated = existing.filter((f) => f.fdc_id !== fdcId);
		saveCustomFoods(updated);
		oncustomchange();
	}

	function handleImport() {
		const input = document.createElement('input');
		input.type = 'file';
		input.accept = '.json';
		input.onchange = async () => {
			const file = input.files?.[0];
			if (!file) return;
			try {
				const text = await file.text();
				const data = JSON.parse(text);
				const imported = validateImportedFoods(data);
				if (!imported) {
					formError = 'Invalid file format';
					return;
				}
				const existing = loadCustomFoods();
				for (const food of imported) {
					const conflict = existing.find((f) => f.name === food.name);
					if (conflict) {
						if (confirm(`"${food.name}" already exists. Overwrite?`)) {
							const idx = existing.indexOf(conflict);
							food.fdc_id = conflict.fdc_id;
							food.category = 'Custom';
							existing[idx] = food;
						}
					} else {
						food.fdc_id = nextCustomId(existing);
						food.category = 'Custom';
						existing.push(food);
					}
				}
				saveCustomFoods(existing);
				oncustomchange();
				formError = '';
			} catch {
				formError = 'Failed to read file';
			}
		};
		input.click();
	}

	function handleClose() {
		resetForm();
		view = 'search';
		onclose();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') handleClose();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="modal-overlay" onclick={handleClose}>
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			{#if view === 'search'}
				<h3>Add Ingredient</h3>
			{:else if view === 'create'}
				<h3>{editingFood ? 'Edit' : 'Create'} Custom Ingredient</h3>
			{:else}
				<h3>My Ingredients</h3>
			{/if}
			<button class="close-btn" onclick={handleClose}>&times;</button>
		</div>

		{#if view === 'search'}
			<input
				type="text"
				class="search-input"
				placeholder="Search foods..."
				value={query}
				oninput={onInput}
				autofocus
			/>

			<div class="custom-actions">
				<button class="create-custom-btn" onclick={() => { resetForm(); view = 'create'; }}>
					+ Create Custom Ingredient
				</button>
				{#if customFoods.length > 0}
					<button class="manage-link" onclick={() => (view = 'manage')}>
						My Ingredients ({customFoods.length})
					</button>
				{/if}
			</div>

			<div class="results">
				{#each groupedResults as { groupKey, representative, variants }}
					{@const [key, food] = representative}
					{@const gaps = hasMicroData ? countGapsFilled(food, microResults, estimateServingG(food)) : 0}
					<div class="group-row">
						<button class="result-item" onclick={() => onselect(Number(key))}>
							<span class="result-name">
								{food.name}
								{#if variants.length > 0}
									<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
									<span
										class="variant-toggle"
										onclick={(e) => toggleGroup(groupKey, e)}
										role="button"
										tabindex="0"
									>
										{#if expandedGroups.has(groupKey)}
											&minus;{variants.length} more
										{:else}
											+{variants.length} more
										{/if}
									</span>
								{/if}
							</span>
							<span class="result-note">{food.subtitle}</span>
							<span class="result-macros">
								{food.calories_kcal_per_100g} kcal &middot; {food.protein_g_per_100g}g pro &middot; {food.fiber_g_per_100g}g fiber
							</span>
							<span class="result-meta">
								{#if gaps > 0}
									<span class="result-gaps">fills {gaps} gap{gaps !== 1 ? 's' : ''}</span>
								{/if}
								<span class="result-category">{food.category}</span>
								{#if food.category === 'Custom'}<span class="custom-badge">Custom</span>{/if}
							</span>
						</button>
					</div>

					{#if expandedGroups.has(groupKey)}
						{#each variants as [vKey, vFood]}
							{@const vGaps = hasMicroData ? countGapsFilled(vFood, microResults, estimateServingG(vFood)) : 0}
							<button class="result-item variant-item" onclick={() => onselect(Number(vKey))}>
								<span class="result-name">{vFood.name}</span>
								<span class="result-note">{vFood.subtitle}</span>
								<span class="result-macros">
									{vFood.calories_kcal_per_100g} kcal &middot; {vFood.protein_g_per_100g}g pro &middot; {vFood.fiber_g_per_100g}g fiber
								</span>
								<span class="result-meta">
									{#if vGaps > 0}
										<span class="result-gaps">fills {vGaps} gap{vGaps !== 1 ? 's' : ''}</span>
									{/if}
									<span class="result-category">{vFood.category}</span>
									{#if vFood.category === 'Custom'}<span class="custom-badge">Custom</span>{/if}
								</span>
							</button>
						{/each}
					{/if}
				{:else}
					<div class="no-results">No matching foods</div>
				{/each}
			</div>

		{:else if view === 'create'}
			<div class="custom-form">
				{#if formError}
					<div class="form-error">{formError}</div>
				{/if}

				<div class="form-section">
					<label class="form-label">
						Name <span class="required">*</span>
						<input type="text" bind:value={formName} placeholder="e.g., Protein Bar" />
					</label>
					<label class="form-label">
						Subtitle
						<input type="text" bind:value={formSubtitle} placeholder="e.g., chocolate flavor" />
					</label>
				</div>

				<div class="form-section">
					<h4>Macros <span class="per100g">(per 100g)</span></h4>
					<div class="macro-grid">
						<label>Calories (kcal) <span class="required">*</span>
							<input type="number" bind:value={formCalories} min="0" step="any" />
						</label>
						<label>Protein (g) <span class="required">*</span>
							<input type="number" bind:value={formProtein} min="0" step="any" />
						</label>
						<label>Fat (g) <span class="required">*</span>
							<input type="number" bind:value={formFat} min="0" step="any" />
						</label>
						<label>Carbs (g) <span class="required">*</span>
							<input type="number" bind:value={formCarbs} min="0" step="any" />
						</label>
						<label>Fiber (g) <span class="required">*</span>
							<input type="number" bind:value={formFiber} min="0" step="any" />
						</label>
					</div>
				</div>

				<div class="form-section">
					<h4>Portion Size <span class="optional">(optional)</span></h4>
					<div class="portion-row">
						<label>Unit name
							<input type="text" bind:value={formPortionUnit} placeholder="e.g., scoop" />
						</label>
						<label>Grams
							<input type="number" bind:value={formPortionG} min="0" step="any" />
						</label>
					</div>
				</div>

				<div class="form-section">
					<button class="micro-toggle" onclick={() => (showMicros = !showMicros)}>
						{showMicros ? '\u2212' : '+'} Micronutrients <span class="optional">(optional)</span>
					</button>
					{#if showMicros}
						<div class="micro-grid">
							{#each Object.entries(MICRO_LABELS) as [key, { name, unit }]}
								<label>
									{name} ({unit})
									<input
										type="number"
										value={formMicros[key] ?? ''}
										oninput={(e) => { formMicros[key] = (e.target as HTMLInputElement).value; formMicros = { ...formMicros }; }}
										min="0"
										step="any"
										placeholder="—"
									/>
								</label>
							{/each}
						</div>
					{/if}
				</div>

				<div class="form-actions">
					<button class="cancel-btn" onclick={() => { resetForm(); view = 'search'; }}>Cancel</button>
					<button class="save-btn" onclick={saveForm}>Save</button>
				</div>
			</div>

		{:else if view === 'manage'}
			<div class="manage-view">
				<button class="back-link" onclick={() => (view = 'search')}>&larr; Back to search</button>

				{#if customFoods.length === 0}
					<div class="no-results">No custom ingredients yet</div>
				{:else}
					<div class="manage-list">
						{#each customFoods as food}
							<div class="manage-item">
								<div class="manage-info">
									<span class="manage-name">{food.name}</span>
									{#if food.subtitle}<span class="manage-subtitle">{food.subtitle}</span>{/if}
									<span class="manage-macros">
										{food.calories_kcal_per_100g} kcal &middot; {food.protein_g_per_100g}g P &middot; {food.fat_g_per_100g}g F &middot; {food.carbs_g_per_100g}g C
									</span>
								</div>
								<div class="manage-actions">
									<button class="edit-btn" onclick={() => { populateForm(food); view = 'create'; }}>Edit</button>
									<button class="delete-btn" onclick={() => deleteCustomFood(food.fdc_id)}>Delete</button>
								</div>
							</div>
						{/each}
					</div>
				{/if}

				{#if formError}
					<div class="form-error">{formError}</div>
				{/if}

				<div class="import-export">
					<button class="import-btn" onclick={handleImport}>Import</button>
					<button class="export-btn" onclick={() => exportCustomFoods(customFoods)}>Export</button>
				</div>
			</div>
		{/if}
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
		width: 500px;
		max-height: 80vh;
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

	.search-input {
		margin: 12px 20px;
		padding: 10px 14px;
		background: var(--bg-input);
		border: 1px solid var(--border-input);
		border-radius: 8px;
		color: var(--text-primary);
		font-size: 14px;
		outline: none;
	}

	.search-input:focus {
		border-color: #3b82f6;
	}

	.results {
		overflow-y: auto;
		padding: 0 8px 8px;
		flex: 1;
	}

	.group-row {
		position: relative;
	}

	.result-item {
		display: grid;
		grid-template-columns: 1fr auto;
		grid-template-rows: auto auto;
		gap: 2px 12px;
		width: 100%;
		padding: 10px 12px;
		background: none;
		border: none;
		border-radius: 8px;
		cursor: pointer;
		text-align: left;
		color: var(--text-primary);
	}

	.result-item:hover {
		background: var(--bg-hover);
	}

	.variant-item {
		padding-left: 28px;
		opacity: 0.75;
	}

	.variant-item:hover {
		opacity: 1;
	}

	.variant-toggle {
		display: inline-flex;
		align-items: center;
		margin-left: 6px;
		padding: 1px 8px;
		font-size: 11px;
		font-weight: 500;
		color: var(--accent);
		background: color-mix(in srgb, var(--accent) 12%, transparent);
		border-radius: 10px;
		cursor: pointer;
		vertical-align: middle;
		user-select: none;
	}

	.variant-toggle:hover {
		background: color-mix(in srgb, var(--accent) 22%, transparent);
	}

	.result-name {
		font-weight: 500;
		display: flex;
		align-items: center;
		gap: 0;
	}

	.result-note {
		font-size: 12px;
		color: var(--text-muted);
	}

	.result-macros {
		font-size: 12px;
		color: var(--text-muted);
	}

	.result-meta {
		display: flex;
		align-items: center;
		gap: 8px;
		justify-self: end;
	}

	.result-gaps {
		font-size: 11px;
		color: #22c55e;
		background: rgba(34, 197, 94, 0.1);
		padding: 1px 6px;
		border-radius: 8px;
	}

	.result-category {
		font-size: 11px;
		color: #3b82f6;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.no-results {
		padding: 20px;
		text-align: center;
		color: var(--text-dim);
	}

	/* Custom actions bar */
	.custom-actions {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 0 20px 8px;
	}

	.create-custom-btn {
		background: none;
		border: 1px dashed var(--border-input);
		border-radius: 8px;
		color: var(--accent);
		font-size: 13px;
		padding: 6px 12px;
		cursor: pointer;
	}

	.create-custom-btn:hover {
		background: var(--bg-hover);
		border-color: var(--accent);
	}

	.manage-link {
		background: none;
		border: none;
		color: var(--text-muted);
		font-size: 12px;
		cursor: pointer;
		padding: 4px 0;
		margin-left: auto;
	}

	.manage-link:hover {
		color: var(--text-primary);
	}

	.custom-badge {
		font-size: 10px;
		color: #a78bfa;
		background: rgba(167, 139, 250, 0.12);
		padding: 1px 6px;
		border-radius: 8px;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	/* Create/edit form */
	.custom-form {
		padding: 12px 20px 20px;
		overflow-y: auto;
		flex: 1;
	}

	.form-section {
		margin-bottom: 16px;
	}

	.form-section h4 {
		margin: 0 0 8px;
		color: var(--text-primary);
		font-size: 13px;
	}

	.per100g, .optional {
		color: var(--text-muted);
		font-weight: normal;
		font-size: 12px;
	}

	.required {
		color: #ef4444;
	}

	.form-label {
		display: block;
		margin-bottom: 8px;
		font-size: 13px;
		color: var(--text-muted);
	}

	.form-label input, .macro-grid input, .portion-row input, .micro-grid input {
		display: block;
		width: 100%;
		margin-top: 4px;
		padding: 8px 10px;
		background: var(--bg-input);
		border: 1px solid var(--border-input);
		border-radius: 6px;
		color: var(--text-primary);
		font-size: 14px;
		box-sizing: border-box;
		min-width: 0;
	}

	.form-label input:focus, .macro-grid input:focus, .portion-row input:focus, .micro-grid input:focus {
		border-color: #3b82f6;
		outline: none;
	}

	.macro-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px;
	}

	.macro-grid label, .portion-row label, .micro-grid label {
		font-size: 12px;
		color: var(--text-muted);
	}

	.portion-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px;
	}

	.micro-toggle {
		background: none;
		border: none;
		color: var(--text-muted);
		font-size: 13px;
		cursor: pointer;
		padding: 4px 0;
	}

	.micro-toggle:hover {
		color: var(--text-primary);
	}

	.micro-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px;
		margin-top: 8px;
	}

	.form-actions {
		display: flex;
		gap: 8px;
		justify-content: flex-end;
		padding-top: 8px;
		border-top: 1px solid var(--border);
	}

	.cancel-btn {
		background: none;
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text-muted);
		padding: 8px 16px;
		cursor: pointer;
		font-size: 13px;
	}

	.save-btn {
		background: var(--accent);
		border: none;
		border-radius: 8px;
		color: white;
		padding: 8px 16px;
		cursor: pointer;
		font-size: 13px;
		font-weight: 500;
	}

	.save-btn:hover {
		filter: brightness(1.1);
	}

	.form-error {
		background: rgba(239, 68, 68, 0.1);
		border: 1px solid rgba(239, 68, 68, 0.3);
		border-radius: 8px;
		color: #ef4444;
		padding: 8px 12px;
		font-size: 13px;
		margin-bottom: 12px;
	}

	/* Management view */
	.manage-view {
		padding: 8px 20px 20px;
		overflow-y: auto;
		flex: 1;
		display: flex;
		flex-direction: column;
	}

	.back-link {
		background: none;
		border: none;
		color: var(--accent);
		font-size: 13px;
		cursor: pointer;
		padding: 4px 0;
		text-align: left;
		margin-bottom: 8px;
	}

	.back-link:hover {
		text-decoration: underline;
	}

	.manage-list {
		flex: 1;
		overflow-y: auto;
	}

	.manage-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 0;
		border-bottom: 1px solid var(--border);
	}

	.manage-info {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.manage-name {
		font-weight: 500;
		color: var(--text-primary);
		font-size: 14px;
	}

	.manage-subtitle {
		font-size: 12px;
		color: var(--text-muted);
	}

	.manage-macros {
		font-size: 12px;
		color: var(--text-muted);
	}

	.manage-actions {
		display: flex;
		gap: 6px;
		flex-shrink: 0;
	}

	.edit-btn, .delete-btn {
		background: none;
		border: 1px solid var(--border);
		border-radius: 6px;
		padding: 4px 10px;
		font-size: 12px;
		cursor: pointer;
	}

	.edit-btn {
		color: var(--accent);
	}

	.edit-btn:hover {
		background: var(--bg-hover);
	}

	.delete-btn {
		color: #ef4444;
	}

	.delete-btn:hover {
		background: rgba(239, 68, 68, 0.1);
	}

	.import-export {
		display: flex;
		gap: 8px;
		padding-top: 12px;
		border-top: 1px solid var(--border);
		margin-top: auto;
	}

	.import-btn, .export-btn {
		flex: 1;
		background: none;
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text-muted);
		padding: 8px;
		font-size: 13px;
		cursor: pointer;
	}

	.import-btn:hover, .export-btn:hover {
		background: var(--bg-hover);
		color: var(--text-primary);
	}

	@media (max-width: 768px) {
		.modal {
			width: 100vw;
			height: 100vh;
			max-width: none;
			max-height: none;
			border-radius: 0;
			margin: 0;
		}

		.macro-grid, .portion-row, .micro-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
