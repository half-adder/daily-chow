import { describe, it, expect } from 'vitest';
import { buildLpModel, solveLocal } from './solver';
import type { Food } from '$lib/api';

const rice: Food = {
	fdc_id: 169756,
	name: 'White Rice',
	subtitle: 'cooked',
	usda_description: '',
	calories_kcal_per_100g: 130,
	protein_g_per_100g: 2.38,
	fat_g_per_100g: 0.21,
	carbs_g_per_100g: 28.59,
	fiber_g_per_100g: 0.0,
	category: 'Grains',
	commonness: 5,
	micros: { iron_mg: 0.2, calcium_mg: 3 },
};

const broccoli: Food = {
	fdc_id: 170379,
	name: 'Broccoli',
	subtitle: 'raw',
	usda_description: '',
	calories_kcal_per_100g: 34,
	protein_g_per_100g: 2.82,
	fat_g_per_100g: 0.37,
	carbs_g_per_100g: 6.64,
	fiber_g_per_100g: 2.6,
	category: 'Vegetables',
	commonness: 5,
	micros: { iron_mg: 0.73, calcium_mg: 47, vitamin_c_mg: 89.2 },
};

describe('buildLpModel', () => {
	it('generates valid LP with calorie band', () => {
		const lp = buildLpModel({
			ingredients: [{ key: 169756, min_g: 0, max_g: 400 }],
			foods: { 169756: rice },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
		});
		expect(lp).toContain('Minimize');
		expect(lp).toContain('Subject To');
		expect(lp).toContain('Bounds');
		expect(lp).toContain('End');
		expect(lp).toMatch(/cal_lo:/);
		expect(lp).toMatch(/cal_hi:/);
	});

	it('includes hard macro constraints', () => {
		const lp = buildLpModel({
			ingredients: [
				{ key: 169756, min_g: 0, max_g: 400 },
				{ key: 170379, min_g: 100, max_g: 300 },
			],
			foods: { 169756: rice, 170379: broccoli },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
			macro_constraints: [{ nutrient: 'protein', mode: 'gte', grams: 30, hard: true }],
		});
		expect(lp).toMatch(/protein_gte:/);
	});

	it('includes micro shortfall variables', () => {
		const lp = buildLpModel({
			ingredients: [
				{ key: 169756, min_g: 0, max_g: 400 },
				{ key: 170379, min_g: 100, max_g: 300 },
			],
			foods: { 169756: rice, 170379: broccoli },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
			micro_targets: { iron_mg: 8.0 },
		});
		expect(lp).toMatch(/iron_mg_short/);
		expect(lp).toMatch(/iron_mg_pct/);
		expect(lp).toMatch(/worst_pct/);
	});

	it('includes ingredient bounds', () => {
		const lp = buildLpModel({
			ingredients: [{ key: 169756, min_g: 50, max_g: 400 }],
			foods: { 169756: rice },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
		});
		expect(lp).toMatch(/50 <= g_169756 <= 400/);
	});

	it('includes soft macro constraints with deviation vars', () => {
		const lp = buildLpModel({
			ingredients: [
				{ key: 169756, min_g: 0, max_g: 400 },
				{ key: 170379, min_g: 0, max_g: 300 },
			],
			foods: { 169756: rice, 170379: broccoli },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
			macro_constraints: [{ nutrient: 'protein', mode: 'gte', grams: 30, hard: false }],
		});
		expect(lp).toMatch(/loose_protein_gte_dev/);
		expect(lp).toMatch(/loose_protein_gte_pct/);
		expect(lp).toMatch(/worst_loose/);
	});

	it('includes UL hard constraints', () => {
		const lp = buildLpModel({
			ingredients: [
				{ key: 169756, min_g: 0, max_g: 400 },
				{ key: 170379, min_g: 0, max_g: 300 },
			],
			foods: { 169756: rice, 170379: broccoli },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
			micro_uls: { iron_mg: 45 },
		});
		expect(lp).toMatch(/ul_iron_mg:/);
	});

	it('includes UL proximity penalty when both targets and ULs exist', () => {
		const lp = buildLpModel({
			ingredients: [
				{ key: 169756, min_g: 0, max_g: 400 },
				{ key: 170379, min_g: 0, max_g: 300 },
			],
			foods: { 169756: rice, 170379: broccoli },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
			micro_targets: { iron_mg: 8.0 },
			micro_uls: { iron_mg: 45 },
		});
		expect(lp).toMatch(/iron_mg_ul_excess/);
		expect(lp).toMatch(/iron_mg_ul_prox/);
		expect(lp).toMatch(/worst_ul_prox/);
	});

	it('includes macro ratio minimax', () => {
		const lp = buildLpModel({
			ingredients: [
				{ key: 169756, min_g: 0, max_g: 400 },
				{ key: 170379, min_g: 0, max_g: 300 },
			],
			foods: { 169756: rice, 170379: broccoli },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
			macro_ratio: {
				carb_pct: 50,
				protein_pct: 25,
				fat_pct: 25,
				pinned_carb_g: 0,
				pinned_protein_g: 0,
				pinned_fat_g: 0,
			},
		});
		expect(lp).toMatch(/macro_carb_pctdev/);
		expect(lp).toMatch(/macro_pro_pctdev/);
		expect(lp).toMatch(/macro_fat_pctdev/);
		expect(lp).toMatch(/macro_worst/);
	});

	it('excludes constrained macros from ratio optimization', () => {
		const lp = buildLpModel({
			ingredients: [
				{ key: 169756, min_g: 0, max_g: 400 },
				{ key: 170379, min_g: 0, max_g: 300 },
			],
			foods: { 169756: rice, 170379: broccoli },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
			macro_ratio: {
				carb_pct: 50,
				protein_pct: 25,
				fat_pct: 25,
				pinned_carb_g: 0,
				pinned_protein_g: 0,
				pinned_fat_g: 0,
			},
			macro_constraints: [{ nutrient: 'protein', mode: 'gte', grams: 30, hard: true }],
		});
		// protein should be excluded from ratio
		expect(lp).not.toMatch(/macro_pro_pctdev/);
		// carb and fat should still be present
		expect(lp).toMatch(/macro_carb_pctdev/);
		expect(lp).toMatch(/macro_fat_pctdev/);
	});

	it('includes ingredient diversity var', () => {
		const lp = buildLpModel({
			ingredients: [
				{ key: 169756, min_g: 0, max_g: 400 },
				{ key: 170379, min_g: 0, max_g: 300 },
			],
			foods: { 169756: rice, 170379: broccoli },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
			priorities: ['ingredient_diversity', 'total_weight'],
		});
		expect(lp).toMatch(/max_gram/);
		expect(lp).toMatch(/max_gram_g_169756/);
		expect(lp).toMatch(/max_gram_g_170379/);
	});

	it('uses breadth strategy ordering', () => {
		const lp = buildLpModel({
			ingredients: [
				{ key: 169756, min_g: 0, max_g: 400 },
				{ key: 170379, min_g: 0, max_g: 300 },
			],
			foods: { 169756: rice, 170379: broccoli },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
			micro_targets: { iron_mg: 8.0 },
			micro_strategy: 'breadth',
		});
		// Both micro_sum and worst_pct should appear in objective
		expect(lp).toMatch(/micro_sum/);
		expect(lp).toMatch(/worst_pct/);
	});

	it('calorie coefficients are correct', () => {
		const lp = buildLpModel({
			ingredients: [{ key: 169756, min_g: 0, max_g: 400 }],
			foods: { 169756: rice },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
		});
		// rice: 130 kcal/100g = 1.3 kcal/g
		expect(lp).toMatch(/cal_lo: 1\.3 g_169756 >= 450/);
		expect(lp).toMatch(/cal_hi: 1\.3 g_169756 <= 550/);
	});
});

