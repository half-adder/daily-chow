import { DRI_TARGETS, DRI_UL } from '$lib/dri';
import type { LpModelInput } from './solver';

export interface Food {
	fdc_id: number;
	name: string;
	subtitle: string;
	usda_description: string;
	calories_kcal_per_100g: number;
	protein_g_per_100g: number;
	fat_g_per_100g: number;
	carbs_g_per_100g: number;
	fiber_g_per_100g: number;
	category: string;
	commonness: number;
	micros: Record<string, number>;
}

export interface SolveIngredient {
	key: number; // FDC ID
	min_g: number;
	max_g: number;
}

export interface SolveTargets {
	meal_calories_kcal: number;
	cal_tolerance: number;
}

export interface MacroRatio {
	carb_pct: number;
	protein_pct: number;
	fat_pct: number;
	pinned_carb_g: number;
	pinned_protein_g: number;
	pinned_fat_g: number;
}

export interface MacroConstraint {
	nutrient: 'carbs' | 'protein' | 'fat' | 'fiber';
	mode: 'gte' | 'lte' | 'eq' | 'none';
	grams: number;
	hard: boolean;
}

export interface SolvedIngredient {
	key: number; // FDC ID
	grams: number;
	calories_kcal: number;
	protein_g: number;
	fat_g: number;
	carbs_g: number;
	fiber_g: number;
}

export interface PinnedMeal {
	id: string;
	name: string;
	nutrients: Record<string, number>;
}

export interface MicroResult {
	total: number;
	pinned: number;
	dri: number;
	remaining: number;
	pct: number;
	optimized: boolean;
	ear: number | null;
	ul: number | null;
}

export interface SolveResponse {
	status: string;
	ingredients: SolvedIngredient[];
	meal_calories_kcal: number;
	meal_protein_g: number;
	meal_fat_g: number;
	meal_carbs_g: number;
	meal_fiber_g: number;
	micros: Record<string, MicroResult>;
}

// USDA nutrient ID → macro field extraction (prefer Atwater General for calories)
const MACRO_USDA_IDS: Record<string, number[]> = {
	calories_kcal: [2047, 1008],
	protein_g: [1003],
	fat_g: [1004],
	carbs_g: [1005],
	fiber_g: [1079],
};

// USDA nutrient ID → canonical micro key
const USDA_ID_TO_MICRO: Record<number, string> = {
	1087: 'calcium_mg',
	1089: 'iron_mg',
	1090: 'magnesium_mg',
	1091: 'phosphorus_mg',
	1092: 'potassium_mg',
	1095: 'zinc_mg',
	1098: 'copper_mg',
	1101: 'manganese_mg',
	1103: 'selenium_mcg',
	1162: 'vitamin_c_mg',
	1165: 'thiamin_mg',
	1166: 'riboflavin_mg',
	1167: 'niacin_mg',
	1175: 'vitamin_b6_mg',
	1177: 'folate_mcg',
	1178: 'vitamin_b12_mcg',
	1106: 'vitamin_a_mcg',
	1114: 'vitamin_d_mcg',
	1109: 'vitamin_e_mg',
	1185: 'vitamin_k_mcg',
};

function extractMacro(nutrients: Record<string, number>, usdaIds: number[]): number {
	for (const id of usdaIds) {
		const val = nutrients[String(id)];
		if (val !== undefined) return val;
	}
	return 0;
}

function transformFood(entry: RawFood): Food {
	const n = entry.nutrients;
	const micros: Record<string, number> = {};
	for (const [uid, amount] of Object.entries(n)) {
		const key = USDA_ID_TO_MICRO[Number(uid)];
		if (key) micros[key] = amount;
	}
	return {
		fdc_id: entry.fdc_id,
		name: entry.name,
		subtitle: entry.subtitle ?? '',
		usda_description: entry.usda_description ?? entry.name,
		category: entry.category ?? '',
		commonness: entry.commonness ?? 3,
		calories_kcal_per_100g: extractMacro(n, MACRO_USDA_IDS.calories_kcal),
		protein_g_per_100g: extractMacro(n, MACRO_USDA_IDS.protein_g),
		fat_g_per_100g: extractMacro(n, MACRO_USDA_IDS.fat_g),
		carbs_g_per_100g: extractMacro(n, MACRO_USDA_IDS.carbs_g),
		fiber_g_per_100g: extractMacro(n, MACRO_USDA_IDS.fiber_g),
		micros,
	};
}

