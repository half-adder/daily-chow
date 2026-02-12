<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchFoods, solve, type Food, type SolveResponse, type SolvedIngredient, type MicroResult } from '$lib/api';
	import IngredientRow from '$lib/components/IngredientRow.svelte';
	import AddIngredientModal from '$lib/components/AddIngredientModal.svelte';

	// ── Micronutrient display info ──────────────────────────────────

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

	const MICRO_NAMES: Record<string, { name: string; unit: string }> = {
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
		vitamin_k_mcg: { name: 'Vitamin K', unit: 'mcg' }
	};

	// ── State ────────────────────────────────────────────────────────

	let foods = $state<Record<string, Food>>({});

	// Targets
	let dailyCal = $state(3500);
	let dailyPro = $state(160);
	let dailyFiberMin = $state(40);
	let smoothieCal = $state(720);
	let smoothiePro = $state(30);
	let smoothieFiber = $state(14);
	let calTol = $state(50);
	let proTol = $state(5);
	let objective = $state('minimize_oil');

	// Profile
	let sex = $state('male');
	let ageGroup = $state('19-30');

	// Micronutrient optimization
	let optimizeNutrients = $state<Set<string>>(new Set());
	let microsOpen = $state(false);

	// Ingredients
	interface IngredientEntry {
		key: string;
		enabled: boolean;
		minG: number;
		maxG: number;
	}

	let ingredients = $state<IngredientEntry[]>([
		{ key: 'white_rice_dry', enabled: true, minG: 0, maxG: 400 },
		{ key: 'broccoli_raw', enabled: true, minG: 200, maxG: 400 },
		{ key: 'carrots_raw', enabled: true, minG: 150, maxG: 300 },
		{ key: 'zucchini_raw', enabled: true, minG: 250, maxG: 500 },
		{ key: 'avocado_oil', enabled: true, minG: 0, maxG: 100 },
		{ key: 'black_beans_cooked', enabled: true, minG: 150, maxG: 400 },
		{ key: 'yellow_split_peas_dry', enabled: true, minG: 60, maxG: 150 },
		{ key: 'ground_beef_80_20_raw', enabled: true, minG: 0, maxG: 1000 },
		{ key: 'chicken_thigh_raw', enabled: true, minG: 0, maxG: 1000 },
	]);

	let solution = $state<SolveResponse | null>(null);
	let showAddModal = $state(false);
	let solving = $state(false);

	// Derived
	let mealCal = $derived(dailyCal - smoothieCal);
	let mealPro = $derived(dailyPro - smoothiePro);
	let mealFiberMin = $derived(dailyFiberMin - smoothieFiber);

	let existingKeys = $derived(new Set(ingredients.map((i) => i.key)));

	let macroPcts = $derived.by(() => {
		if (!solution || solution.status === 'infeasible') return null;
		const carbCal = solution.meal_carbs * 4;
		const proCal = solution.meal_protein * 4;
		const fatCal = solution.meal_fat * 9;
		const total = carbCal + proCal + fatCal;
		if (total <= 0) return null;
		const carb = Math.round((carbCal / total) * 100);
		const pro = Math.round((proCal / total) * 100);
		const fat = 100 - carb - pro;
		return { carb, pro, fat };
	});

	// ── Micro checkbox helpers ───────────────────────────────────────

	function toggleNutrient(key: string) {
		const next = new Set(optimizeNutrients);
		if (next.has(key)) next.delete(key);
		else next.add(key);
		optimizeNutrients = next;
		triggerSolve();
	}

	function groupState(keys: string[]): 'all' | 'none' | 'some' {
		let checked = 0;
		for (const k of keys) {
			if (optimizeNutrients.has(k)) checked++;
		}
		if (checked === 0) return 'none';
		if (checked === keys.length) return 'all';
		return 'some';
	}

	function toggleGroup(keys: string[]) {
		const state = groupState(keys);
		const next = new Set(optimizeNutrients);
		if (state === 'all') {
			for (const k of keys) next.delete(k);
		} else {
			for (const k of keys) next.add(k);
		}
		optimizeNutrients = next;
		triggerSolve();
	}

	// ── Solver ───────────────────────────────────────────────────────

	let solveTimeout: ReturnType<typeof setTimeout> | null = null;

	function triggerSolve() {
		if (solveTimeout) clearTimeout(solveTimeout);
		solveTimeout = setTimeout(doSolve, 30);
	}

	async function doSolve() {
		const enabled = ingredients.filter((i) => i.enabled);
		if (enabled.length === 0) {
			solution = {
				status: 'infeasible', ingredients: [], meal_calories: 0, meal_protein: 0,
				meal_fat: 0, meal_carbs: 0, meal_fiber: 0, micros: {}
			};
			return;
		}
		solving = true;
		try {
			solution = await solve(
				enabled.map((i) => ({ key: i.key, min_g: i.minG, max_g: i.maxG })),
				{
					meal_calories: mealCal,
					meal_protein: mealPro,
					meal_fiber_min: mealFiberMin,
					cal_tolerance: calTol,
					protein_tolerance: proTol
				},
				objective,
				sex,
				ageGroup,
				Array.from(optimizeNutrients)
			);
		} catch {
			solution = null;
		}
		solving = false;
		saveState();
	}

	function getSolved(key: string): SolvedIngredient | null {
		return solution?.ingredients.find((i) => i.key === key) ?? null;
	}

	// ── Persistence (localStorage) ───────────────────────────────────

	function saveState() {
		const state = {
			dailyCal, dailyPro, dailyFiberMin,
			smoothieCal, smoothiePro, smoothieFiber,
			calTol, proTol, objective, ingredients,
			sex, ageGroup,
			optimizeNutrients: Array.from(optimizeNutrients),
			microsOpen
		};
		localStorage.setItem('daily-chow', JSON.stringify(state));
	}

	function loadState() {
		const raw = localStorage.getItem('daily-chow');
		if (!raw) return;
		try {
			const s = JSON.parse(raw);
			dailyCal = s.dailyCal ?? 3500;
			dailyPro = s.dailyPro ?? 160;
			dailyFiberMin = s.dailyFiberMin ?? 40;
			smoothieCal = s.smoothieCal ?? 720;
			smoothiePro = s.smoothiePro ?? 30;
			smoothieFiber = s.smoothieFiber ?? 14;
			calTol = s.calTol ?? 50;
			proTol = s.proTol ?? 5;
			objective = s.objective ?? 'minimize_oil';
			if (s.ingredients) ingredients = s.ingredients;
			sex = s.sex ?? 'male';
			ageGroup = s.ageGroup ?? '19-30';
			if (s.optimizeNutrients) optimizeNutrients = new Set(s.optimizeNutrients);
			if (s.microsOpen !== undefined) microsOpen = s.microsOpen;
		} catch { /* ignore corrupt state */ }
	}

	// ── Actions ──────────────────────────────────────────────────────

	function addIngredient(key: string) {
		const food = foods[key];
		if (!food) return;
		ingredients = [...ingredients, {
			key,
			enabled: true,
			minG: food.default_min,
			maxG: food.default_max
		}];
		showAddModal = false;
		triggerSolve();
	}

	function removeIngredient(index: number) {
		ingredients = ingredients.filter((_, i) => i !== index);
		triggerSolve();
	}

	// ── Helpers ──────────────────────────────────────────────────────

	function pctColor(pct: number): string {
		if (pct >= 80) return '#22c55e';
		if (pct >= 50) return '#f59e0b';
		return '#ef4444';
	}

	function fmtMicro(val: number, unit: string): string {
		if (unit === 'mcg') return val < 10 ? val.toFixed(1) : Math.round(val).toString();
		if (val < 1) return val.toFixed(2);
		if (val < 10) return val.toFixed(1);
		return Math.round(val).toString();
	}

	// ── Init ─────────────────────────────────────────────────────────

	onMount(async () => {
		foods = await fetchFoods();
		loadState();
		doSolve();
	});