describe('solveLocal', () => {
	it('solves a simple 2-ingredient problem', async () => {
		const result = await solveLocal({
			ingredients: [
				{ key: 169756, min_g: 0, max_g: 400 },
				{ key: 170379, min_g: 100, max_g: 300 },
			],
			foods: { 169756: rice, 170379: broccoli },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
		});
		expect(result.status).toBe('optimal');
		expect(result.ingredients).toHaveLength(2);
		// Allow small floating-point tolerance from LP solver
		expect(result.meal_calories_kcal).toBeGreaterThanOrEqual(449);
		expect(result.meal_calories_kcal).toBeLessThanOrEqual(551);
	});

	it('returns infeasible for impossible constraints', async () => {
		const result = await solveLocal({
			ingredients: [{ key: 169756, min_g: 0, max_g: 10 }],
			foods: { 169756: rice },
			targets: { meal_calories_kcal: 500, cal_tolerance: 10 },
		});
		expect(result.status).toBe('infeasible');
	});

	it('returns infeasible for empty ingredients', async () => {
		const result = await solveLocal({
			ingredients: [],
			foods: {},
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
		});
		expect(result.status).toBe('infeasible');
	});

	it('computes micro results with DRI/UL/EAR', async () => {
		const result = await solveLocal({
			ingredients: [
				{ key: 169756, min_g: 100, max_g: 400 },
				{ key: 170379, min_g: 100, max_g: 300 },
			],
			foods: { 169756: rice, 170379: broccoli },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
			sex: 'male',
			age_group: '19-30',
			optimize_nutrients: ['iron_mg', 'calcium_mg'],
			pinned_micros: { iron_mg: 2.0 },
		});
		expect(result.status).toBe('optimal');

		// Should have micro results for all 20 nutrients
		expect(Object.keys(result.micros).length).toBe(20);

		// Iron should include pinned amount
		const iron = result.micros.iron_mg;
		expect(iron).toBeDefined();
		expect(iron.pinned).toBe(2.0);
		expect(iron.dri).toBe(8);
		expect(iron.optimized).toBe(true);
		expect(iron.total).toBeGreaterThan(0);
		expect(iron.pct).toBeGreaterThan(0);

		// Calcium should not be pinned
		const calcium = result.micros.calcium_mg;
		expect(calcium.pinned).toBe(0);
		expect(calcium.optimized).toBe(true);

		// Non-optimized nutrients should have optimized=false
		expect(result.micros.vitamin_k_mcg.optimized).toBe(false);
	});

	it('returns micros with defaults when sex/age_group not provided', async () => {
		const result = await solveLocal({
			ingredients: [{ key: 169756, min_g: 100, max_g: 400 }],
			foods: { 169756: rice },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
		});
		// Should still return micros (using defaults male/19-30)
		expect(Object.keys(result.micros).length).toBe(20);
	});

	it('respects hard protein floor', async () => {
		const result = await solveLocal({
			ingredients: [
				{ key: 169756, min_g: 0, max_g: 400 },
				{ key: 170379, min_g: 100, max_g: 500 },
			],
			foods: { 169756: rice, 170379: broccoli },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
			macro_constraints: [
				{ nutrient: 'protein', mode: 'gte', grams: 10, hard: true },
			],
		});
		expect(result.status).toBe('optimal');
		expect(result.meal_protein_g).toBeGreaterThanOrEqual(9.5);
	});
});
