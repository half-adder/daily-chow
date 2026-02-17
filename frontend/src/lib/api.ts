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

export async function fetchFoods(): Promise<Record<number, Food>> {
	const res = await fetch('/api/foods');
	return res.json();
}

// ── Web Worker solver ────────────────────────────────────────────────

let worker: Worker | null = null;
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
	foods: Record<number, Food> = {},
): Promise<SolveResponse> {
	// Compute micro_targets from DRI data (port of api.py lines 228-236)
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

	// Compute micro_uls from UL data (port of api.py lines 239-247)
	const ulTable = DRI_UL[sex]?.[age_group] ?? {};
	const micro_uls: Record<string, number> = {};
	for (const [k, ulVal] of Object.entries(ulTable)) {
		const pinnedVal = pinned_micros[k] ?? 0;
		const remainingUl = ulVal - pinnedVal;
		if (remainingUl > 0) {
			micro_uls[k] = remainingUl;
		}
	}

	const input: LpModelInput = {
		ingredients,
		foods,
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
		w.postMessage({ id, input });
	});
}
