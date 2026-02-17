# Client-Side LP Solver Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the nutrition solver from the Python backend to the browser using HiGHS WASM, eliminating server load and enabling real-time slider feedback.

**Architecture:** A TypeScript LP model builder generates CPLEX `.lp` format strings from ingredient/constraint data, passes them to the HiGHS WASM solver running in a Web Worker, and returns results in the existing `SolveResponse` shape. The DRI/UL/EAR reference data is ported to a static TypeScript module.

**Tech Stack:** HiGHS WASM (`highs` npm package), Vite Web Workers, Vitest for testing, TypeScript.

---

### Task 1: Add vitest and highs dependencies

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`

**Step 1: Install dependencies**

Run: `cd /Users/sean/code/daily-chow/frontend && bun add highs && bun add -d vitest`

**Step 2: Create vitest config**

Create `frontend/vitest.config.ts`:
```ts
import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
	test: {
		include: ['src/**/*.test.ts'],
	},
	resolve: {
		alias: {
			$lib: path.resolve('./src/lib'),
		},
	},
});
```

**Step 3: Add test script to package.json**

Add `"test": "vitest run"` and `"test:watch": "vitest"` to the `scripts` section.

**Step 4: Verify vitest runs**

Run: `cd /Users/sean/code/daily-chow/frontend && bun run test`
Expected: 0 tests found, clean exit.

**Step 5: Commit**

```bash
git add frontend/package.json frontend/bun.lock frontend/vitest.config.ts
git commit -m "chore: add vitest and highs dependencies"
```

---

### Task 2: Port DRI reference data to TypeScript

The Python `dri.py` contains DRI targets, EAR, and UL lookup tables keyed by (sex, age_group). The server endpoint uses these to compute `micro_targets`, `micro_uls`, and `MicroResult` objects. The client-side solver needs this same data.

**Files:**
- Create: `frontend/src/lib/dri.ts`
- Test: `frontend/src/lib/dri.test.ts`

**Step 1: Write the test**

Create `frontend/src/lib/dri.test.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { DRI_TARGETS, DRI_UL, DRI_EAR, MICRO_KEYS } from './dri';

describe('DRI data', () => {
	it('has targets for male 19-30', () => {
		const t = DRI_TARGETS['male']['19-30'];
		expect(t.calcium_mg).toBe(1000);
		expect(t.iron_mg).toBe(8);
		expect(t.vitamin_k_mcg).toBe(120);
	});

	it('has targets for female 19-30', () => {
		const t = DRI_TARGETS['female']['19-30'];
		expect(t.iron_mg).toBe(18);
		expect(t.potassium_mg).toBe(2600);
	});

	it('has UL for male 19-30', () => {
		const ul = DRI_UL['male']['19-30'];
		expect(ul.calcium_mg).toBe(2500);
		expect(ul.iron_mg).toBe(45);
	});

	it('has EAR for male 19-30', () => {
		const ear = DRI_EAR['male']['19-30'];
		expect(ear.calcium_mg).toBe(800);
	});

	it('MICRO_KEYS has 20 entries', () => {
		expect(MICRO_KEYS).toHaveLength(20);
		expect(MICRO_KEYS).toContain('calcium_mg');
		expect(MICRO_KEYS).toContain('vitamin_k_mcg');
	});
});
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/sean/code/daily-chow/frontend && bun run test -- src/lib/dri.test.ts`
Expected: FAIL — module not found.

**Step 3: Write the implementation**

Create `frontend/src/lib/dri.ts` — port all data from `src/daily_chow/dri.py`.

The structure should be:
```ts
// Type for nutrient values keyed by nutrient string
export type NutrientTable = Record<string, number>;

// Nested lookup: DRI_TARGETS[sex][ageGroup] -> NutrientTable
export const DRI_TARGETS: Record<string, Record<string, NutrientTable>> = {
	male: {
		'19-30': {
			calcium_mg: 1000, iron_mg: 8, magnesium_mg: 400,
			// ... all 20 nutrients from _MALE_19_30 in dri.py
		},
		'31-50': { /* ... spread from 19-30, override magnesium_mg: 420 */ },
		'51-70': { /* ... */ },
		'71+': { /* ... */ },
	},
	female: {
		'19-30': { /* ... from _FEMALE_19_30 */ },
		// ...
	},
};

