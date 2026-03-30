import type { Food } from './api';

const STORAGE_KEY = 'custom-foods';

export function loadCustomFoods(): Food[] {
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (!raw) return [];
		return JSON.parse(raw) as Food[];
	} catch {
		return [];
	}
}

export function saveCustomFoods(foods: Food[]): void {
	localStorage.setItem(STORAGE_KEY, JSON.stringify(foods));
}

export function nextCustomId(existing: Food[]): number {
	if (existing.length === 0) return -1;
	return Math.min(...existing.map((f) => f.fdc_id)) - 1;
}

export function mergeCustomFoods(
	usdaFoods: Record<number, Food>,
	customFoods: Food[]
): Record<number, Food> {
	const merged = { ...usdaFoods };
	for (const f of customFoods) {
		merged[f.fdc_id] = f;
	}
	return merged;
}

export function exportCustomFoods(foods: Food[]): void {
	const blob = new Blob([JSON.stringify(foods, null, 2)], { type: 'application/json' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = 'custom-ingredients.json';
	a.click();
	URL.revokeObjectURL(url);
}

export function validateImportedFoods(data: unknown): Food[] | null {
	if (!Array.isArray(data)) return null;
	for (const item of data) {
		if (
			typeof item !== 'object' ||
			item === null ||
			typeof item.name !== 'string' ||
			typeof item.calories_kcal_per_100g !== 'number' ||
			typeof item.protein_g_per_100g !== 'number' ||
			typeof item.fat_g_per_100g !== 'number' ||
			typeof item.carbs_g_per_100g !== 'number' ||
			typeof item.fiber_g_per_100g !== 'number'
		) {
			return null;
		}
	}
	return data as Food[];
}
