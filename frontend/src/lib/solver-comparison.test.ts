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
		expect(result.meal_calories_kcal).toBeGreaterThanOrEqual(2730);
		expect(result.meal_calories_kcal).toBeLessThanOrEqual(2830);
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

		// Set UL to 85% of unconstrained — tight enough to constrain,
		// but loose enough to be feasible given ingredient minimums
		const ironUl = freeIron * 0.85;
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
		// Hard UL cap: iron must not exceed UL + small tolerance
		expect(ironTotal).toBeLessThanOrEqual(ironUl + 0.1);
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
		expect(totalWeightFirst).toBeLessThanOrEqual(totalMicrosFirst + 0.1);
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
