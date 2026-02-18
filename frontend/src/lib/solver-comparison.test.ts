/**
 * Comprehensive solver comparison tests.
 *
 * Verifies the client-side LP solver (HiGHS WASM) produces correct results
 * on realistic scenarios using real food data from the Python food database.
 * Test cases mirror those in tests/test_solver.py.
 */

import { describe, it, expect } from 'vitest';
import { solveLocal } from './solver';
import type { Food } from '$lib/api';
import testFoodsRaw from './test-foods.json';

const testFoods = testFoodsRaw as unknown as Record<number, Food>;

function findKey(name: string): number {
	for (const [key, food] of Object.entries(testFoods)) {
		if ((food as Food).name.toLowerCase().includes(name.toLowerCase())) return Number(key);
	}
	throw new Error(`No food matching '${name}'`);
}

function defaultIngredients() {
	return [
		{ key: findKey('White Rice'), min_g: 0, max_g: 400 },
		{ key: findKey('Broccoli'), min_g: 200, max_g: 400 },
		{ key: findKey('Carrots'), min_g: 150, max_g: 300 },
		{ key: findKey('Zucchini'), min_g: 250, max_g: 500 },
		{ key: findKey('Avocado Oil'), min_g: 0, max_g: 100 },
		{ key: findKey('Black Beans'), min_g: 150, max_g: 400 },
		{ key: findKey('Split Peas'), min_g: 60, max_g: 150 },
		{ key: findKey('Ground Beef'), min_g: 0, max_g: 1000 },
		{ key: findKey('Chicken Thigh'), min_g: 0, max_g: 1000 },
	];
}

const defaultTargets = { meal_calories_kcal: 2780, cal_tolerance: 50 };

describe('Solver feasibility', () => {
	it('default ingredients feasible', async () => {
		const result = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: defaultTargets,
		});
		expect(result.status).toBe('optimal');
	});
});

describe('Solver constraints', () => {
	it('calories within tolerance', async () => {
		const result = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: defaultTargets,
		});
		expect(result.status).toBe('optimal');
		expect(result.meal_calories_kcal).toBeGreaterThanOrEqual(2729);
		expect(result.meal_calories_kcal).toBeLessThanOrEqual(2831);
	});

	it('hard protein floor', async () => {
		const result = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: defaultTargets,
			macro_constraints: [
				{ nutrient: 'protein', mode: 'gte', grams: 130, hard: true },
			],
		});
		expect(result.status).toBe('optimal');
		// LP uses continuous variables; allow small tolerance below integer target
		expect(result.meal_protein_g).toBeGreaterThanOrEqual(129);
	});

	it('hard fat eq', async () => {
		const result = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: defaultTargets,
			macro_constraints: [
				{ nutrient: 'fat', mode: 'eq', grams: 80, hard: true },
			],
		});
		expect(result.status).toBe('optimal');
		expect(result.meal_fat_g).toBeGreaterThanOrEqual(78);
		expect(result.meal_fat_g).toBeLessThanOrEqual(82);
	});
});

describe('Micro optimization', () => {
	it('micro optimization produces coverage', async () => {
		const microTargets = {
			calcium_mg: 800,
			iron_mg: 10,
			magnesium_mg: 500,
			vitamin_c_mg: 200,
		};
		const result = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: defaultTargets,
			micro_targets: microTargets,
			optimize_nutrients: Object.keys(microTargets),
		});
		expect(result.status).toBe('optimal');
		// Each nutrient total should be greater than 0 (solver allocated some)
		for (const key of Object.keys(microTargets)) {
			const total = result.micros[key]?.total ?? 0;
			expect(total).toBeGreaterThan(0);
		}
	});
});