export const DRI_UL: Record<string, Record<string, NutrientTable>> = {
	// Same structure, data from _UL_19_70
};

export const DRI_EAR: Record<string, Record<string, NutrientTable>> = {
	// Same structure, data from _EAR_MALE_19_30 and _EAR_FEMALE_19_30
};

export const MICRO_KEYS: string[] = [
	'calcium_mg', 'iron_mg', /* ... all 20 keys */
];
```

Copy values exactly from `src/daily_chow/dri.py`. Don't miss the per-age-group overrides (e.g., male 31-50 has magnesium_mg: 420).

**Step 4: Run test to verify it passes**

Run: `cd /Users/sean/code/daily-chow/frontend && bun run test -- src/lib/dri.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/lib/dri.ts frontend/src/lib/dri.test.ts
git commit -m "feat: port DRI reference data to TypeScript"
```

---

### Task 3: Build LP model string generator

This is the core translation layer. It takes the same inputs as the Python solver and produces a CPLEX `.lp` format string that HiGHS can solve.

**Reference:** Read `src/daily_chow/solver.py` lines 104-536 carefully. Every constraint and objective term must be translated.

**CPLEX LP format reference:** The format looks like:
```
Minimize
 obj: 1000 worst_pct + 100 micro_sum + gram_0 + gram_1
Subject To
 cal_lo: 28 gram_0 + 15 gram_1 >= 273000
 cal_hi: 28 gram_0 + 15 gram_1 <= 283000
 iron_short: iron_shortfall + 0.036 gram_0 >= 4.9
Bounds
 0 <= gram_0 <= 400
 200 <= gram_1 <= 400
End
```

Variables must be named with letters/underscores (no hyphens). Use `g_<key>` for gram variables.

**Files:**
- Create: `frontend/src/lib/solver.ts`
- Test: `frontend/src/lib/solver.test.ts`

**Step 1: Write tests for LP string generation**

Create `frontend/src/lib/solver.test.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { buildLpModel } from './solver';
import type { Food } from './api';

// Minimal test food
const rice: Food = {
	fdc_id: 169756,
	name: 'White Rice',
	subtitle: 'cooked',
	usda_description: 'Rice, white, medium-grain, cooked',
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
	usda_description: 'Broccoli, raw',
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
	it('generates valid LP with calorie band constraint', () => {
		const lp = buildLpModel({
			ingredients: [{ key: 169756, min_g: 0, max_g: 400 }],
			foods: { 169756: rice },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
		});
		expect(lp).toContain('Minimize');
		expect(lp).toContain('Subject To');
		expect(lp).toContain('Bounds');
		expect(lp).toContain('End');
		// Calorie band: 1.3 * g >= 450, 1.3 * g <= 550
		expect(lp).toMatch(/cal_lo:/);
		expect(lp).toMatch(/cal_hi:/);
	});

	it('includes macro hard constraints', () => {
		const lp = buildLpModel({
			ingredients: [
				{ key: 169756, min_g: 0, max_g: 400 },
				{ key: 170379, min_g: 100, max_g: 300 },
			],
			foods: { 169756: rice, 170379: broccoli },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
			macro_constraints: [
				{ nutrient: 'protein', mode: 'gte', grams: 30, hard: true },
			],
		});
		expect(lp).toMatch(/protein_gte:/);
	});

	it('includes micro shortfall variables when micro_targets provided', () => {
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
			ingredients: [
				{ key: 169756, min_g: 50, max_g: 400 },
			],
			foods: { 169756: rice },
			targets: { meal_calories_kcal: 500, cal_tolerance: 50 },
		});
		expect(lp).toMatch(/50 <= g_169756 <= 400/);
	});
});
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/sean/code/daily-chow/frontend && bun run test -- src/lib/solver.test.ts`
Expected: FAIL — module not found.

**Step 3: Write the implementation**

Create `frontend/src/lib/solver.ts`. This is the largest piece of work. The function signature:

```ts
import type { Food, SolveIngredient, SolveTargets, MacroRatio, MacroConstraint } from './api';