</script>

<div class="app">
	<header>
		<h1>Daily Chow</h1>
		<p class="subtitle">Meal macro solver</p>
	</header>

	<section class="targets-section">
		<div class="targets-row">
			<div class="target-group">
				<label>Daily cal</label>
				<div class="target-input-row">
					<input type="number" bind:value={dailyCal} onchange={triggerSolve} />
				</div>
			</div>
			<div class="target-group">
				<label>Protein</label>
				<div class="target-input-row">
					<input type="number" bind:value={dailyPro} onchange={triggerSolve} />
					<span class="unit">g</span>
				</div>
			</div>
			<div class="target-group">
				<label>Fiber ≥</label>
				<div class="target-input-row">
					<input type="number" bind:value={dailyFiberMin} onchange={triggerSolve} />
					<span class="unit">g</span>
				</div>
			</div>
			<div class="target-group">
				<label>Cal tol ±</label>
				<div class="target-input-row">
					<input type="number" bind:value={calTol} onchange={triggerSolve} />
				</div>
			</div>
			<div class="target-group">
				<label>Pro tol ±</label>
				<div class="target-input-row">
					<input type="number" bind:value={proTol} onchange={triggerSolve} />
					<span class="unit">g</span>
				</div>
			</div>
			<div class="target-group">
				<label>Objective</label>
				<div class="target-input-row">
					<select bind:value={objective} onchange={triggerSolve}>
						<option value="minimize_oil">Minimize oil</option>
						<option value="minimize_rice_deviation">Minimize rice deviation</option>
						<option value="minimize_total_grams">Minimize total grams</option>
					</select>
				</div>
			</div>
			<div class="target-group">
				<label>Sex</label>
				<div class="target-input-row">
					<select bind:value={sex} onchange={triggerSolve}>
						<option value="male">Male</option>
						<option value="female">Female</option>
					</select>
				</div>
			</div>
			<div class="target-group">
				<label>Age</label>
				<div class="target-input-row">
					<select bind:value={ageGroup} onchange={triggerSolve}>
						<option value="19-30">19-30</option>
						<option value="31-50">31-50</option>
						<option value="51-70">51-70</option>
						<option value="71+">71+</option>
					</select>
				</div>
			</div>
		</div>
		<div class="smoothie-row">
			Smoothie:
			<input type="number" bind:value={smoothieCal} onchange={triggerSolve} class="sm-input" /> kcal ·
			<input type="number" bind:value={smoothiePro} onchange={triggerSolve} class="sm-input" />g pro ·
			<input type="number" bind:value={smoothieFiber} onchange={triggerSolve} class="sm-input" />g fiber
		</div>
	</section>

	<section class="ingredients-section">
		<div class="ingredients-header">
			<span></span>
			<span>Ingredient</span>
			<span class="text-right">Min</span>
			<span class="text-center">Range</span>
			<span class="text-right">Max</span>
			<span class="text-right">Solved</span>
			<span class="header-macros"><span>kcal</span><span>/</span><span>pro</span></span>
			<span></span>
		</div>
		{#each ingredients as ing, i (ing.key)}
			{#if foods[ing.key]}
				<IngredientRow
					ingredientKey={ing.key}
					food={foods[ing.key]}
					bind:enabled={ing.enabled}
					bind:minG={ing.minG}
					bind:maxG={ing.maxG}
					solved={getSolved(ing.key)}
					onchange={triggerSolve}
					ontoggle={() => triggerSolve()}
					onremove={() => removeIngredient(i)}
				/>
			{/if}
		{/each}
		<button class="add-btn" onclick={() => (showAddModal = true)}>
			+ Add ingredient
		</button>
	</section>

	<section class="totals-section">
		{#if solution}
			<div class="totals-grid">
				<div class="total-item">
					<span class="total-label">Meal</span>
					<span class="total-cal">{Math.round(solution.meal_calories)} kcal</span>
					<span class="total-pro">{Math.round(solution.meal_protein)}g pro</span>
					<span class="total-fib">{Math.round(solution.meal_fiber)}g fiber</span>
				</div>
				<div class="total-item">
					<span class="total-label">Day</span>
					<span class="total-cal">{Math.round(solution.meal_calories + smoothieCal)} kcal</span>
					<span class="total-pro">{Math.round(solution.meal_protein + smoothiePro)}g pro</span>
					<span class="total-fib">{Math.round(solution.meal_fiber + smoothieFiber)}g fiber</span>
				</div>
				{#if macroPcts}
					<div class="macro-bar">
						<div class="macro-segment macro-carbs" style="width: {macroPcts.carb}%">
							{#if macroPcts.carb >= 10}<span>carb {macroPcts.carb}%</span>{/if}
						</div>
						<div class="macro-segment macro-protein" style="width: {macroPcts.pro}%">
							{#if macroPcts.pro >= 10}<span>pro {macroPcts.pro}%</span>{/if}
						</div>
						<div class="macro-segment macro-fat" style="width: {macroPcts.fat}%">
							{#if macroPcts.fat >= 10}<span>fat {macroPcts.fat}%</span>{/if}
						</div>
					</div>
				{/if}
				<div class="total-status" class:feasible={solution.status !== 'infeasible'} class:infeasible={solution.status === 'infeasible'}>
					{#if solution.status === 'infeasible'}
						✗ INFEASIBLE — widen ranges or disable ingredients
					{:else}
						✓ {solution.status.toUpperCase()}
					{/if}
				</div>
			</div>
		{:else if solving}
			<div class="solving">Solving...</div>
		{/if}
	</section>

	<!-- ── Micronutrient Report ─────────────────────────────────── -->
	{#if solution && solution.status !== 'infeasible' && solution.micros}
		<section class="micros-section">
			<button class="micros-toggle" onclick={() => { microsOpen = !microsOpen; saveState(); }}>
				<span class="micros-arrow" class:open={microsOpen}>▸</span>
				Micronutrients
				{#if optimizeNutrients.size > 0}
					<span class="micros-badge">{optimizeNutrients.size} optimized</span>
				{/if}
			</button>

			{#if microsOpen}
				<div class="micros-content">
					{#each MICRO_TIERS as tier}
						{@const gs = groupState(tier.keys)}
						<div class="micro-group">
							<label class="micro-group-header">
								<input
									type="checkbox"
									checked={gs === 'all'}
									indeterminate={gs === 'some'}
									onchange={() => toggleGroup(tier.keys)}
								/>
								<span class="micro-group-name">{tier.name}</span>
							</label>
							<div class="micro-items">
								{#each tier.keys as key}
									{@const m = solution.micros[key]}
									{@const info = MICRO_NAMES[key]}
									{#if m && info}
										{@const barPct = Math.min(m.pct, 100)}
										<label class="micro-row" class:dimmed={!optimizeNutrients.has(key)}>
											<input
												type="checkbox"
												checked={optimizeNutrients.has(key)}
												onchange={() => toggleNutrient(key)}
											/>
											<span class="micro-name">{info.name}</span>
											<div class="micro-bar-track">
												<div
													class="micro-bar-fill"
													style="width: {barPct}%; background: {pctColor(m.pct)}"
												></div>
											</div>
											<span class="micro-pct" style="color: {pctColor(m.pct)}">{Math.round(m.pct)}%</span>
											<span class="micro-amounts">
												{fmtMicro(m.total + m.smoothie, info.unit)} / {fmtMicro(m.dri, info.unit)} {info.unit}
											</span>
										</label>
									{/if}
								{/each}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</section>
	{/if}
</div>

{#if showAddModal}
	<AddIngredientModal
		{foods}
		{existingKeys}
		onselect={addIngredient}
		onclose={() => (showAddModal = false)}
	/>
{/if}

<style>
	:global(body) {
		margin: 0;
		background: #0a0a0a;
		color: #e2e8f0;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
	}

	.app {
		max-width: 1100px;
		margin: 0 auto;
		padding: 24px 20px;
	}

	header {
		margin-bottom: 24px;
	}

	h1 {
		margin: 0;
		font-size: 28px;
		font-weight: 700;
		letter-spacing: -0.02em;
	}

	.subtitle {
		margin: 4px 0 0;
		color: #64748b;
		font-size: 14px;
	}

	/* ── Targets ──────────────────────────────────────── */

	.targets-section {
		background: #0f172a;
		border: 1px solid #1e293b;
		border-radius: 12px;
		padding: 16px 20px;
		margin-bottom: 16px;
	}

	.targets-row {
		display: flex;
		flex-wrap: wrap;
		gap: 16px;
		align-items: end;
	}

	.target-group {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.target-group label {
		font-size: 11px;
		color: #64748b;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.target-input-row {
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.target-group input[type='number'],
	.target-group select {
		padding: 6px 10px;
		background: #1e1e2e;
		border: 1px solid #334155;
		border-radius: 6px;
		color: #e2e8f0;
		font-size: 14px;
		width: 80px;
		font-variant-numeric: tabular-nums;
	}

	.target-group select {
		width: auto;
		min-width: 100px;
	}

	.target-group input:focus,
	.target-group select:focus {
		border-color: #3b82f6;
		outline: none;
	}

	.unit {
		font-size: 12px;
		color: #64748b;
	}

	.smoothie-row {
		margin-top: 12px;
		font-size: 13px;
		color: #64748b;
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.sm-input {
		width: 48px;
		padding: 3px 6px;
		background: #1e1e2e;
		border: 1px solid #334155;
		border-radius: 4px;
		color: #94a3b8;
		font-size: 12px;
		text-align: center;
	}

	.sm-input:focus {
		border-color: #3b82f6;
		outline: none;
	}

	/* Hide number spinners */
	input[type='number']::-webkit-inner-spin-button,
	input[type='number']::-webkit-outer-spin-button {
		-webkit-appearance: none;
	}
	input[type='number'] {
		-moz-appearance: textfield;
	}

	/* ── Ingredients ──────────────────────────────────── */

	.ingredients-section {
		background: #0f172a;
		border: 1px solid #1e293b;
		border-radius: 12px;
		overflow: hidden;
		margin-bottom: 16px;
	}

	.ingredients-header {
		display: grid;
		grid-template-columns: 32px 180px 64px 1fr 64px 72px 100px 32px;
		gap: 8px;
		padding: 10px 12px;
		font-size: 11px;
		color: #475569;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		border-bottom: 1px solid #1e293b;
	}

	.ingredients-header .text-right {
		text-align: right;
	}

	.ingredients-header .text-center {
		text-align: center;
	}

	.header-macros {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
	}

	.header-macros span:first-child {
		text-align: right;
	}

	.header-macros span:nth-child(2) {
		text-align: center;
		padding: 0 4px;
	}

	.header-macros span:last-child {
		text-align: left;
	}

	.add-btn {
		width: 100%;
		padding: 12px;
		background: none;
		border: none;
		border-top: 1px solid #1e293b;
		color: #3b82f6;
		font-size: 14px;
		cursor: pointer;
		transition: background 0.15s;
	}

	.add-btn:hover {
		background: #1e293b;
	}

	/* ── Totals ───────────────────────────────────────── */

	.totals-section {
		background: #0f172a;
		border: 1px solid #1e293b;
		border-radius: 12px;
		padding: 16px 20px;
	}

	.totals-grid {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.total-item {
		display: flex;
		gap: 20px;
		align-items: baseline;
	}

	.total-label {
		font-size: 12px;
		color: #64748b;
		text-transform: uppercase;
		width: 40px;
	}

	.total-cal {
		color: #f59e0b;
		font-variant-numeric: tabular-nums;
		font-weight: 500;
	}

	.total-pro {
		color: #3b82f6;
		font-variant-numeric: tabular-nums;
		font-weight: 500;
	}

	.total-fib {
		color: #22c55e;
		font-variant-numeric: tabular-nums;
		font-weight: 500;
	}

	.total-status {
		font-size: 13px;
		font-weight: 600;
		margin-top: 4px;
	}

	.total-status.feasible {
		color: #22c55e;
	}

	.total-status.infeasible {
		color: #ef4444;
	}

	.solving {
		color: #64748b;
		font-size: 14px;
	}

	/* ── Macro bar ────────────────────────────────────── */

	.macro-bar {
		display: flex;
		height: 28px;
		border-radius: 6px;
		overflow: hidden;
		margin-top: 4px;
	}

	.macro-segment {
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 12px;
		font-weight: 600;
		color: #fff;
		white-space: nowrap;
		min-width: 0;
		transition: width 0.3s ease;
	}

	.macro-segment span {
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
	}

	.macro-carbs {
		background: #f59e0b;
	}

	.macro-protein {
		background: #3b82f6;
	}

	.macro-fat {
		background: #a855f7;
	}

	/* ── Micronutrients ──────────────────────────────── */

	.micros-section {
		background: #0f172a;
		border: 1px solid #1e293b;
		border-radius: 12px;
		margin-top: 16px;
		overflow: hidden;
	}

	.micros-toggle {
		width: 100%;
		padding: 14px 20px;
		background: none;
		border: none;
		color: #e2e8f0;
		font-size: 15px;
		font-weight: 600;
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: 8px;
		text-align: left;
		transition: background 0.15s;
	}

	.micros-toggle:hover {
		background: #1e293b44;
	}

	.micros-arrow {
		display: inline-block;
		transition: transform 0.15s;
		font-size: 14px;
		color: #64748b;
	}

	.micros-arrow.open {
		transform: rotate(90deg);
	}

	.micros-badge {
		font-size: 11px;
		font-weight: 500;
		color: #3b82f6;
		background: #1e3a5f;
		padding: 2px 8px;
		border-radius: 10px;
		margin-left: auto;
	}

	.micros-content {
		padding: 0 20px 16px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.micro-group {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.micro-group-header {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 0;
		cursor: pointer;
	}

	.micro-group-header input[type='checkbox'] {
		accent-color: #3b82f6;
		width: 15px;
		height: 15px;
		cursor: pointer;
	}

	.micro-group-name {
		font-size: 12px;
		font-weight: 600;
		color: #94a3b8;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.micro-items {
		display: flex;
		flex-direction: column;
		gap: 1px;
		padding-left: 4px;
	}

	.micro-row {
		display: grid;
		grid-template-columns: 20px 120px 1fr 48px 120px;
		gap: 8px;
		align-items: center;
		padding: 4px 0;
		cursor: pointer;
		transition: opacity 0.15s;
	}

	.micro-row.dimmed {
		opacity: 0.45;
	}

	.micro-row:hover {
		opacity: 1;
	}

	.micro-row input[type='checkbox'] {
		accent-color: #3b82f6;
		width: 14px;
		height: 14px;
		cursor: pointer;
	}

	.micro-name {
		font-size: 13px;
		color: #cbd5e1;
	}

	.micro-bar-track {
		height: 8px;
		background: #1e293b;
		border-radius: 4px;
		overflow: hidden;
	}

	.micro-bar-fill {
		height: 100%;
		border-radius: 4px;
		transition: width 0.3s ease;
		min-width: 2px;
	}

	.micro-pct {
		font-size: 13px;
		font-weight: 600;
		text-align: right;
		font-variant-numeric: tabular-nums;
	}

	.micro-amounts {
		font-size: 12px;
		color: #64748b;
		font-variant-numeric: tabular-nums;
		text-align: right;
	}
</style>