describe('UL hard constraint', () => {
	it('UL hard constraint caps nutrient', async () => {
		// First solve without UL to find unconstrained iron
		const free = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: defaultTargets,
			micro_targets: { iron_mg: 10 },
			optimize_nutrients: ['iron_mg'],
		});
		expect(free.status).toBe('optimal');
		const freeIron = free.micros['iron_mg']?.total ?? 0;

		// Set UL so the effective cap (85% of UL) constrains iron below free value.
		// Solver caps at 85% of UL, so effective cap = ironUl * 0.85.
		// We want effective cap < freeIron, so ironUl < freeIron / 0.85.
		// Use 95% of free value as UL → effective cap = 0.95 * 0.85 ≈ 0.81 of free.
		const ironUl = freeIron * 0.95;
		const effectiveCap = ironUl * 0.85;
		const result = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: defaultTargets,
			micro_targets: { iron_mg: 10 },
			micro_uls: { iron_mg: ironUl },
			optimize_nutrients: ['iron_mg'],
		});
		expect(result.status).toBe('optimal');
		const ironTotal = result.micros['iron_mg']?.total ?? 0;
		// Hard UL cap: iron must not exceed 85% of UL + small tolerance
		expect(ironTotal).toBeLessThanOrEqual(effectiveCap + 0.1);
		// Confirm the UL actually constrained the result
		expect(ironTotal).toBeLessThan(freeIron);
	});
});

describe('Macro ratio', () => {
	it('macro ratio steers solution', async () => {
		const highFat = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: defaultTargets,
			macro_ratio: {
				carb_pct: 30,
				protein_pct: 20,
				fat_pct: 50,
				pinned_carb_g: 0,
				pinned_protein_g: 0,
				pinned_fat_g: 0,
			},
			priorities: ['macro_ratio', 'total_weight'],
		});
		const lowFat = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: defaultTargets,
			macro_ratio: {
				carb_pct: 60,
				protein_pct: 25,
				fat_pct: 15,
				pinned_carb_g: 0,
				pinned_protein_g: 0,
				pinned_fat_g: 0,
			},
			priorities: ['macro_ratio', 'total_weight'],
		});
		expect(highFat.status).toBe('optimal');
		expect(lowFat.status).toBe('optimal');
		expect(highFat.meal_fat_g).toBeGreaterThan(lowFat.meal_fat_g);
	});
});