export interface LpModelInput {
	ingredients: SolveIngredient[];
	foods: Record<number, Food>;
	targets: SolveTargets;
	micro_targets?: Record<string, number>;
	micro_uls?: Record<string, number>;
	macro_ratio?: MacroRatio | null;
	macro_constraints?: MacroConstraint[];
	priorities?: string[];
	micro_strategy?: 'depth' | 'breadth';
}

export function buildLpModel(input: LpModelInput): string {
	// ... generate CPLEX LP format string
}
```

**Translation rules from CP-SAT to LP:**

1. **Variables:** `g_<key>` for each ingredient (continuous, bounded by min_g/max_g). No SCALE needed — work in natural units.

2. **Calorie band:** Two constraints:
   - `cal_lo: sum(cal_per_g * g_<key>) >= target - tolerance`
   - `cal_hi: sum(cal_per_g * g_<key>) <= target + tolerance`
   Where `cal_per_g = calories_kcal_per_100g / 100`.

3. **Hard macro constraints:** Direct translation of gte/lte/eq to LP constraints using `protein_g_per_100g / 100`, etc.

4. **Soft macro constraints:** Create deviation variable. For `gte`: `dev >= target - actual` and `dev >= 0`. For `lte`: `dev >= actual - target` and `dev >= 0`. For `eq`: split into `x_pos - x_neg = actual - target`, `x_pos, x_neg >= 0`, deviation = `x_pos + x_neg`.

5. **UL hard constraints:** `sum(micro_per_g * g_<key>) <= ul_val` for each nutrient with a UL.

6. **Micro shortfall minimax:** For each micro target:
   - `shortfall_<key> >= target - sum(per_g * g_<key>)` and `shortfall >= 0`
   - `pct_short_<key> >= shortfall_<key> / target` (multiply through: `pct_short * target >= shortfall`)
   - `worst_pct >= pct_short_<key>` for all keys

7. **UL proximity:** For each nutrient with both DRI and UL:
   - `excess_<key> >= sum(per_g * g) - target` and `excess >= 0`
   - `ul_prox_<key> >= excess / headroom` where headroom = UL - target
   - `worst_ul_prox >= ul_prox_<key>` for all keys

8. **Macro ratio minimax:** For each macro (carb/pro/fat) not excluded by constraints:
   - `diff_<macro> = actual_cal - total_cal * target_pct / 100`
   - Split absolute value: `diff = pos - neg`, `abs = pos + neg`, `pos, neg >= 0`
   - `pct_dev >= abs / (cal_denom * 100) * PCT_SCALE`
   - `macro_worst >= pct_dev` for all macros

9. **Combined macro var:** `combined_macro >= macro_worst` and `combined_macro >= worst_loose` (minimax over both).

10. **Ingredient diversity:** `max_gram >= g_<key>` for all keys.

11. **Lexicographic objective:** Same weighted-sum approach as Python. Build terms list in priority order, compute weights where `w[i] = max[i+1] * w[i+1] + 1`.

12. **LP format output:** Sections: `Minimize`, `Subject To`, `Bounds`, `End`. Terms in constraints use format `coeff varname`. Careful: LP format requires `+`/`-` signs between terms, variable names must be alphanumeric + underscore.

**Step 4: Run tests to verify they pass**

Run: `cd /Users/sean/code/daily-chow/frontend && bun run test -- src/lib/solver.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/lib/solver.ts frontend/src/lib/solver.test.ts
git commit -m "feat: LP model string generator for client-side solver"
```

---

### Task 4: Add solve function that calls HiGHS

Wire up HiGHS to parse the LP string and extract solutions.

**Files:**
- Modify: `frontend/src/lib/solver.ts`
- Modify: `frontend/src/lib/solver.test.ts`

**Step 1: Write the test**

Add to `frontend/src/lib/solver.test.ts`:
```ts
import { solveLocal } from './solver';

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
		// Calories should be within tolerance
		expect(result.meal_calories_kcal).toBeGreaterThanOrEqual(450);
		expect(result.meal_calories_kcal).toBeLessThanOrEqual(550);
	});

	it('returns infeasible for impossible constraints', async () => {
		const result = await solveLocal({
			ingredients: [
				{ key: 169756, min_g: 0, max_g: 10 }, // max 10g rice = 13 cal
			],
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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/sean/code/daily-chow/frontend && bun run test -- src/lib/solver.test.ts`
Expected: FAIL — `solveLocal` not exported.

**Step 3: Write the implementation**

Add to `frontend/src/lib/solver.ts`:

```ts
import highs_init from 'highs';
import type { SolveResponse, SolvedIngredient } from './api';

let highsInstance: Awaited<ReturnType<typeof highs_init>> | null = null;

async function getHiGHS() {
	if (!highsInstance) {
		highsInstance = await highs_init();
	}
	return highsInstance;
}

export async function solveLocal(input: LpModelInput): Promise<SolveResponse> {
	if (input.ingredients.length === 0) {
		return {
			status: 'infeasible', ingredients: [],
			meal_calories_kcal: 0, meal_protein_g: 0,
			meal_fat_g: 0, meal_carbs_g: 0, meal_fiber_g: 0,
			micros: {},
		};
	}

	const lpString = buildLpModel(input);
	const highs = await getHiGHS();
	const result = highs.solve(lpString);

	if (result.Status !== 'Optimal') {
		return {
			status: 'infeasible', ingredients: [],
			meal_calories_kcal: 0, meal_protein_g: 0,
			meal_fat_g: 0, meal_carbs_g: 0, meal_fiber_g: 0,
			micros: {},
		};
	}

	// Extract gram values from solution columns
	const cols = result.Columns;
	const ingredients: SolvedIngredient[] = [];
	let totalCal = 0, totalPro = 0, totalFat = 0, totalCarb = 0, totalFib = 0;

	for (const ing of input.ingredients) {
		const grams = cols[`g_${ing.key}`]?.Primal ?? 0;
		const food = input.foods[ing.key];
		const cal = grams * food.calories_kcal_per_100g / 100;
		const pro = grams * food.protein_g_per_100g / 100;
		const fat = grams * food.fat_g_per_100g / 100;
		const carb = grams * food.carbs_g_per_100g / 100;
		const fib = grams * food.fiber_g_per_100g / 100;
		totalCal += cal; totalPro += pro; totalFat += fat;
		totalCarb += carb; totalFib += fib;

		ingredients.push({
			key: ing.key,
			grams: Math.round(grams),
			calories_kcal: Math.round(cal * 10) / 10,
			protein_g: Math.round(pro * 10) / 10,
			fat_g: Math.round(fat * 10) / 10,
			carbs_g: Math.round(carb * 10) / 10,
			fiber_g: Math.round(fib * 10) / 10,
		});
	}

	return {
		status: 'optimal',
		ingredients,
		meal_calories_kcal: Math.round(totalCal * 10) / 10,
		meal_protein_g: Math.round(totalPro * 10) / 10,
		meal_fat_g: Math.round(totalFat * 10) / 10,
		meal_carbs_g: Math.round(totalCarb * 10) / 10,
		meal_fiber_g: Math.round(totalFib * 10) / 10,
		micros: {},  // Micro results are computed in Task 5
	};
}
```

Note: The exact HiGHS API shape (`result.Status`, `result.Columns[name].Primal`) should be verified against the `highs` package types. Check `node_modules/highs/` for the actual TypeScript definitions after install.

**Step 4: Run tests to verify they pass**

Run: `cd /Users/sean/code/daily-chow/frontend && bun run test -- src/lib/solver.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/lib/solver.ts frontend/src/lib/solver.test.ts
git commit -m "feat: solveLocal function using HiGHS WASM"
```

---

### Task 5: Compute micro results on the client

The server endpoint computes `MicroResult` objects (total, pinned, dri, remaining, pct, optimized, ear, ul) using DRI data. Port this logic so the client-side solver returns the full `micros` field.

**Files:**
- Modify: `frontend/src/lib/solver.ts`
- Modify: `frontend/src/lib/solver.test.ts`

**Step 1: Write the test**

Add to `frontend/src/lib/solver.test.ts`:
```ts
describe('solveLocal micro results', () => {
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
	});
});
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/sean/code/daily-chow/frontend && bun run test -- src/lib/solver.test.ts`
Expected: FAIL — micros is empty `{}`.

**Step 3: Write the implementation**

Update `solveLocal` to accept `sex`, `age_group`, `optimize_nutrients`, and `pinned_micros` parameters. After solving, compute micro results:

```ts
import { DRI_TARGETS, DRI_UL, DRI_EAR, MICRO_KEYS } from './dri';

// Add to LpModelInput:
//   sex?: string;
//   age_group?: string;
//   optimize_nutrients?: string[];
//   pinned_micros?: Record<string, number>;

// In solveLocal, after extracting gram values:
function computeMicroResults(
	input: LpModelInput,
	gramValues: Record<number, number>,
): Record<string, MicroResult> {
	const sex = input.sex ?? 'male';
	const ageGroup = input.age_group ?? '19-30';
	const dri = DRI_TARGETS[sex]?.[ageGroup] ?? {};
	const ulTable = DRI_UL[sex]?.[ageGroup] ?? {};
	const earTable = DRI_EAR[sex]?.[ageGroup] ?? {};
	const optimizedSet = new Set(input.optimize_nutrients ?? []);
	const pinnedMicros = input.pinned_micros ?? {};

	const micros: Record<string, MicroResult> = {};
	for (const key of MICRO_KEYS) {
		const driVal = dri[key] ?? 0;
		const pinnedVal = pinnedMicros[key] ?? 0;
		const remaining = Math.max(0, driVal - pinnedVal);

		// Compute meal total from solved grams
		let mealTotal = 0;
		for (const ing of input.ingredients) {
			const grams = gramValues[ing.key] ?? 0;
			const food = input.foods[ing.key];
			const per100g = food.micros[key] ?? 0;
			mealTotal += grams * per100g / 100;
		}

		const pct = driVal > 0 ? (mealTotal + pinnedVal) / driVal * 100 : 0;

		micros[key] = {
			total: Math.round(mealTotal * 100) / 100,
			pinned: Math.round(pinnedVal * 100) / 100,
			dri: Math.round(driVal * 100) / 100,
			remaining: Math.round(remaining * 100) / 100,
			pct: Math.round(pct * 10) / 10,
			optimized: optimizedSet.has(key),
			ear: earTable[key] ?? null,
			ul: ulTable[key] ?? null,
		};
	}
	return micros;
}
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/sean/code/daily-chow/frontend && bun run test -- src/lib/solver.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/lib/solver.ts frontend/src/lib/solver.test.ts
git commit -m "feat: compute micro results in client-side solver"
```

---

### Task 6: Comprehensive solver comparison tests

Test that the client-side solver produces results comparable to the Python solver on realistic scenarios. These tests use the real food database (loaded via the API at test time or from a fixture).

**Files:**
- Create: `frontend/src/lib/solver-comparison.test.ts`

**Step 1: Create test fixture data**

Extract test food data from the Python food database. Run a quick script to dump the foods used in `_default_ingredients()` (White Rice, Broccoli, Carrots, Zucchini, Avocado Oil, Black Beans, Split Peas, Ground Beef, Chicken Thigh) as a JSON fixture:

Run: `cd /Users/sean/code/daily-chow && uv run python -c "
import json
from daily_chow.food_db import load_foods
foods = load_foods()
names = ['White Rice', 'Broccoli', 'Carrots', 'Zucchini', 'Avocado Oil', 'Black Beans', 'Split Peas', 'Ground Beef', 'Chicken Thigh']
result = {}
for fdc_id, f in foods.items():
    if any(n.lower() in f.name.lower() for n in names):
        result[fdc_id] = {
            'fdc_id': f.fdc_id, 'name': f.name, 'subtitle': f.subtitle,
            'usda_description': f.usda_description,
            'calories_kcal_per_100g': f.calories_kcal_per_100g,
            'protein_g_per_100g': f.protein_g_per_100g,
            'fat_g_per_100g': f.fat_g_per_100g,
            'carbs_g_per_100g': f.carbs_g_per_100g,
            'fiber_g_per_100g': f.fiber_g_per_100g,
            'category': f.category, 'commonness': f.commonness,
            'micros': f.micros,
        }
print(json.dumps(result, indent=2))
" > frontend/src/lib/test-foods.json`

**Step 2: Write comparison tests**

Create `frontend/src/lib/solver-comparison.test.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { solveLocal } from './solver';
import type { Food } from './api';
import testFoodsRaw from './test-foods.json';

const testFoods = testFoodsRaw as Record<string, Food>;

// Helper to find food by name substring
function findKey(name: string): number {
	for (const [key, food] of Object.entries(testFoods)) {
		if (food.name.toLowerCase().includes(name.toLowerCase())) return Number(key);
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

describe('solver comparison', () => {
	it('default ingredients are feasible', async () => {
		const result = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods as unknown as Record<number, Food>,
			targets: { meal_calories_kcal: 2780, cal_tolerance: 50 },
		});
		expect(result.status).toBe('optimal');
	});

	it('calories within tolerance', async () => {
		const result = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods as unknown as Record<number, Food>,
			targets: { meal_calories_kcal: 2780, cal_tolerance: 50 },
		});
		expect(result.meal_calories_kcal).toBeGreaterThanOrEqual(2730);
		expect(result.meal_calories_kcal).toBeLessThanOrEqual(2830);
	});

	it('hard protein floor respected', async () => {
		const result = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods as unknown as Record<number, Food>,
			targets: { meal_calories_kcal: 2780, cal_tolerance: 50 },
			macro_constraints: [{ nutrient: 'protein', mode: 'gte', grams: 130, hard: true }],
		});
		expect(result.status).toBe('optimal');
		expect(result.meal_protein_g).toBeGreaterThanOrEqual(129);
	});

	it('hard fat eq respected', async () => {
		const result = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods as unknown as Record<number, Food>,
			targets: { meal_calories_kcal: 2780, cal_tolerance: 50 },
			macro_constraints: [{ nutrient: 'fat', mode: 'eq', grams: 80, hard: true }],
		});
		expect(result.status).toBe('optimal');
		expect(result.meal_fat_g).toBeGreaterThanOrEqual(78);
		expect(result.meal_fat_g).toBeLessThanOrEqual(82);
	});

	it('micro optimization produces non-zero shortfall coverage', async () => {
		const result = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods as unknown as Record<number, Food>,
			targets: { meal_calories_kcal: 2780, cal_tolerance: 50 },
			micro_targets: {
				calcium_mg: 800, iron_mg: 10, magnesium_mg: 500, vitamin_c_mg: 200,
			},
			sex: 'male',
			age_group: '19-30',
			optimize_nutrients: ['calcium_mg', 'iron_mg', 'magnesium_mg', 'vitamin_c_mg'],
		});
		expect(result.status).toBe('optimal');
		// Each nutrient should get some coverage
		for (const key of ['calcium_mg', 'iron_mg', 'magnesium_mg', 'vitamin_c_mg']) {
			expect(result.micros[key].total).toBeGreaterThan(0);
		}
	});

	it('UL hard constraint caps nutrient', async () => {
		const result = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods as unknown as Record<number, Food>,
			targets: { meal_calories_kcal: 2780, cal_tolerance: 50 },
			micro_targets: { iron_mg: 10 },
			micro_uls: { iron_mg: 15 },
			sex: 'male',
			age_group: '19-30',
			optimize_nutrients: ['iron_mg'],
		});
		expect(result.status).toBe('optimal');
		expect(result.micros.iron_mg.total).toBeLessThanOrEqual(15.1);
	});

	it('macro ratio steers solution', async () => {
		const highFat = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods as unknown as Record<number, Food>,
			targets: { meal_calories_kcal: 2780, cal_tolerance: 50 },
			macro_ratio: {
				carb_pct: 30, protein_pct: 20, fat_pct: 50,
				pinned_carb_g: 0, pinned_protein_g: 0, pinned_fat_g: 0,
			},
			priorities: ['macro_ratio', 'total_weight'],
		});
		const lowFat = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods as unknown as Record<number, Food>,
			targets: { meal_calories_kcal: 2780, cal_tolerance: 50 },
			macro_ratio: {
				carb_pct: 60, protein_pct: 25, fat_pct: 15,
				pinned_carb_g: 0, pinned_protein_g: 0, pinned_fat_g: 0,
			},
			priorities: ['macro_ratio', 'total_weight'],
		});
		expect(highFat.meal_fat_g).toBeGreaterThan(lowFat.meal_fat_g);
	});

	it('loose constraint does not cause infeasibility', async () => {
		const result = await solveLocal({
			ingredients: defaultIngredients(),
			foods: testFoods as unknown as Record<number, Food>,
			targets: { meal_calories_kcal: 2780, cal_tolerance: 50 },
			macro_constraints: [{ nutrient: 'protein', mode: 'lte', grams: 1, hard: false }],
		});
		expect(result.status).toBe('optimal');
	});
});
```

**Step 3: Run tests**

Run: `cd /Users/sean/code/daily-chow/frontend && bun run test -- src/lib/solver-comparison.test.ts`
Expected: PASS — all scenarios produce feasible solutions matching constraints.

If any tests fail, debug by printing the LP string and HiGHS output.

**Step 4: Commit**

```bash
git add frontend/src/lib/solver-comparison.test.ts frontend/src/lib/test-foods.json
git commit -m "test: comprehensive solver comparison tests"
```

---

### Task 7: Web Worker wrapper

Run the solver in a Web Worker so it doesn't block the UI thread during drag.

**Files:**
- Create: `frontend/src/lib/solver.worker.ts`
- Modify: `frontend/src/lib/api.ts`

**Step 1: Create the worker**

Create `frontend/src/lib/solver.worker.ts`:
```ts
import { solveLocal, type LpModelInput } from './solver';

interface WorkerMessage {
	id: number;
	input: LpModelInput;
}

self.onmessage = async (e: MessageEvent<WorkerMessage>) => {
	const { id, input } = e.data;
	const result = await solveLocal(input);
	self.postMessage({ id, result });
};
```

**Step 2: Update api.ts to use the worker**

Modify `frontend/src/lib/api.ts` — replace the `solve` function's `fetch` call with a worker message:

```ts
import type { SolveResponse, Food } from './api';

let worker: Worker | null = null;
let messageId = 0;
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
			const { id, result } = e.data;
			const p = pending.get(id);
			if (p) {
				pending.delete(id);
				p.resolve(result);
			}
		};
	}
	return worker;
}
```

The `solve` function needs the `foods` data (to pass to the worker). It currently only receives `SolveIngredient[]` (key + min/max), not full `Food` objects. Two options:

- **Option A:** Pass `foods` into `solve()` as a new parameter. This requires updating the call site in `+page.svelte`.
- **Option B:** Have the worker load foods itself on init.

Choose **Option A** — it's simpler and the foods are already available in the page component.

Update the `solve` function signature:
```ts
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
	foods: Record<number, Food> = {},  // NEW parameter
): Promise<SolveResponse> {
	// Build micro_targets and micro_uls from DRI data (same logic as api.py lines 228-247)
	// Then post to worker
}
```

The DRI lookup logic (lines 224-247 of api.py) needs to move into this function — computing `micro_targets` and `micro_uls` from the raw `sex`, `age_group`, `optimize_nutrients`, and `pinned_micros` inputs.

**Step 3: Update +page.svelte call site**

Modify the `doSolve` function in `frontend/src/routes/+page.svelte` to pass `foods`:

Find the `solve(` call (around line 310) and add `foods` as the last argument.

**Step 4: Decouple saveState from solving**

In `+page.svelte`, remove `saveState()` from inside `doSolve()`. Instead, add a separate debounced save:

```ts
let saveTimeout: ReturnType<typeof setTimeout> | null = null;
function debouncedSave() {
	if (saveTimeout) clearTimeout(saveTimeout);
	saveTimeout = setTimeout(saveState, 500);
}
```

Call `debouncedSave()` at the end of `doSolve()` instead of `saveState()`.

**Step 5: Reduce debounce from 30ms to 50ms**

In `triggerSolve`, change `setTimeout(doSolve, 30)` to `setTimeout(doSolve, 50)`. With no network round-trip, 50ms is responsive enough while avoiding excessive WASM calls during fast drags.

**Step 6: Test manually**

The dev server should already be running. Open the app and verify:
- Sliders respond smoothly
- Solution updates in real-time during drag
- No network requests to `/api/solve` in the Network tab (only `/api/foods` on load)

**Step 7: Commit**

```bash
git add frontend/src/lib/solver.worker.ts frontend/src/lib/api.ts frontend/src/routes/+page.svelte
git commit -m "feat: wire solver through Web Worker, remove server dependency"
```

---

### Task 8: Discard stale solver results

When the user drags quickly, multiple solve requests may be in flight. Only the latest result should be applied.

**Files:**
- Modify: `frontend/src/lib/api.ts`

**Step 1: Add sequence tracking**

In the `solve` function, track a monotonically increasing sequence number. When a result arrives, discard it if a newer request has been sent:

```ts
let latestRequestId = 0;

export async function solve(...): Promise<SolveResponse> {
	const thisId = ++latestRequestId;
	// ... post to worker
	const result = await workerPromise;
	if (thisId !== latestRequestId) {
		// A newer request superseded this one — return a sentinel
		// that doSolve can check and ignore
		throw new Error('superseded');
	}
	return result;
}
```

Update `doSolve` in `+page.svelte` to catch and ignore the `superseded` error:
```ts
try {
	solution = await solve(...);
} catch (e) {
	if (e instanceof Error && e.message === 'superseded') return;
	solution = null;
}
```

**Step 2: Test manually**

Drag a slider rapidly. Verify no visual glitches from out-of-order results.

**Step 3: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/routes/+page.svelte
git commit -m "feat: discard stale solver results during rapid slider drag"
```

---

### Task 9: Keep server endpoint as fallback

Ensure the server endpoint still works for the export feature and as a WASM fallback.

**Files:**
- No code changes needed — the server endpoint remains unchanged.

**Step 1: Verify export still works**

The export endpoint (`/api/export`) receives a `SolveResponse` from the frontend — it doesn't call the solver itself. Verify it still works by testing the export flow in the UI.

**Step 2: Verify server solve endpoint still works**

Run: `cd /Users/sean/code/daily-chow && uv run pytest tests/test_solver.py -v`
Expected: All existing Python tests still pass.

**Step 3: Commit (if any cleanup needed)**

No commit expected unless issues are found.

---

### Task 10: Final cleanup and verification

**Step 1: Run all frontend tests**

Run: `cd /Users/sean/code/daily-chow/frontend && bun run test`
Expected: All tests pass.

**Step 2: Run all Python tests**

Run: `cd /Users/sean/code/daily-chow && uv run pytest -v`
Expected: All tests pass.

**Step 3: Run type check**

Run: `cd /Users/sean/code/daily-chow/frontend && bun run check`
Expected: No type errors.

**Step 4: Manual verification**

Open the app and verify:
- Slider drag is smooth with real-time solution updates
- No `/api/solve` requests in browser Network tab
- All UI features work: macro constraints, micro optimization, ingredient diversity, pinned meals, export

**Step 5: Commit any remaining fixes**

```bash
git add -A
git commit -m "chore: cleanup and verify client-side solver integration"
```
