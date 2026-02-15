<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchFoods, solve, type Food, type SolveResponse, type SolvedIngredient, type MicroResult, type PinnedMeal } from '$lib/api';
	import IngredientRow from '$lib/components/IngredientRow.svelte';
	import AddIngredientModal from '$lib/components/AddIngredientModal.svelte';
	import PinnedMealModal from '$lib/components/PinnedMealModal.svelte';
	import StackedBar from '$lib/components/StackedBar.svelte';
	import MacroRatioBar from '$lib/components/MacroRatioBar.svelte';
	import { INGREDIENT_COLORS, assignColor, computeContributions, enrichWithDri, type IngredientContribution } from '$lib/contributions';

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

	let foods = $state<Record<number, Food>>({});

	// Targets
	let dailyCal = $state(3500);
	let dailyPro = $state(160);
	let dailyFiberMin = $state(40);
	let pinnedMeals = $state<PinnedMeal[]>([]);
	let calTol = $state(50);
	let carbPct = $state(50);
	let proteinPct = $state(25);
	let fatPct = $state(25);
	let priorities = $state<string[]>(['micros', 'macro_ratio', 'total_weight']);
	let theme = $state<'dark' | 'light'>('dark');

	// Slider scale
	let sliderAbsMax = $state(500);

	// Clamp ingredient bounds when absMax changes
	$effect(() => {
		const cap = sliderAbsMax;
		let changed = false;
		for (const ing of ingredients) {
			if (ing.maxG > cap) { ing.maxG = cap; changed = true; }
			if (ing.minG > cap) { ing.minG = cap; changed = true; }
		}
		if (changed) triggerSolve();
	});

	// Profile
	let sex = $state('male');
	let ageGroup = $state('19-30');

	// Micronutrient optimization
	let optimizeNutrients = $state<Set<string>>(new Set());
	let microsOpen = $state(true);

	// Ingredients
	interface IngredientEntry {
		key: number; // FDC ID
		enabled: boolean;
		minG: number;
		maxG: number;
		color: string;
	}

	const DEFAULT_INGREDIENTS: IngredientEntry[] = [
		{ key: 2512381, enabled: true, minG: 0, maxG: 400, color: INGREDIENT_COLORS[0] },  // White rice, raw
		{ key: 747447, enabled: true, minG: 200, maxG: 400, color: INGREDIENT_COLORS[1] },  // Broccoli, raw
		{ key: 2258586, enabled: true, minG: 150, maxG: 300, color: INGREDIENT_COLORS[2] }, // Carrots, raw
		{ key: 2685568, enabled: true, minG: 250, maxG: 500, color: INGREDIENT_COLORS[3] }, // Zucchini, raw
		{ key: 173573, enabled: true, minG: 0, maxG: 100, color: INGREDIENT_COLORS[4] },    // Avocado oil
		{ key: 173735, enabled: true, minG: 150, maxG: 400, color: INGREDIENT_COLORS[5] },  // Black beans, cooked
		{ key: 172429, enabled: true, minG: 60, maxG: 150, color: INGREDIENT_COLORS[6] },   // Split peas, cooked
		{ key: 2514744, enabled: true, minG: 0, maxG: 500, color: INGREDIENT_COLORS[7] },   // Ground beef 80/20, raw
		{ key: 2646171, enabled: true, minG: 0, maxG: 500, color: INGREDIENT_COLORS[8] },   // Chicken thigh, raw
	];

	let ingredients = $state<IngredientEntry[]>([...DEFAULT_INGREDIENTS]);

	let solution = $state<SolveResponse | null>(null);
	let showAddModal = $state(false);
	let solving = $state(false);
	let pinnedMealsOpen = $state(true);
	let showPinnedModal = $state(false);
	let editingPinnedMeal = $state<PinnedMeal | null>(null);

	// Expand states
	let expandedIngredient = $state<number | null>(null);
	let expandedMacro = $state(false);
	let expandedMicro = $state<string | null>(null);

	// Derived
	const MACRO_KEYS = new Set(['calories_kcal', 'protein_g', 'fat_g', 'carbs_g', 'fiber_g']);
	const MICRO_BAR_MAX = 200; // bar shows 0–200% of DRI

	let pinnedTotals = $derived.by(() => {
		const totals: Record<string, number> = {};
		for (const meal of pinnedMeals) {
			for (const [key, val] of Object.entries(meal.nutrients)) {
				totals[key] = (totals[key] ?? 0) + val;
			}
		}
		return totals;
	});

	let pinnedMicros = $derived.by(() => {
		const micros: Record<string, number> = {};
		for (const [key, val] of Object.entries(pinnedTotals)) {
			if (!MACRO_KEYS.has(key)) {
				micros[key] = val;
			}
		}
		return micros;
	});

	let mealCal = $derived(dailyCal - (pinnedTotals.calories_kcal ?? 0));
	let mealPro = $derived(dailyPro - (pinnedTotals.protein_g ?? 0));
	let mealFiberMin = $derived(dailyFiberMin - (pinnedTotals.fiber_g ?? 0));

	let existingKeys = $derived(new Set<number>(ingredients.map((i) => i.key)));

	// Ingredient color map for stacked bars
	let ingredientColorMap = $derived(
		new Map(ingredients.map((i) => [i.key, i.color]))
	);

	// Per-ingredient contributions (derived from solution)
	let contributions = $derived.by(() => {
		if (!solution || solution.status === 'infeasible') return new Map<number, IngredientContribution>();
		const contribs = computeContributions(solution, foods);
		enrichWithDri(contribs, solution.micros);
		return contribs;
	});

	let macroPcts = $derived.by(() => {
		if (!solution || solution.status === 'infeasible') return null;
		const carbCal = (solution.meal_carbs_g + (pinnedTotals.carbs_g ?? 0)) * 4;
		const proCal = (solution.meal_protein_g + (pinnedTotals.protein_g ?? 0)) * 4;
		const fatCal = (solution.meal_fat_g + (pinnedTotals.fat_g ?? 0)) * 9;
		const total = carbCal + proCal + fatCal;
		if (total <= 0) return null;
		const carb = Math.round((carbCal / total) * 100);
		const pro = Math.round((proCal / total) * 100);
		const fat = 100 - carb - pro;
		return { carb, pro, fat };
	});

	// ── Theme ───────────────────────────────────────────────────────

	function applyTheme(t: 'dark' | 'light') {
		if (t === 'light') document.documentElement.dataset.theme = 'light';
		else delete document.documentElement.dataset.theme;
	}

	function toggleTheme() {
		theme = theme === 'dark' ? 'light' : 'dark';
		applyTheme(theme);
		saveState();
	}

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

	function addPinnedMeal(meal: PinnedMeal) {
		pinnedMeals = [...pinnedMeals, meal];
		showPinnedModal = false;
		editingPinnedMeal = null;
		triggerSolve();
	}

	function updatePinnedMeal(updated: PinnedMeal) {
		pinnedMeals = pinnedMeals.map((m) => m.id === updated.id ? updated : m);
		showPinnedModal = false;
		editingPinnedMeal = null;
		triggerSolve();
	}

	function removePinnedMeal(id: string) {
		pinnedMeals = pinnedMeals.filter((m) => m.id !== id);
		triggerSolve();
	}

	function exportPinnedMeal(meal: PinnedMeal) {
		const data = { name: meal.name, nutrients: meal.nutrients };
		const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `${meal.name.toLowerCase().replace(/\s+/g, '-')}.json`;
		a.click();
		URL.revokeObjectURL(url);
	}

	async function doSolve() {
		const enabled = ingredients.filter((i) => i.enabled);
		if (enabled.length === 0) {
			solution = {
				status: 'infeasible', ingredients: [], meal_calories_kcal: 0, meal_protein_g: 0,
				meal_fat_g: 0, meal_carbs_g: 0, meal_fiber_g: 0, micros: {}
			};
			return;
		}
		solving = true;
		try {
			solution = await solve(
				enabled.map((i) => ({ key: i.key, min_g: i.minG, max_g: i.maxG })),
				{
					meal_calories_kcal: mealCal,
					meal_protein_min_g: mealPro,
					meal_fiber_min_g: mealFiberMin,
					cal_tolerance: calTol
				},
				sex,
				ageGroup,
				Array.from(optimizeNutrients),
				priorities,
				pinnedMicros,
				{
					carb_pct: carbPct, protein_pct: proteinPct, fat_pct: fatPct,
					pinned_carb_g: pinnedTotals.carbs_g ?? 0,
					pinned_protein_g: pinnedTotals.protein_g ?? 0,
					pinned_fat_g: pinnedTotals.fat_g ?? 0
				}
			);
		} catch {
			solution = null;
		}
		solving = false;
		saveState();
	}

	function getSolved(key: number): SolvedIngredient | null {
		return solution?.ingredients.find((i) => i.key === key) ?? null;
	}

	// ── Persistence (localStorage) ───────────────────────────────────

	function saveState() {
		const state = {
			dailyCal, dailyPro, dailyFiberMin,
			pinnedMeals, pinnedMealsOpen,
			calTol, carbPct, proteinPct, fatPct,
			priorities, theme, ingredients,
			sex, ageGroup,
			optimizeNutrients: Array.from(optimizeNutrients),
			microsOpen, sliderAbsMax
		};
		localStorage.setItem('daily-chow', JSON.stringify(state));
	}

	function loadState() {
		const raw = localStorage.getItem('daily-chow');
		if (!raw) return;
		try {
			const s = JSON.parse(raw);
			// Detect old slug-based state (keys are strings instead of numbers)
			if (s.ingredients?.length > 0 && typeof s.ingredients[0].key === 'string') {
				// Discard old state, use defaults
				localStorage.removeItem('daily-chow');
				return;
			}
			dailyCal = s.dailyCal ?? 3500;
			dailyPro = s.dailyPro ?? 160;
			dailyFiberMin = s.dailyFiberMin ?? 40;
			if (s.pinnedMeals) pinnedMeals = s.pinnedMeals;
			if (s.pinnedMealsOpen !== undefined) pinnedMealsOpen = s.pinnedMealsOpen;
			calTol = s.calTol ?? 50;
			if (s.carbPct !== undefined) carbPct = s.carbPct;
			if (s.proteinPct !== undefined) proteinPct = s.proteinPct;
			if (s.fatPct !== undefined) fatPct = s.fatPct;
			// Migrate from old objective/microStrategy to priorities
			if (s.priorities && Array.isArray(s.priorities)) {
				priorities = s.priorities;
				// Backfill macro_ratio into old priority lists
				if (!priorities.includes('macro_ratio')) {
					const idx = priorities.indexOf('total_weight');
					if (idx >= 0) priorities.splice(idx, 0, 'macro_ratio');
					else priorities.push('macro_ratio');
				}
			} else {
				priorities = ['micros', 'macro_ratio', 'total_weight'];
			}
			if (s.theme === 'light' || s.theme === 'dark') theme = s.theme;
			if (s.ingredients) {
				ingredients = s.ingredients;
				// Backfill colors for ingredients saved before color support
				const usedColors = ingredients.filter((i) => i.color).map((i) => i.color);
				for (const ing of ingredients) {
					if (!ing.color) {
						ing.color = assignColor(usedColors);
						usedColors.push(ing.color);
					}
				}
			}
			sex = s.sex ?? 'male';
			ageGroup = s.ageGroup ?? '19-30';
			if (s.optimizeNutrients) optimizeNutrients = new Set(s.optimizeNutrients);
			if (s.microsOpen !== undefined) microsOpen = s.microsOpen;
			if (s.sliderAbsMax) sliderAbsMax = s.sliderAbsMax;
		} catch { /* ignore corrupt state */ }
	}

	// ── Actions ──────────────────────────────────────────────────────

	function addIngredient(key: number) {
		const food = foods[key];
		if (!food) return;
		const usedColors = ingredients.map((i) => i.color);
		ingredients = [...ingredients, {
			key,
			enabled: true,
			minG: 0,
			maxG: 500,
			color: assignColor(usedColors)
		}];
		showAddModal = false;
		triggerSolve();
	}

	function removeIngredient(index: number) {
		ingredients = ingredients.filter((_, i) => i !== index);
		triggerSolve();
	}

	// ── Helpers ──────────────────────────────────────────────────────

	function pctColor(pct: number, earPct: number | null = null, ulPct: number | null = null): string {
		if (ulPct !== null && pct > ulPct) return '#ef4444';
		if (pct >= 100) return '#22c55e';
		if (earPct !== null) {
			if (pct >= earPct) return '#f59e0b';
			return '#ef4444';
		}
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

	function macroStackedSegments(macro: 'cal' | 'pro' | 'fat' | 'carb' | 'fiber') {
		if (!solution || solution.status === 'infeasible') return [];

		const pinnedKeyMap: Record<string, string> = {
			cal: 'calories_kcal', pro: 'protein_g', fat: 'fat_g', carb: 'carbs_g', fiber: 'fiber_g'
		};
		const mealTotalMap: Record<string, number> = {
			cal: solution.meal_calories_kcal,
			pro: solution.meal_protein_g,
			fat: solution.meal_fat_g,
			carb: solution.meal_carbs_g,
			fiber: solution.meal_fiber_g,
		};
		const pinnedVal = pinnedTotals[pinnedKeyMap[macro]] ?? 0;
		const dayTotal = mealTotalMap[macro] + pinnedVal;
		if (dayTotal <= 0) return [];

		const segments = solution.ingredients
			.map((ing) => {
				const color = ingredientColorMap.get(ing.key) ?? '#666';
				const food = foods[ing.key];
				const name = food?.name ?? String(ing.key);
				let val = 0;
				if (macro === 'cal') val = ing.calories_kcal;
				else if (macro === 'pro') val = ing.protein_g;
				else if (macro === 'fat') val = ing.fat_g;
				else if (macro === 'carb') val = ing.carbs_g;
				else val = ing.fiber_g;
				const pct = (val / dayTotal) * 100;
				return { key: String(ing.key), label: name, value: `${Math.round(val)}${macro === 'cal' ? ' kcal' : 'g'}`, pct, color };
			})
			.filter((s) => s.pct > 0.5);

		if (pinnedVal > 0) {
			const pinnedPct = (pinnedVal / dayTotal) * 100;
			if (pinnedPct > 0.5) {
				segments.push({
					key: '_pinned',
					label: 'Pinned',
					value: `${Math.round(pinnedVal)}${macro === 'cal' ? ' kcal' : 'g'}`,
					pct: pinnedPct,
					color: '#94a3b8'
				});
			}
		}

		return segments;
	}

	function microStackedSegments(microKey: string) {
		if (!solution || solution.status === 'infeasible') return [];
		const mr = solution.micros[microKey];
		if (!mr || mr.dri <= 0) return [];
		const info = MICRO_NAMES[microKey];
		// Compute raw amounts per ingredient
		const raw: { key: string; label: string; value: string; amount: number; color: string }[] = [];
		for (const ing of solution.ingredients) {
			const food = foods[ing.key];
			if (!food) continue;
			const per100g = food.micros[microKey] ?? 0;
			const amount = (per100g * ing.grams) / 100;
			if (amount <= 0) continue;
			const color = ingredientColorMap.get(ing.key) ?? '#666';
			raw.push({ key: String(ing.key), label: food.name, value: `${fmtMicro(amount, info?.unit ?? '')} ${info?.unit ?? ''}`, amount, color });
		}
		if (mr.pinned > 0) {
			raw.push({ key: '_pinned', label: 'Pinned', value: `${fmtMicro(mr.pinned, info?.unit ?? '')} ${info?.unit ?? ''}`, amount: mr.pinned, color: '#94a3b8' });
		}
		// Scale so segments fill 100% of the track
		const total = raw.reduce((s, r) => s + r.amount, 0);
		if (total <= 0) return [];
		return raw
			.map((r) => ({ key: r.key, label: r.label, value: r.value, pct: (r.amount / total) * 100, color: r.color }))
			.filter((s) => s.pct > 0.5);
	}

	// ── Init ─────────────────────────────────────────────────────────

	onMount(async () => {
		foods = await fetchFoods();
		loadState();
		applyTheme(theme);
		doSolve();
	});
</script>

<div class="app">
	<header>
		<div class="header-row">
			<h1>Daily Chow</h1>
			<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
			<div class="theme-switch" onclick={toggleTheme} title="Toggle light/dark mode">
				<svg class="theme-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
					<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>
				</svg>
				<div class="switch-track" class:light={theme === 'light'}>
					<div class="switch-thumb"></div>
				</div>
				<svg class="theme-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
					<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>
				</svg>
			</div>
		</div>
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
				<label>Protein ≥</label>
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
			<div class="target-group priority-group">
				<label>Solve priorities</label>
				<div class="priority-list">
					{#each priorities as p, i}
						<div class="priority-row">
							<span class="priority-rank">{i + 1}.</span>
							<button class="priority-btn" disabled={i === 0} onclick={() => { [priorities[i - 1], priorities[i]] = [priorities[i], priorities[i - 1]]; priorities = [...priorities]; triggerSolve(); }} title="Move up">&#9650;</button>
							<button class="priority-btn" disabled={i === priorities.length - 1} onclick={() => { [priorities[i], priorities[i + 1]] = [priorities[i + 1], priorities[i]]; priorities = [...priorities]; triggerSolve(); }} title="Move down">&#9660;</button>
							<span class="priority-label">{p === 'micros' ? 'Micronutrient coverage' : p === 'macro_ratio' ? 'Macro ratio target' : 'Minimize total weight'}</span>
						</div>
					{/each}
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
			<div class="target-group">
				<label>Max / ingr</label>
				<div class="target-input-row">
					<input type="number" value={sliderAbsMax} onchange={(e) => {
						const val = parseInt((e.target as HTMLInputElement).value);
						if (!isNaN(val) && val > 0) sliderAbsMax = val;
					}} />
					<span class="unit">g</span>
				</div>
			</div>
		</div>
		<div class="ratio-target">
			<label>Macro target</label>
			<MacroRatioBar
				{carbPct}
				{proteinPct}
				{fatPct}
				onchange={(c, p, f) => { carbPct = c; proteinPct = p; fatPct = f; triggerSolve(); }}
			/>
		</div>
	</section>

	<section class="pinned-section">
		<div class="pinned-header">
			<button class="pinned-toggle" onclick={() => { pinnedMealsOpen = !pinnedMealsOpen; }}>
				<span class="pinned-arrow" class:open={pinnedMealsOpen}>▸</span>
				Pinned Meals
				{#if pinnedMeals.length > 0}
					<span class="pinned-badge">{pinnedMeals.length}</span>
				{/if}
			</button>
			<button class="add-pinned-btn" onclick={() => { editingPinnedMeal = null; showPinnedModal = true; }}>+ Add</button>
		</div>
		{#if pinnedMealsOpen}
			{#if pinnedMeals.length === 0}
				<div class="pinned-empty">No pinned meals. Add one to subtract from daily targets.</div>
			{:else}
				{#each pinnedMeals as meal (meal.id)}
					<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
					<div class="pinned-row" onclick={() => { editingPinnedMeal = meal; showPinnedModal = true; }}>
						<span class="pinned-name">{meal.name}</span>
						<span class="pinned-macros">
							{meal.nutrients.calories_kcal ?? 0} kcal ·
							{meal.nutrients.protein_g ?? 0}g pro ·
							{meal.nutrients.fat_g ?? 0}g fat ·
							{meal.nutrients.carbs_g ?? 0}g carb ·
							{meal.nutrients.fiber_g ?? 0}g fib
						</span>
						<button class="pinned-export" onclick={(e) => { e.stopPropagation(); exportPinnedMeal(meal); }} title="Export JSON">↓</button>
						<button class="pinned-remove" onclick={(e) => { e.stopPropagation(); removePinnedMeal(meal.id); }} title="Remove">×</button>
					</div>
				{/each}
			{/if}
		{/if}
	</section>

	<div class="main-columns">
	<div class="left-column">
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
					color={ing.color}
					bind:enabled={ing.enabled}
					bind:minG={ing.minG}
					bind:maxG={ing.maxG}
					absMax={sliderAbsMax}
					solved={getSolved(ing.key)}
					contribution={contributions.get(ing.key) ?? null}
					expanded={expandedIngredient === ing.key}
					onchange={triggerSolve}
					ontoggle={() => triggerSolve()}
					onremove={() => removeIngredient(i)}
					onexpand={() => { expandedIngredient = expandedIngredient === ing.key ? null : ing.key; }}
				/>
			{/if}
		{/each}
		<button class="add-btn" onclick={() => (showAddModal = true)}>
			+ Add ingredient
		</button>
	</section>

	</div><!-- /.left-column -->

	<!-- ── Right Column: Macros + Micros ──────────────────────────── -->
	<div class="right-column">
	<section class="totals-section">
		{#if solution}
			<div class="totals-grid">
				<div class="total-item">
					<span class="total-label">Meal</span>
					<span class="total-cal">{Math.round(solution.meal_calories_kcal)} kcal</span>
					<span class="total-pro">{Math.round(solution.meal_protein_g)}g pro</span>
					<span class="total-fib">{Math.round(solution.meal_fiber_g)}g fiber</span>
				</div>
				<div class="total-item">
					<span class="total-label">Day</span>
					<span class="total-cal">{Math.round(solution.meal_calories_kcal + (pinnedTotals.calories_kcal ?? 0))} kcal</span>
					<span class="total-pro">{Math.round(solution.meal_protein_g + (pinnedTotals.protein_g ?? 0))}g pro</span>
					<span class="total-fib">{Math.round(solution.meal_fiber_g + (pinnedTotals.fiber_g ?? 0))}g fiber</span>
				</div>
				{#if macroPcts}
					<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
					<div class="macro-bar clickable" onclick={() => { expandedMacro = !expandedMacro; }}>
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
					{#if expandedMacro}
						<div class="macro-breakdown">
							<div class="breakdown-row">
								<span class="breakdown-label">Calories</span>
								<StackedBar segments={macroStackedSegments('cal')} />
							</div>
							<div class="breakdown-row">
								<span class="breakdown-label">Protein</span>
								<StackedBar segments={macroStackedSegments('pro')} />
							</div>
							<div class="breakdown-row">
								<span class="breakdown-label">Fat</span>
								<StackedBar segments={macroStackedSegments('fat')} />
							</div>
							<div class="breakdown-row">
								<span class="breakdown-label">Carbs</span>
								<StackedBar segments={macroStackedSegments('carb')} />
							</div>
							<div class="breakdown-row">
								<span class="breakdown-label">Fiber</span>
								<StackedBar segments={macroStackedSegments('fiber')} />
							</div>
						</div>
					{/if}
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

	{#if solution && solution.status !== 'infeasible' && solution.micros}
		<section class="micros-section">
			<div class="micros-header">
				<span class="micros-title">Micronutrients</span>
				{#if optimizeNutrients.size > 0}
					<span class="micros-badge">{optimizeNutrients.size} optimized</span>
				{/if}
			</div>

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
									{@const earPct = m.ear !== null && m.dri > 0 ? m.ear / m.dri * 100 : null}
									{@const ulPct = m.ul !== null && m.dri > 0 ? m.ul / m.dri * 100 : null}
									{@const barPct = Math.min(m.pct / MICRO_BAR_MAX * 100, 100)}
									{@const zoneColor = pctColor(m.pct, earPct, ulPct)}
									<div class="micro-row-wrapper">
										<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
										<div class="micro-row" class:dimmed={!optimizeNutrients.has(key)}>
											<input
												type="checkbox"
												checked={optimizeNutrients.has(key)}
												onchange={() => toggleNutrient(key)}
											/>
											<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
											<span class="micro-name clickable" onclick={() => toggleNutrient(key)}>{info.name}</span>
											<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
											<div class="micro-bar-track clickable" onclick={() => { expandedMicro = expandedMicro === key ? null : key; }}>
												{#if earPct !== null || ulPct !== null}
													{@const rangeLeft = earPct !== null ? Math.min(earPct / MICRO_BAR_MAX * 100, 100) : 0}
													{@const rangeRight = ulPct !== null ? Math.min(ulPct / MICRO_BAR_MAX * 100, 100) : 100}
													<div class="micro-bar-range" style="left: {rangeLeft}%; right: {100 - rangeRight}%; --bar-color: {zoneColor}"></div>
												{/if}
												<div
													class="micro-bar-fill"
													style="width: {barPct}%; --bar-color: {zoneColor}"
												></div>
												<div class="micro-bar-rdi-tick" style="left: 50%"></div>
											</div>
											<span class="micro-pct" style="color: {zoneColor}">{Math.round(m.pct)}%</span>
											<span class="micro-amounts">
												{fmtMicro(m.total + m.pinned, info.unit)} / {fmtMicro(m.dri, info.unit)} {info.unit}
											</span>
										</div>
										{#if expandedMicro === key}
											<div class="micro-breakdown">
												<div class="micro-breakdown-track">
													<StackedBar segments={microStackedSegments(key)} height={16} />
												</div>
											</div>
										{/if}
									</div>
								{/if}
							{/each}
						</div>
					</div>
				{/each}
			</div>
		</section>
	{/if}
	</div><!-- /.right-column -->
	</div><!-- /.main-columns -->
</div>

{#if showAddModal}
	<AddIngredientModal
		{foods}
		{existingKeys}
		microResults={solution?.micros ?? {}}
		onselect={addIngredient}
		onclose={() => (showAddModal = false)}
	/>
{/if}

{#if showPinnedModal}
	<PinnedMealModal
		meal={editingPinnedMeal}
		onsave={(meal) => {
			if (editingPinnedMeal) updatePinnedMeal(meal);
			else addPinnedMeal(meal);
		}}
		onclose={() => { showPinnedModal = false; editingPinnedMeal = null; }}
	/>
{/if}

<style>
	:global(body) {
		margin: 0;
		background: var(--bg-body);
		color: var(--text-primary);
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
	}

	.app {
		max-width: 1600px;
		margin: 0 auto;
		padding: 24px 20px;
	}

	header {
		margin-bottom: 24px;
	}

	.header-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	h1 {
		margin: 0;
		font-size: 28px;
		font-weight: 700;
		letter-spacing: -0.02em;
	}

	.theme-switch {
		display: flex;
		align-items: center;
		gap: 6px;
		color: var(--text-muted);
		cursor: pointer;
		user-select: none;
	}

	.switch-track {
		position: relative;
		width: 36px;
		height: 20px;
		background: var(--border-input);
		border-radius: 10px;
		transition: background 0.2s;
	}

	.switch-track.light {
		background: #3b82f6;
	}

	.switch-thumb {
		position: absolute;
		top: 2px;
		left: 2px;
		width: 16px;
		height: 16px;
		background: #fff;
		border-radius: 50%;
		transition: transform 0.2s;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
	}

	.switch-track.light .switch-thumb {
		transform: translateX(16px);
	}

	.subtitle {
		margin: 4px 0 0;
		color: var(--text-muted);
		font-size: 14px;
	}

	/* ── Targets ──────────────────────────────────────── */

	.targets-section {
		background: var(--bg-panel);
		border: 1px solid var(--border);
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

	.ratio-target {
		padding: 8px 0 0;
	}

	.ratio-target label {
		font-size: 11px;
		font-weight: 600;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin-bottom: 6px;
		display: block;
	}

	.target-group {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.target-group label {
		font-size: 11px;
		color: var(--text-muted);
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
		background: var(--bg-input);
		border: 1px solid var(--border-input);
		border-radius: 6px;
		color: var(--text-primary);
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

	.priority-group {
		min-width: 200px;
	}

	.priority-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.priority-row {
		display: flex;
		align-items: center;
		gap: 4px;
		font-size: 13px;
	}

	.priority-rank {
		width: 16px;
		text-align: right;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}

	.priority-btn {
		background: none;
		border: 1px solid var(--border-input);
		border-radius: 4px;
		color: var(--text-muted);
		cursor: pointer;
		padding: 1px 4px;
		font-size: 10px;
		line-height: 1;
	}

	.priority-btn:hover:not(:disabled) {
		color: var(--text-primary);
		border-color: var(--text-primary);
	}

	.priority-btn:disabled {
		opacity: 0.25;
		cursor: default;
	}

	.priority-label {
		color: var(--text-primary);
	}

	.unit {
		font-size: 12px;
		color: var(--text-muted);
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
		background: var(--bg-panel);
		border: 1px solid var(--border);
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
		color: var(--text-dim);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		border-bottom: 1px solid var(--border);
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
		border-top: 1px solid var(--border);
		color: #3b82f6;
		font-size: 14px;
		cursor: pointer;
		transition: background 0.15s;
	}

	.add-btn:hover {
		background: var(--bg-hover);
	}

	/* ── Two-column layout ────────────────────────────── */

	.main-columns {
		display: grid;
		grid-template-columns: 1fr 380px;
		gap: 16px;
		align-items: start;
	}

	.left-column {
		min-width: 0;
	}

	.right-column {
		display: flex;
		flex-direction: column;
		gap: 16px;
		position: sticky;
		top: 16px;
		align-self: start;
	}

	@media (max-width: 1200px) {
		.main-columns {
			grid-template-columns: 1fr;
		}
		.right-column {
			position: static;
		}
	}

	/* ── Totals ───────────────────────────────────────── */

	.totals-section {
		background: var(--bg-panel);
		border: 1px solid var(--border);
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
		color: var(--text-muted);
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
		color: var(--text-muted);
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
		background: var(--bg-panel);
		border: 1px solid var(--border);
		border-radius: 12px;
	}

	.micros-header {
		padding: 14px 20px;
		display: flex;
		align-items: center;
		gap: 8px;
		border-bottom: 1px solid var(--border);
	}

	.micros-title {
		font-size: 15px;
		font-weight: 600;
		color: var(--text-primary);
	}

	.micros-badge {
		font-size: 11px;
		font-weight: 500;
		color: #3b82f6;
		background: var(--bg-badge);
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
		color: var(--text-secondary);
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
		grid-template-columns: 20px 100px 1fr 50px 100px;
		gap: 6px;
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
		color: var(--text-micro);
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.micro-bar-track {
		height: 8px;
		border-radius: 2px;
		overflow: visible;
		position: relative;
		background: var(--bg-track, #e2e8f0);
		min-width: 0;
	}

	.micro-bar-range {
		position: absolute;
		top: -4px;
		bottom: -4px;
		border-radius: 0;
		opacity: 0.15;
		background: var(--bar-color) !important;
	}

	.micro-bar-fill {
		height: 100%;
		border-radius: 2px;
		transition: width 0.3s ease;
		min-width: 2px;
		position: relative;
		z-index: 1;
		overflow: hidden;
		background: var(--bar-color) !important;
	}

	.micro-bar-rdi-tick {
		position: absolute;
		top: -3px;
		bottom: -3px;
		width: 2px;
		background: var(--text-secondary, #64748b);
		opacity: 0.5;
		z-index: 2;
		border-radius: 1px;
	}

	.micro-pct {
		font-size: 13px;
		font-weight: 600;
		text-align: right;
		font-variant-numeric: tabular-nums;
		min-width: 0;
		overflow: hidden;
		white-space: nowrap;
	}

	.micro-amounts {
		font-size: 12px;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
		text-align: right;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* ── Clickable / Expandable ──────────────────────── */

	.clickable {
		cursor: pointer;
	}

	.macro-breakdown {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 8px 0 4px;
	}

	.breakdown-row {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.breakdown-label {
		font-size: 11px;
		color: var(--text-muted);
		text-transform: uppercase;
		width: 60px;
		flex-shrink: 0;
	}

	.micro-row-wrapper {
		display: flex;
		flex-direction: column;
	}

	.micro-breakdown {
		padding: 2px 0 6px;
	}

	.micro-breakdown-track {
		background: var(--bg-track);
		border-radius: 6px;
		overflow: hidden;
	}

	/* ── Pinned Meals ────────────────────────────────── */

	.pinned-section {
		margin-bottom: 16px;
	}

	.pinned-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 4px;
	}

	.pinned-toggle {
		background: none;
		border: none;
		color: var(--text-primary);
		font-size: 15px;
		font-weight: 600;
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 8px 4px;
	}

	.pinned-arrow {
		display: inline-block;
		transition: transform 0.15s;
		font-size: 12px;
	}

	.pinned-arrow.open {
		transform: rotate(90deg);
	}

	.pinned-badge {
		background: #3b82f6;
		color: white;
		font-size: 11px;
		padding: 1px 7px;
		border-radius: 10px;
		font-weight: 600;
	}

	.add-pinned-btn {
		background: none;
		border: 1px solid var(--border-input);
		color: var(--text-secondary);
		padding: 4px 12px;
		border-radius: 6px;
		cursor: pointer;
		font-size: 13px;
	}

	.add-pinned-btn:hover {
		border-color: #3b82f6;
		color: #3b82f6;
	}

	.pinned-empty {
		padding: 12px 16px;
		color: var(--text-muted);
		font-size: 13px;
	}

	.pinned-row {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 8px 16px;
		cursor: pointer;
		border-radius: 6px;
	}

	.pinned-row:hover {
		background: var(--bg-hover);
	}

	.pinned-name {
		font-weight: 500;
		color: var(--text-primary);
		min-width: 120px;
	}

	.pinned-macros {
		flex: 1;
		font-size: 13px;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}

	.pinned-export,
	.pinned-remove {
		background: none;
		border: none;
		color: var(--text-dim);
		cursor: pointer;
		padding: 2px 6px;
		border-radius: 4px;
		font-size: 16px;
	}

	.pinned-export:hover {
		color: #3b82f6;
		background: rgba(59, 130, 246, 0.1);
	}

	.pinned-remove:hover {
		color: #ef4444;
		background: rgba(239, 68, 68, 0.1);
	}
</style>