describe('Loose constraints', () => {
	it('loose constraint does not cause infeasibility', async () => {
		const result = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: defaultTargets,
			macro_constraints: [
				{ nutrient: 'protein', mode: 'lte', grams: 1, hard: false },
			],
		});
		expect(result.status).toBe('optimal');
	});

	it('soft protein gives equal or better micro coverage than hard protein', async () => {
		const microTargets = {
			calcium_mg: 800,
			iron_mg: 10,
			magnesium_mg: 500,
			phosphorus_mg: 700,
			potassium_mg: 3400,
			zinc_mg: 11,
			copper_mg: 0.9,
			manganese_mg: 2.3,
			selenium_mcg: 55,
			vitamin_c_mg: 200,
		};
		// Use tighter calorie budget (2000 kcal) to make 160g protein binding
		const tightTargets = { meal_calories_kcal: 2000, cal_tolerance: 50 };
		const sharedInput = {
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: tightTargets,
			micro_targets: microTargets,
			optimize_nutrients: Object.keys(microTargets),
			macro_ratio: {
				carb_pct: 37,
				protein_pct: 33,
				fat_pct: 30,
				pinned_carb_g: 0,
				pinned_protein_g: 0,
				pinned_fat_g: 0,
			},
			micro_strategy: 'breadth' as const,
			// User's priority order: micros → diversity → macro_ratio → weight
			priorities: ['micros', 'ingredient_diversity', 'macro_ratio', 'total_weight'],
			macro_constraints: [
				{ nutrient: 'fiber', mode: 'gte', grams: 40, hard: true },
			],
		};

		const hardResult = await solveLocal({
			...sharedInput,
			macro_constraints: [
				...sharedInput.macro_constraints,
				{ nutrient: 'protein', mode: 'gte', grams: 160, hard: true },
			],
		});
		const softResult = await solveLocal({
			...sharedInput,
			macro_constraints: [
				...sharedInput.macro_constraints,
				{ nutrient: 'protein', mode: 'gte', grams: 160, hard: false },
			],
		});

		expect(hardResult.status).toBe('optimal');
		expect(softResult.status).toBe('optimal');

		// Compute total micro shortfall for both solutions
		// Soft constraint gives solver MORE freedom, so micro_sum (total shortfall)
		// should be equal or better (lower) than hard
		let hardShortfall = 0;
		let softShortfall = 0;
		for (const key of Object.keys(microTargets)) {
			const hardPct = hardResult.micros[key]?.pct ?? 0;
			const softPct = softResult.micros[key]?.pct ?? 0;
			hardShortfall += Math.max(0, 100 - hardPct);
			softShortfall += Math.max(0, 100 - softPct);
		}

		// Soft should have equal or less total shortfall (better coverage)
		// Allow small tolerance for LP solver precision
		expect(softShortfall).toBeLessThanOrEqual(hardShortfall + 5);
	});

	it('micros-first gives equal or better micros than diversity-first (exact user setup)', async () => {
		// Exact user setup from bug report screenshots:
		// Male, 25, 2500 kcal, fiber >= 40g hard, no protein/carb/fat constraints
		// Macro ratio: 37/47/16, breadth strategy, all 20 micros
		// Broccoli min=41, all others min=0 max=1000, Chicken Thigh disabled
		const userIngredients = [
			{ key: findKey('White Rice'), min_g: 0, max_g: 1000 },
			{ key: findKey('Broccoli'), min_g: 41, max_g: 1000 },
			{ key: findKey('Carrots'), min_g: 0, max_g: 1000 },
			{ key: findKey('Zucchini'), min_g: 0, max_g: 1000 },
			{ key: findKey('Avocado Oil'), min_g: 0, max_g: 1000 },
			{ key: findKey('Black Beans'), min_g: 0, max_g: 1000 },
			{ key: findKey('Split Peas'), min_g: 0, max_g: 1000 },
			{ key: findKey('Ground Beef'), min_g: 0, max_g: 1000 },
		];

		// DRI targets for male 19-30 (no pinned meals)
		const microTargets: Record<string, number> = {
			calcium_mg: 1000, iron_mg: 8, magnesium_mg: 400, phosphorus_mg: 700,
			potassium_mg: 3400, zinc_mg: 11, copper_mg: 0.9, manganese_mg: 2.3,
			selenium_mcg: 55, vitamin_c_mg: 90, thiamin_mg: 1.2, riboflavin_mg: 1.3,
			niacin_mg: 16, vitamin_b6_mg: 1.3, folate_mcg: 400, vitamin_b12_mcg: 2.4,
			vitamin_a_mcg: 900, vitamin_d_mcg: 15, vitamin_e_mg: 15, vitamin_k_mcg: 120,
		};
		const microUls: Record<string, number> = {
			calcium_mg: 2500, iron_mg: 45, zinc_mg: 40, manganese_mg: 11,
			selenium_mcg: 400, vitamin_c_mg: 2000, niacin_mg: 35, vitamin_b6_mg: 100,
			folate_mcg: 1000, vitamin_a_mcg: 3000, vitamin_d_mcg: 100, vitamin_e_mg: 1000,
		};

		const sharedInput = {
			ingredients: userIngredients,
			foods: testFoods,
			targets: { meal_calories_kcal: 2500, cal_tolerance: 50 },
			micro_targets: microTargets,
			micro_uls: microUls,
			optimize_nutrients: Object.keys(microTargets),
			macro_ratio: {
				carb_pct: 37, protein_pct: 47, fat_pct: 16,
				pinned_carb_g: 0, pinned_protein_g: 0, pinned_fat_g: 0,
			},
			macro_constraints: [
				{ nutrient: 'fiber', mode: 'gte' as const, grams: 40, hard: true },
			],
			micro_strategy: 'breadth' as const,
			sex: 'male',
			age_group: '19-30',
		};

		const microsFirst = await solveLocal({
			...sharedInput,
			priorities: ['micros', 'ingredient_diversity', 'macro_ratio', 'total_weight'],
		});
		const diversityFirst = await solveLocal({
			...sharedInput,
			priorities: ['ingredient_diversity', 'micros', 'macro_ratio', 'total_weight'],
		});

		expect(microsFirst.status).toBe('optimal');
		expect(diversityFirst.status).toBe('optimal');

		// Compute total shortfall for both (across all 20 micros)
		let microsFirstShortfall = 0;
		let diversityFirstShortfall = 0;
		for (const key of Object.keys(microTargets)) {
			const mfPct = microsFirst.micros[key]?.pct ?? 0;
			const dfPct = diversityFirst.micros[key]?.pct ?? 0;
			microsFirstShortfall += Math.max(0, 100 - mfPct);
			diversityFirstShortfall += Math.max(0, 100 - dfPct);
		}

		console.log('Micros-first shortfall:', microsFirstShortfall.toFixed(1),
			'Diversity-first shortfall:', diversityFirstShortfall.toFixed(1));
		for (const key of Object.keys(microTargets)) {
			const mf = microsFirst.micros[key]?.pct ?? 0;
			const df = diversityFirst.micros[key]?.pct ?? 0;
			if (Math.abs(mf - df) > 2) {
				console.log(`  ${key}: micros-first=${mf.toFixed(1)}% diversity-first=${df.toFixed(1)}%`);
			}
		}

		// Micros-first should have equal or less total shortfall
		expect(microsFirstShortfall).toBeLessThanOrEqual(diversityFirstShortfall + 1);
	});
});

