export interface Food {
	fdc_id: number;
	name: string;
	subtitle: string;
	usda_description: string;
	cal_per_100g: number;
	protein_per_100g: number;
	fat_per_100g: number;
	carbs_per_100g: number;
	fiber_per_100g: number;
	category: string;
	micros: Record<string, number>;
}

export interface SolveIngredient {
	key: number; // FDC ID
	min_g: number;
	max_g: number;
}

export interface SolveTargets {
	meal_calories: number;
	meal_protein: number;
	meal_fiber_min: number;
	cal_tolerance: number;
	protein_tolerance: number;
}

export interface SolvedIngredient {
	key: number; // FDC ID
	grams: number;
	calories: number;
	protein: number;
	fat: number;
	carbs: number;
	fiber: number;
}

export interface MicroResult {
	total: number;
	smoothie: number;
	dri: number;
	remaining: number;
	pct: number;
	optimized: boolean;
}

export interface SolveResponse {
	status: string;
	ingredients: SolvedIngredient[];
	meal_calories: number;
	meal_protein: number;
	meal_fat: number;
	meal_carbs: number;
	meal_fiber: number;
	micros: Record<string, MicroResult>;
}

export async function fetchFoods(): Promise<Record<number, Food>> {
	const res = await fetch('/api/foods');
	return res.json();
}

export async function solve(
	ingredients: SolveIngredient[],
	targets: SolveTargets,
	objective: string,
	sex: string,
	age_group: string,
	optimize_nutrients: string[],
	micro_strategy: string
): Promise<SolveResponse> {
	const res = await fetch('/api/solve', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ ingredients, targets, objective, sex, age_group, optimize_nutrients, micro_strategy })
	});
	return res.json();
}
