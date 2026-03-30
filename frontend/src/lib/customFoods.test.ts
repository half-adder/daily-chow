import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
	nextCustomId,
	mergeCustomFoods,
	validateImportedFoods,
} from './customFoods';
import type { Food } from '$lib/api';

function makeFood(overrides: Partial<Food> = {}): Food {
	return {
		fdc_id: -1,
		name: 'Test Food',
		subtitle: '',
		usda_description: 'Test Food',
		calories_kcal_per_100g: 100,
		protein_g_per_100g: 10,
		fat_g_per_100g: 5,
		carbs_g_per_100g: 15,
		fiber_g_per_100g: 2,
		category: 'Custom',
		commonness: 5,
		group: 'Test Food',
		micros: {},
		...overrides,
	};
}

describe('nextCustomId', () => {
	it('returns -1 for empty list', () => {
		expect(nextCustomId([])).toBe(-1);
	});

	it('returns one less than the minimum existing id', () => {
		const foods = [makeFood({ fdc_id: -1 }), makeFood({ fdc_id: -3 })];
		expect(nextCustomId(foods)).toBe(-4);
	});
});

describe('mergeCustomFoods', () => {
	it('adds custom foods to USDA foods', () => {
		const usda: Record<number, Food> = { 123: makeFood({ fdc_id: 123, category: 'Grains' }) };
		const custom = [makeFood({ fdc_id: -1, name: 'Custom A' })];
		const merged = mergeCustomFoods(usda, custom);
		expect(Object.keys(merged)).toHaveLength(2);
		expect(merged[123].category).toBe('Grains');
		expect(merged[-1].name).toBe('Custom A');
	});

	it('does not mutate the original USDA record', () => {
		const usda: Record<number, Food> = { 123: makeFood({ fdc_id: 123 }) };
		const custom = [makeFood({ fdc_id: -1 })];
		mergeCustomFoods(usda, custom);
		expect(usda[-1]).toBeUndefined();
	});
});

describe('validateImportedFoods', () => {
	it('accepts a valid array', () => {
		const data = [
			{ name: 'A', calories_kcal_per_100g: 100, protein_g_per_100g: 10, fat_g_per_100g: 5, carbs_g_per_100g: 15, fiber_g_per_100g: 2 },
		];
		const result = validateImportedFoods(data);
		expect(result).toHaveLength(1);
	});

	it('accepts a single object (not wrapped in array)', () => {
		const data = { name: 'A', calories_kcal_per_100g: 100, protein_g_per_100g: 10, fat_g_per_100g: 5, carbs_g_per_100g: 15, fiber_g_per_100g: 2 };
		const result = validateImportedFoods(data);
		expect(result).toHaveLength(1);
		expect(result![0].name).toBe('A');
	});

	it('rejects if name is missing', () => {
		expect(validateImportedFoods([{ calories_kcal_per_100g: 100, protein_g_per_100g: 10, fat_g_per_100g: 5, carbs_g_per_100g: 15, fiber_g_per_100g: 2 }])).toBeNull();
	});

	it('rejects if a macro field is missing', () => {
		expect(validateImportedFoods([{ name: 'A', calories_kcal_per_100g: 100, protein_g_per_100g: 10, fat_g_per_100g: 5, carbs_g_per_100g: 15 }])).toBeNull();
	});

	it('rejects non-object values', () => {
		expect(validateImportedFoods([42])).toBeNull();
		expect(validateImportedFoods('string')).toBeNull();
		expect(validateImportedFoods(null)).toBeNull();
	});
});