describe('Priority ordering', () => {
	it('priority ordering affects solution', async () => {
		const microTargets = {
			iron_mg: 4.9,
			calcium_mg: 500,
			magnesium_mg: 200,
		};
		const microsFirst = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: defaultTargets,
			micro_targets: microTargets,
			optimize_nutrients: Object.keys(microTargets),
			priorities: ['micros', 'total_weight'],
		});
		const weightFirst = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: defaultTargets,
			micro_targets: microTargets,
			optimize_nutrients: Object.keys(microTargets),
			priorities: ['total_weight', 'micros'],
		});
		expect(microsFirst.status).toBe('optimal');
		expect(weightFirst.status).toBe('optimal');

		const totalMicrosFirst = microsFirst.ingredients.reduce(
			(s, i) => s + i.grams,
			0
		);
		const totalWeightFirst = weightFirst.ingredients.reduce(
			(s, i) => s + i.grams,
			0
		);
		// Weight-first should produce fewer (or equal) total grams
		// Allow tolerance from lex pin slack (REL_TOL compounds across passes)
		expect(totalWeightFirst).toBeLessThanOrEqual(totalMicrosFirst * 1.05 + 1);
	});
});

describe('Ingredient diversity', () => {
	it('ingredient diversity spreads grams', async () => {
		const noDiversity = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: defaultTargets,
			priorities: ['micros', 'macro_ratio', 'total_weight'],
		});
		const withDiversity = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods,
			targets: defaultTargets,
			priorities: [
				'micros',
				'macro_ratio',
				'ingredient_diversity',
				'total_weight',
			],
		});
		expect(noDiversity.status).toBe('optimal');
		expect(withDiversity.status).toBe('optimal');

		const maxNoDiversity = Math.max(
			...noDiversity.ingredients.map((i) => i.grams)
		);
		const maxWithDiversity = Math.max(
			...withDiversity.ingredients.map((i) => i.grams)
		);
		expect(maxWithDiversity).toBeLessThanOrEqual(maxNoDiversity);
	});
});
