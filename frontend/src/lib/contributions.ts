import type { Food, SolveResponse, MicroResult } from './api';

// 15 distinguishable colors for ingredient identification
export const INGREDIENT_COLORS = [
	'#3b82f6', // blue
	'#ef4444', // red
	'#22c55e', // green
	'#f59e0b', // amber
	'#a855f7', // purple
	'#06b6d4', // cyan
	'#f97316', // orange
	'#ec4899', // pink
	'#14b8a6', // teal
	'#8b5cf6', // violet
	'#84cc16', // lime
	'#e11d48', // rose
	'#0ea5e9', // sky
	'#d946ef', // fuchsia
	'#eab308', // yellow
];

export function assignColor(usedColors: string[]): string {
	const used = new Set(usedColors);
	for (const c of INGREDIENT_COLORS) {
		if (!used.has(c)) return c;
	}
	// All used — cycle from start
	return INGREDIENT_COLORS[usedColors.length % INGREDIENT_COLORS.length];
}

export interface MacroPcts {
	cal: number;
	pro: number;
	fat: number;
	carb: number;
	fiber: number;
}

export interface MicroContrib {
	amount: number;
	driPct: number;
}

export interface IngredientContribution {
	macroPcts: MacroPcts;
	micros: Record<string, MicroContrib>;
}

export function computeContributions(
	solution: SolveResponse,
	foods: Record<number, Food>
): Map<number, IngredientContribution> {
	const result = new Map<number, IngredientContribution>();
	if (solution.status === 'infeasible') return result;

	const totalCal = solution.meal_calories_kcal || 1;
	const totalPro = solution.meal_protein_g || 1;
	const totalFat = solution.meal_fat_g || 1;
	const totalCarb = solution.meal_carbs_g || 1;
	const totalFiber = solution.meal_fiber_g || 1;

	for (const ing of solution.ingredients) {
		const food = foods[ing.key];
		if (!food) continue;

		const macroPcts: MacroPcts = {
			cal: (ing.calories_kcal / totalCal) * 100,
			pro: (ing.protein_g / totalPro) * 100,
			fat: (ing.fat_g / totalFat) * 100,
			carb: (ing.carbs_g / totalCarb) * 100,
			fiber: (ing.fiber_g / totalFiber) * 100,
		};

		const micros: Record<string, MicroContrib> = {};
		for (const [key, per100g] of Object.entries(food.micros)) {
			const amount = (per100g * ing.grams) / 100;
			micros[key] = { amount, driPct: 0 };
		}

		result.set(ing.key, { macroPcts, micros });
	}

	return result;
}

// Fill in driPct values using the micro results from the solve response
export function enrichWithDri(
	contributions: Map<number, IngredientContribution>,
	microResults: Record<string, MicroResult>
): void {
	for (const [, contrib] of contributions) {
		for (const [key, mc] of Object.entries(contrib.micros)) {
			const mr = microResults[key];
			if (mr && mr.dri > 0) {
				mc.driPct = (mc.amount / mr.dri) * 100;
			}
		}
	}
}

// Estimate gap score using a fixed 250g serving assumption
const ESTIMATED_SERVING_G = 250;

export function computeGapScore(
	foodKey: number | string,
	food: Food,
	microResults: Record<string, MicroResult>
): number {
	let score = 0;

	for (const [key, mr] of Object.entries(microResults)) {
		if (mr.pct >= 100) continue; // no gap
		const gap = mr.dri - (mr.total + mr.pinned);
		if (gap <= 0) continue;

		const per100g = food.micros[key];
		if (!per100g) continue;

		const wouldAdd = (per100g * ESTIMATED_SERVING_G) / 100;
		const fillPct = Math.min(wouldAdd / gap, 1.0);
		score += fillPct;
	}

	return score;
}

export function countGapsFilled(
	food: Food,
	microResults: Record<string, MicroResult>
): number {
	let count = 0;

	for (const [key, mr] of Object.entries(microResults)) {
		if (mr.pct >= 100) continue;
		const gap = mr.dri - (mr.total + mr.pinned);
		if (gap <= 0) continue;

		const per100g = food.micros[key];
		if (!per100g) continue;

		const wouldAdd = (per100g * ESTIMATED_SERVING_G) / 100;
		if (wouldAdd / gap > 0.1) count++;
	}

	return count;
}
