export interface Food {
	name: string;
	unit_note: string;
	cal_per_100g: number;
	protein_per_100g: number;
	fat_per_100g: number;
	carbs_per_100g: number;
	fiber_per_100g: number;
	category: string;
	default_min: number;
	default_max: number;
}

export interface SolveIngredient {
	key: string;
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
	key: string;
	grams: number;
	calories: number;
	protein: number;
	fat: number;
	carbs: number;
	fiber: number;
}

export interface SolveResponse {
	status: string;
	ingredients: SolvedIngredient[];
	meal_calories: number;
	meal_protein: number;
	meal_fat: number;
	meal_carbs: number;
	meal_fiber: number;
}

export async function fetchFoods(): Promise<Record<string, Food>> {
	const res = await fetch('/api/foods');
	return res.json();
}

export async function solve(
	ingredients: SolveIngredient[],
	targets: SolveTargets,
	objective: string
): Promise<SolveResponse> {
	const res = await fetch('/api/solve', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ ingredients, targets, objective })
	});
	return res.json();
}