interface RawFood {
	fdc_id: number;
	name: string;
	subtitle?: string;
	usda_description?: string;
	category?: string;
	commonness?: number;
	nutrients: Record<string, number>;
}

export async function fetchFoods(): Promise<Record<number, Food>> {
	const res = await fetch('/foods.json');
	const raw: RawFood[] = await res.json();
	const foods: Record<number, Food> = {};
	for (const entry of raw) {
		foods[entry.fdc_id] = transformFood(entry);
	}
	return foods;
}

// ── Web Worker solver ────────────────────────────────────────────────

let worker: Worker | null = null;
let foodsSent = false;
let messageId = 0;
let latestRequestId = 0;
const pending = new Map<number, {
	resolve: (r: SolveResponse) => void;
	reject: (e: Error) => void;
}>();

function getWorker(): Worker {
	if (!worker) {
		worker = new Worker(
			new URL('./solver.worker.ts', import.meta.url),
			{ type: 'module' }
		);
		worker.onmessage = (e) => {
			const { id, result, error } = e.data;
			const p = pending.get(id);
			if (p) {
				pending.delete(id);
				if (error) p.reject(new Error(error));
				else p.resolve(result);
			}
		};
	}
	return worker;
}

/** Send foods catalog to the worker once. Call after fetchFoods(). */
export function initWorkerFoods(foods: Record<number, Food>) {
	const w = getWorker();
	// foods from fetchFoods() is plain JSON (no Svelte proxy), safe to post directly
	w.postMessage({ type: 'init', foods });
	foodsSent = true;
}

export async function solve(
	ingredients: SolveIngredient[],
	targets: SolveTargets,
	sex: string,
	age_group: string,
	optimize_nutrients: string[],
	priorities: string[],
	pinned_micros: Record<string, number> = {},
	macro_ratio: MacroRatio | null = null,
	macro_constraints: MacroConstraint[] = [],
	micro_strategy: 'depth' | 'breadth' = 'depth',
): Promise<SolveResponse> {
	if (!foodsSent) {
		throw new Error('initWorkerFoods() must be called before solve()');
	}

	// Compute micro_targets from DRI data
	const dri = DRI_TARGETS[sex]?.[age_group] ?? {};
	const micro_targets: Record<string, number> = {};
	for (const k of optimize_nutrients) {
		const driVal = dri[k] ?? 0;
		const pinnedVal = pinned_micros[k] ?? 0;
		const remaining = Math.max(0, driVal - pinnedVal);
		if (remaining > 0 && driVal > 0) {
			micro_targets[k] = remaining;
		}
	}

	// Compute micro_uls from UL data
	const ulTable = DRI_UL[sex]?.[age_group] ?? {};
	const micro_uls: Record<string, number> = {};
	for (const [k, ulVal] of Object.entries(ulTable)) {
		const pinnedVal = pinned_micros[k] ?? 0;
		const remainingUl = ulVal - pinnedVal;
		if (remainingUl > 0) {
			micro_uls[k] = remainingUl;
		}
	}

	const input: Omit<LpModelInput, 'foods'> = {
		ingredients,
		targets,
		micro_targets: Object.keys(micro_targets).length > 0 ? micro_targets : undefined,
		micro_uls: Object.keys(micro_uls).length > 0 ? micro_uls : undefined,
		macro_ratio: macro_ratio ?? undefined,
		macro_constraints,
		priorities,
		micro_strategy,
		sex,
		age_group,
		optimize_nutrients,
		pinned_micros,
	};

	const w = getWorker();
	const id = ++messageId;
	latestRequestId = id;
	return new Promise((resolve, reject) => {
		pending.set(id, {
			resolve: (r) => {
				if (id !== latestRequestId) {
					reject(new Error('superseded'));
				} else {
					resolve(r);
				}
			},
			reject,
		});
		// JSON round-trip strips Svelte 5 $state proxies (e.g. priorities, macro_constraints)
		w.postMessage({ type: 'solve', id, input: JSON.parse(JSON.stringify(input)) });
	});
}
