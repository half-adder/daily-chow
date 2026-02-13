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
	micros: Record<string, number>;
}

export interface SolveIngredient {
	key: number; // FDC ID
	min_g: number;
	max_g: number;
}

export interface SolveTargets {
	meal_calories_kcal: number;
	meal_protein_min_g: number;
	meal_fiber_min_g: number;
	cal_tolerance: number;
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

export async function solve(
	ingredients: SolveIngredient[],
	targets: SolveTargets,
	sex: string,
	age_group: string,
	optimize_nutrients: string[],
	priorities: string[],
	pinned_micros: Record<string, number> = {}
): Promise<SolveResponse> {
	const res = await fetch('/api/solve', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ ingredients, targets, sex, age_group, optimize_nutrients, priorities, pinned_micros })
	});
	return res.json();
}
