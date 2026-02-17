/**
 * LP model string generator for client-side HiGHS solver.
 *
 * Translates the same inputs as the Python CP-SAT solver into a CPLEX .lp
 * format string that HiGHS can solve. Uses continuous variables in natural
 * units (grams, mg, kcal) — no integer scaling needed.
 */

import type {
	Food,
	SolveIngredient,
	SolveTargets,
	MacroRatio,
	MacroConstraint,
	SolveResponse,
	SolvedIngredient,
	MicroResult,
} from '$lib/api';
import { DRI_TARGETS, DRI_UL, DRI_EAR, MICRO_KEYS } from '$lib/dri';
import highsLoader from 'highs';

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
	sex?: string;
	age_group?: string;
	optimize_nutrients?: string[];
	pinned_micros?: Record<string, number>;
}

// Priority constants matching Python solver
const PRIORITY_MICROS = 'micros';
const PRIORITY_MACRO_RATIO = 'macro_ratio';
const PRIORITY_INGREDIENT_DIVERSITY = 'ingredient_diversity';
const PRIORITY_TOTAL_WEIGHT = 'total_weight';
const DEFAULT_PRIORITIES = [
	PRIORITY_MICROS,
	PRIORITY_MACRO_RATIO,
	PRIORITY_INGREDIENT_DIVERSITY,
	PRIORITY_TOTAL_WEIGHT,
];

/** Format a number for LP output, avoiding -0 and unnecessary precision. */
function fmt(n: number): string {
	if (Math.abs(n) < 1e-12) return '0';
	// Use enough precision to not lose nutritional data
	const s = n.toPrecision(10);
	// Strip trailing zeros after decimal point
	if (s.includes('.')) {
		return s.replace(/\.?0+$/, '');
	}
	return s;
}

/** Build a linear expression string from terms, omitting zero coefficients. */
function buildExpr(terms: [number, string][]): string {
	const parts: string[] = [];
	for (const [coeff, varName] of terms) {
		if (Math.abs(coeff) < 1e-12) continue;
		if (parts.length === 0) {
			if (coeff === 1) {
				parts.push(varName);
			} else if (coeff === -1) {
				parts.push(`- ${varName}`);
			} else if (coeff < 0) {
				parts.push(`- ${fmt(-coeff)} ${varName}`);
			} else {
				parts.push(`${fmt(coeff)} ${varName}`);
			}
		} else {
			if (coeff === 1) {
				parts.push(`+ ${varName}`);
			} else if (coeff === -1) {
				parts.push(`- ${varName}`);
			} else if (coeff < 0) {
				parts.push(`- ${fmt(-coeff)} ${varName}`);
			} else {
				parts.push(`+ ${fmt(coeff)} ${varName}`);
			}
		}
	}
	return parts.join(' ') || '0';
}

/** Sanitize a nutrient key to be a valid LP variable name component. */
function sanitize(key: string): string {
	return key.replace(/[^a-zA-Z0-9_]/g, '_');
}

export function buildLpModel(input: LpModelInput): string {
	const {
		ingredients,
		foods,
		targets,
		micro_targets,
		micro_uls,
		macro_ratio,
		macro_constraints,
		micro_strategy = 'depth',
	} = input;
	const priorities = input.priorities ?? [...DEFAULT_PRIORITIES];

	const constraints: string[] = [];
	const bounds: string[] = [];

	// Track objective terms: (expression_var, max_possible_value)
	const objTerms: { varName: string; maxVal: number }[] = [];

	// Auxiliary variable counters for unique naming
	const auxVars = new Set<string>();

	function addBound(lb: number, varName: string, ub: number) {
		bounds.push(` ${fmt(lb)} <= ${varName} <= ${fmt(ub)}`);
		auxVars.add(varName);
	}

	function addLowerBound(varName: string, lb: number = 0) {
		bounds.push(` ${varName} >= ${fmt(lb)}`);
		auxVars.add(varName);
	}

	// ── Decision variables ──────────────────────────────────────────
	for (const ing of ingredients) {
		addBound(ing.min_g, `g_${ing.key}`, ing.max_g);
	}

	// Precompute per-gram coefficients (natural units, no scaling)
	const calPerG: Record<number, number> = {};
	const proPerG: Record<number, number> = {};
	const fatPerG: Record<number, number> = {};
	const carbPerG: Record<number, number> = {};
	const fibPerG: Record<number, number> = {};

	for (const ing of ingredients) {
		const f = foods[ing.key];
		calPerG[ing.key] = f.calories_kcal_per_100g / 100;
		proPerG[ing.key] = f.protein_g_per_100g / 100;
		fatPerG[ing.key] = f.fat_g_per_100g / 100;
		carbPerG[ing.key] = f.carbs_g_per_100g / 100;
		fibPerG[ing.key] = f.fiber_g_per_100g / 100;
	}

	const macroCoeffMap: Record<string, Record<number, number>> = {
		carbs: carbPerG,
		protein: proPerG,
		fat: fatPerG,
		fiber: fibPerG,
	};

	// Helper to build sum expression terms for a coefficient map
	function nutrientTerms(coeffs: Record<number, number>): [number, string][] {
		return ingredients.map((ing) => [coeffs[ing.key], `g_${ing.key}`]);
	}

	// ── Calorie band ────────────────────────────────────────────────
	const calLo = targets.meal_calories_kcal - targets.cal_tolerance;
	const calHi = targets.meal_calories_kcal + targets.cal_tolerance;

	constraints.push(` cal_lo: ${buildExpr(nutrientTerms(calPerG))} >= ${fmt(calLo)}`);
	constraints.push(` cal_hi: ${buildExpr(nutrientTerms(calPerG))} <= ${fmt(calHi)}`);

	// ── Macro constraints ───────────────────────────────────────────
	const looseDevVars: string[] = [];
	let maxLooseDev = 0;

	if (macro_constraints) {
		for (const mc of macro_constraints) {
			if (mc.mode === 'none') continue;
			const coeffs = macroCoeffMap[mc.nutrient];
			const terms = nutrientTerms(coeffs);
			const target = mc.grams;

			if (mc.hard) {
				if (mc.mode === 'gte') {
					constraints.push(` ${mc.nutrient}_gte: ${buildExpr(terms)} >= ${fmt(target)}`);
				} else if (mc.mode === 'lte') {
					constraints.push(` ${mc.nutrient}_lte: ${buildExpr(terms)} <= ${fmt(target)}`);
				} else if (mc.mode === 'eq') {
					constraints.push(` ${mc.nutrient}_eq_lo: ${buildExpr(terms)} >= ${fmt(target)}`);
					constraints.push(` ${mc.nutrient}_eq_hi: ${buildExpr(terms)} <= ${fmt(target)}`);
				}
			} else {
				// Soft / loose constraint
				const name = `loose_${mc.nutrient}_${mc.mode}`;
				const maxPossible = ingredients.reduce(
					(s, ing) => s + ing.max_g * coeffs[ing.key],
					0
				);
				const devBound = Math.max(maxPossible, target);

				if (mc.mode === 'gte') {
					// dev >= target - actual => dev + actual >= target
					// Rewrite: dev + sum(coeff * g) >= target
					const devTerms: [number, string][] = [[1, `${name}_dev`], ...terms];
					constraints.push(` ${name}_c: ${buildExpr(devTerms)} >= ${fmt(target)}`);
					addBound(0, `${name}_dev`, devBound);
				} else if (mc.mode === 'lte') {
					// dev >= actual - target => dev - sum(coeff * g) >= -target
					// Rewrite: dev - actual >= -target
					const devTerms: [number, string][] = [
						[1, `${name}_dev`],
						...terms.map(([c, v]) => [-c, v] as [number, string]),
					];
					constraints.push(
						` ${name}_c: ${buildExpr(devTerms)} >= ${fmt(-target)}`
					);
					addBound(0, `${name}_dev`, devBound);
				} else if (mc.mode === 'eq') {
					// Absolute value via pos/neg split:
					// actual - target = pos - neg, dev = pos + neg
					// => sum(coeff*g) - pos + neg = target
					// => dev - pos - neg = 0
					const diffTerms: [number, string][] = [
						...terms,
						[-1, `${name}_pos`],
						[1, `${name}_neg`],
					];
					constraints.push(` ${name}_diff: ${buildExpr(diffTerms)} = ${fmt(target)}`);
					constraints.push(
						` ${name}_abs: ${name}_dev - ${name}_pos - ${name}_neg = 0`
					);
					addBound(0, `${name}_pos`, devBound);
					addBound(0, `${name}_neg`, devBound);
					addBound(0, `${name}_dev`, devBound);
				}

				// Normalize deviation to percentage [0, 1]
				// pct_dev >= dev / normalizer
				// => pct_dev * normalizer >= dev  (keep linear)
				// => pct_dev * normalizer - dev >= 0
				const normDenom =
					mc.mode === 'gte' ? Math.max(target, 1e-9) : Math.max(devBound, 1e-9);
				constraints.push(
					` ${name}_pct_c: ${fmt(normDenom)} ${name}_pct - ${name}_dev >= 0`
				);
				addBound(0, `${name}_pct`, 1);

				looseDevVars.push(`${name}_pct`);
				maxLooseDev = 1;
			}
		}
	}

	// Minimax over loose deviations
	let hasWorstLoose = false;
	let maxWorstLoose = 0;

	if (looseDevVars.length > 0) {
		addBound(0, 'worst_loose', maxLooseDev);
		for (const dv of looseDevVars) {
			constraints.push(` worst_loose_${dv}: worst_loose - ${dv} >= 0`);
		}
		hasWorstLoose = true;
		maxWorstLoose = maxLooseDev;
	}

	// ── UL hard constraints ─────────────────────────────────────────
	// Helper to get micro per-gram coefficient
	function microPerG(foodObj: Food, key: string): number {
		return (foodObj.micros[key] ?? 0) / 100;
	}

	function microTerms(key: string): [number, string][] {
		return ingredients
			.map((ing) => [microPerG(foods[ing.key], key), `g_${ing.key}`] as [number, string])
			.filter(([c]) => Math.abs(c) > 1e-12);
	}

	if (micro_uls) {
		for (const [key, ulVal] of Object.entries(micro_uls)) {
			if (ulVal <= 0) continue;
			const terms = microTerms(key);
			if (terms.length === 0) continue;
			const sKey = sanitize(key);
			constraints.push(` ul_${sKey}: ${buildExpr(terms)} <= ${fmt(ulVal)}`);
		}
	}

	// ── Micronutrient minimax objective ──────────────────────────────
	let hasWorstPct = false;
	let maxWorstPct = 0;
	const pctShortVars: string[] = [];

	if (micro_targets) {
		for (const [key, targetVal] of Object.entries(micro_targets)) {
			if (targetVal <= 0) continue;
			const terms = microTerms(key);
			const sKey = sanitize(key);

			// shortfall >= target - sum(per_g * g), shortfall >= 0
			// => shortfall + sum(per_g * g) >= target
			const shortTerms: [number, string][] = [[1, `${sKey}_short`], ...terms];
			constraints.push(` ${sKey}_short_c: ${buildExpr(shortTerms)} >= ${fmt(targetVal)}`);
			addBound(0, `${sKey}_short`, targetVal);

			// pct_short >= shortfall / target
			// => pct_short * target >= shortfall
			// => pct_short * target - shortfall >= 0
			constraints.push(
				` ${sKey}_pct_c: ${fmt(targetVal)} ${sKey}_pct - ${sKey}_short >= 0`
			);
			addBound(0, `${sKey}_pct`, 1);

			pctShortVars.push(`${sKey}_pct`);
		}

		if (pctShortVars.length > 0) {
			// worst_pct >= each pct_short
			addBound(0, 'worst_pct', 1);
			for (const ps of pctShortVars) {
				constraints.push(` worst_pct_${ps}: worst_pct - ${ps} >= 0`);
			}
			hasWorstPct = true;
			maxWorstPct = 1;
		}
	}

	// micro_sum = sum of all pct_short vars (tiebreaker)
	// Encode as: micro_sum - sum(pct_short) = 0
	let hasMicroSum = false;
	let maxMicroPctSum = 0;

	if (pctShortVars.length > 0) {
		const sumTerms: [number, string][] = [
			[1, 'micro_sum'],
			...pctShortVars.map((v) => [-1, v] as [number, string]),
		];
		constraints.push(` micro_sum_def: ${buildExpr(sumTerms)} = 0`);
		maxMicroPctSum = pctShortVars.length; // each pct_short <= 1
		addBound(0, 'micro_sum', maxMicroPctSum);
		hasMicroSum = true;
	}

	// ── UL proximity penalty ────────────────────────────────────────
	let hasWorstUlProx = false;
	let maxWorstUlProx = 0;

	if (micro_targets && micro_uls) {
		const ulProxVars: string[] = [];

		for (const [key, targetVal] of Object.entries(micro_targets)) {
			const ulVal = micro_uls[key];
			if (ulVal === undefined) continue;
			const headroom = ulVal - targetVal;
			if (headroom <= 0) continue;
			const sKey = sanitize(key);
			const terms = microTerms(key);

			// excess >= total - target, excess >= 0
			// => excess - sum(per_g * g) >= -target
			const excessTerms: [number, string][] = [
				[1, `${sKey}_ul_excess`],
				...terms.map(([c, v]) => [-c, v] as [number, string]),
			];
			constraints.push(
				` ${sKey}_ul_excess_c: ${buildExpr(excessTerms)} >= ${fmt(-targetVal)}`
			);
			addBound(0, `${sKey}_ul_excess`, headroom);

			// ul_prox >= excess / headroom
			// => ul_prox * headroom - excess >= 0
			constraints.push(
				` ${sKey}_ul_prox_c: ${fmt(headroom)} ${sKey}_ul_prox - ${sKey}_ul_excess >= 0`
			);
			addBound(0, `${sKey}_ul_prox`, 1);

			ulProxVars.push(`${sKey}_ul_prox`);
		}

		if (ulProxVars.length > 0) {
			addBound(0, 'worst_ul_prox', 1);
			for (const up of ulProxVars) {
				constraints.push(` worst_ul_prox_${up}: worst_ul_prox - ${up} >= 0`);
			}
			hasWorstUlProx = true;
			maxWorstUlProx = 1;
		}
	}

	// ── Macro ratio minimax ─────────────────────────────────────────
	let hasMacroWorst = false;
	let maxMacroWorst = 0;

	if (macro_ratio) {
		const pinnedCarbCal = macro_ratio.pinned_carb_g * 4;
		const pinnedProCal = macro_ratio.pinned_protein_g * 4;
		const pinnedFatCal = macro_ratio.pinned_fat_g * 9;
		const pinnedCal = pinnedCarbCal + pinnedProCal + pinnedFatCal;

		// Constant denominator: target meal calories + pinned calories
		const calDenom = targets.meal_calories_kcal + pinnedCal;

		// Exclude macros with active constraints
		const ratioExcluded = new Set<string>();
		if (macro_constraints) {
			for (const mc of macro_constraints) {
				if (mc.mode !== 'none') ratioExcluded.add(mc.nutrient);
			}
		}

		const macroEntries: { name: string; nutrient: string; calCoeffs: Record<number, number>; pinnedCal: number; targetPct: number }[] = [
			{
				name: 'carb',
				nutrient: 'carbs',
				calCoeffs: Object.fromEntries(ingredients.map((ing) => [ing.key, carbPerG[ing.key] * 4])),
				pinnedCal: pinnedCarbCal,
				targetPct: macro_ratio.carb_pct,
			},
			{
				name: 'pro',
				nutrient: 'protein',
				calCoeffs: Object.fromEntries(ingredients.map((ing) => [ing.key, proPerG[ing.key] * 4])),
				pinnedCal: pinnedProCal,
				targetPct: macro_ratio.protein_pct,
			},
			{
				name: 'fat',
				nutrient: 'fat',
				calCoeffs: Object.fromEntries(ingredients.map((ing) => [ing.key, fatPerG[ing.key] * 9])),
				pinnedCal: pinnedFatCal,
				targetPct: macro_ratio.fat_pct,
			},
		];

		const macroDevVars: string[] = [];

		for (const entry of macroEntries) {
			if (ratioExcluded.has(entry.nutrient)) continue;

			// day_X_cal = sum(calCoeff * g) + pinnedCal
			// day_total_cal = sum(all_cal_coeffs * g) + pinnedCal_total
			// We want: |day_X_cal / day_total_cal - targetPct/100| to be small
			// Using constant denominator calDenom:
			// diff = day_X_cal * 100 - day_total_cal_approx * targetPct
			//      = sum(calCoeff * g) * 100 + pinnedCal * 100 - calDenom * targetPct
			// But we use calDenom as constant denominator approximation.
			// diff_expr = sum(calCoeff_i * 100 * g_i) + pinnedCal * 100 - calDenom * targetPct
			// abs_diff via pos/neg split: diff_expr = pos - neg, abs_val = pos + neg

			// Actually, matching the Python more precisely:
			// diff_expr = day_X_cal * 100 - day_total_cal * targetPct
			// But day_total_cal involves all three macros' calories from meal + pinned.
			// The Python uses: diff_expr = cal_expr * 100 - day_total_cal * target_pct
			// where day_total_cal = sum over all macros of (meal_macro_cal + pinned_macro_cal)
			//
			// To keep this linear and matching the Python's constant-denominator approach:
			// pct_dev * calDenom * 100 >= abs_diff
			// where abs_diff is in calorie units * 100 (percentage points * calDenom)

			// Build: sum(calCoeff_i * g_i) * 100 - total_meal_cal * targetPct + pinnedCal * 100 - pinnedTotalCal * targetPct
			// But total_meal_cal involves all macros too. The Python constructs:
			// day_X_cal = total_X * cal_factor + pinned_X_cal
			// day_total_cal = day_carb_cal + day_pro_cal + day_fat_cal
			// diff = day_X_cal * 100 - day_total_cal * target_pct
			//
			// With constant denominator approach, we approximate day_total_cal ~ calDenom:
			// diff ≈ day_X_cal * 100 - calDenom * target_pct
			// = (sum(calCoeff * g) + pinnedXCal) * 100 - calDenom * target_pct

			const rhs = calDenom * entry.targetPct - entry.pinnedCal * 100;
			// diff_var = sum(calCoeff * g) * 100 - rhs = pos - neg

			const maxMealCal = ingredients.reduce(
				(s, ing) => s + ing.max_g * (carbPerG[ing.key] * 4 + proPerG[ing.key] * 4 + fatPerG[ing.key] * 9),
				0
			);
			const bound = (maxMealCal + pinnedCal) * 100;

			// sum(calCoeff_i * 100 * g_i) - pos + neg = rhs
			const diffTerms: [number, string][] = [
				...ingredients.map(
					(ing) =>
						[entry.calCoeffs[ing.key] * 100, `g_${ing.key}`] as [number, string]
				),
				[-1, `macro_${entry.name}_pos`],
				[1, `macro_${entry.name}_neg`],
			];
			constraints.push(
				` macro_${entry.name}_diff: ${buildExpr(diffTerms)} = ${fmt(rhs)}`
			);

			addBound(0, `macro_${entry.name}_pos`, bound);
			addBound(0, `macro_${entry.name}_neg`, bound);

			// abs_dev = pos + neg (implicit via pct_dev constraint)
			// pct_dev >= abs_dev / (calDenom * 100)
			// => pct_dev * calDenom * 100 >= pos + neg
			// => pct_dev * calDenom * 100 - pos - neg >= 0
			const pctDenom = calDenom * 100;
			constraints.push(
				` macro_${entry.name}_pct_c: ${fmt(pctDenom)} macro_${entry.name}_pctdev - macro_${entry.name}_pos - macro_${entry.name}_neg >= 0`
			);
			addBound(0, `macro_${entry.name}_pctdev`, 1);

			macroDevVars.push(`macro_${entry.name}_pctdev`);
		}

		if (macroDevVars.length > 0) {
			addBound(0, 'macro_worst', 1);
			for (const dv of macroDevVars) {
				constraints.push(` macro_worst_${dv}: macro_worst - ${dv} >= 0`);
			}
			hasMacroWorst = true;
			maxMacroWorst = 1;
		}
	}

	// ── Combined macro var ──────────────────────────────────────────
	let hasCombinedMacro = false;
	let maxCombinedMacro = 0;
	let combinedMacroVar: string | null = null;

	const macroPieces: { varName: string; maxVal: number }[] = [];
	if (hasMacroWorst && maxMacroWorst > 0) {
		macroPieces.push({ varName: 'macro_worst', maxVal: maxMacroWorst });
	}
	if (hasWorstLoose && maxWorstLoose > 0) {
		macroPieces.push({ varName: 'worst_loose', maxVal: maxWorstLoose });
	}

	if (macroPieces.length === 1) {
		combinedMacroVar = macroPieces[0].varName;
		maxCombinedMacro = macroPieces[0].maxVal;
		hasCombinedMacro = true;
	} else if (macroPieces.length > 1) {
		maxCombinedMacro = Math.max(...macroPieces.map((p) => p.maxVal));
		addBound(0, 'combined_macro', maxCombinedMacro);
		for (const p of macroPieces) {
			constraints.push(` combined_macro_${p.varName}: combined_macro - ${p.varName} >= 0`);
		}
		combinedMacroVar = 'combined_macro';
		hasCombinedMacro = true;
	}

	// ── Ingredient diversity ────────────────────────────────────────
	let hasDiversity = false;
	let maxDiversity = 0;

	if (priorities.includes(PRIORITY_INGREDIENT_DIVERSITY)) {
		const maxPossible = Math.max(...ingredients.map((ing) => ing.max_g));
		addBound(0, 'max_gram', maxPossible);
		for (const ing of ingredients) {
			constraints.push(` max_gram_g_${ing.key}: max_gram - g_${ing.key} >= 0`);
		}
		hasDiversity = true;
		maxDiversity = maxPossible;
	}

	// ── Build lexicographic objective ───────────────────────────────
	const maxTotal = ingredients.reduce((s, ing) => s + ing.max_g, 0);

	// Collect terms in priority order: (varName, maxVal)
	const lexTerms: { varName: string; maxVal: number }[] = [];

	for (const p of priorities) {
		if (p === PRIORITY_MICROS) {
			if (hasWorstUlProx && maxWorstUlProx > 0) {
				lexTerms.push({ varName: 'worst_ul_prox', maxVal: maxWorstUlProx });
			}
			if (micro_strategy === 'breadth') {
				if (hasMicroSum && maxMicroPctSum > 0) {
					lexTerms.push({ varName: 'micro_sum', maxVal: maxMicroPctSum });
				}
				if (hasWorstPct && maxWorstPct > 0) {
					lexTerms.push({ varName: 'worst_pct', maxVal: maxWorstPct });
				}
			} else {
				if (hasWorstPct && maxWorstPct > 0) {
					lexTerms.push({ varName: 'worst_pct', maxVal: maxWorstPct });
				}
				if (hasMicroSum && maxMicroPctSum > 0) {
					lexTerms.push({ varName: 'micro_sum', maxVal: maxMicroPctSum });
				}
			}
		} else if (p === PRIORITY_MACRO_RATIO) {
			if (hasCombinedMacro && combinedMacroVar && maxCombinedMacro > 0) {
				lexTerms.push({ varName: combinedMacroVar, maxVal: maxCombinedMacro });
			}
		} else if (p === PRIORITY_INGREDIENT_DIVERSITY) {
			if (hasDiversity && maxDiversity > 0) {
				lexTerms.push({ varName: 'max_gram', maxVal: maxDiversity });
			}
		} else if (p === PRIORITY_TOTAL_WEIGHT) {
			// total_weight = sum of all g_<key> — expressed inline in objective
			lexTerms.push({ varName: '__total_weight__', maxVal: maxTotal });
		}
	}

	// Fallback: if no terms, minimize total weight
	if (lexTerms.length === 0) {
		lexTerms.push({ varName: '__total_weight__', maxVal: maxTotal });
	}

	// Compute weights: w[-1]=1, w[i] = max[i+1] * w[i+1] + 1
	const weights = new Array(lexTerms.length).fill(1);
	for (let i = lexTerms.length - 2; i >= 0; i--) {
		weights[i] = lexTerms[i + 1].maxVal * weights[i + 1] + 1;
	}

	// Build objective expression
	const objExprTerms: [number, string][] = [];
	for (let i = 0; i < lexTerms.length; i++) {
		const w = weights[i];
		const t = lexTerms[i];
		if (t.varName === '__total_weight__') {
			// Expand inline: w * sum(g_<key>)
			for (const ing of ingredients) {
				objExprTerms.push([w, `g_${ing.key}`]);
			}
		} else {
			objExprTerms.push([w, t.varName]);
		}
	}

	// ── Assemble LP string ──────────────────────────────────────────
	const lines: string[] = [];
	lines.push('Minimize');
	lines.push(` obj: ${buildExpr(objExprTerms)}`);
	lines.push('Subject To');
	for (const c of constraints) {
		lines.push(c);
	}
	lines.push('Bounds');
	for (const b of bounds) {
		lines.push(b);
	}
	lines.push('End');

	return lines.join('\n');
}

// ── Micro results computation ───────────────────────────────────────

/**
 * Compute MicroResult for each of the 20 MICRO_KEYS nutrients.
 *
 * Mirrors the Python API logic in api.py lines 240-259.
 */
function computeMicroResults(
	solvedIngredients: SolvedIngredient[],
	foods: Record<number, Food>,
	sex: string,
	ageGroup: string,
	optimizeNutrients: string[],
	pinnedMicros: Record<string, number>,
): Record<string, MicroResult> {
	const driTable = DRI_TARGETS[sex]?.[ageGroup] ?? {};
	const earTable = DRI_EAR[sex]?.[ageGroup] ?? {};
	const ulTable = DRI_UL[sex]?.[ageGroup] ?? {};
	const optimizedSet = new Set(optimizeNutrients);

	const micros: Record<string, MicroResult> = {};
	for (const key of MICRO_KEYS) {
		const driVal = driTable[key] ?? 0;
		const pinnedVal = pinnedMicros[key] ?? 0;
		const remainingVal = Math.max(0, driVal - pinnedVal);

		// Sum nutrient from solved grams: grams * food.micros[key] / 100
		let mealTotal = 0;
		for (const si of solvedIngredients) {
			const food = foods[si.key];
			mealTotal += si.grams * (food.micros[key] ?? 0) / 100;
		}

		const pct = driVal > 0 ? (mealTotal + pinnedVal) / driVal * 100 : 0;

		micros[key] = {
			total: Math.round(mealTotal * 100) / 100,
			pinned: Math.round(pinnedVal * 100) / 100,
			dri: Math.round(driVal * 100) / 100,
			remaining: Math.round(remainingVal * 100) / 100,
			pct: Math.round(pct * 10) / 10,
			optimized: optimizedSet.has(key),
			ear: earTable[key] ?? null,
			ul: ulTable[key] ?? null,
		};
	}
	return micros;
}

// ── HiGHS solver integration ───────────────────────────────────────

/** Cached HiGHS WASM singleton. */
let highsPromise: ReturnType<typeof highsLoader> | null = null;

function getHighs() {
	if (!highsPromise) {
		highsPromise = highsLoader();
	}
	return highsPromise;
}

/**
 * Solve a meal optimisation problem locally using HiGHS WASM.
 *
 * Returns a SolveResponse with status, per-ingredient macros, and meal totals.
 * The `micros` field is left empty (`{}`) — Task 5 will fill it in.
 */
export async function solveLocal(input: LpModelInput): Promise<SolveResponse> {
	// Early exit for empty ingredients
	if (input.ingredients.length === 0) {
		return {
			status: 'infeasible',
			ingredients: [],
			meal_calories_kcal: 0,
			meal_protein_g: 0,
			meal_fat_g: 0,
			meal_carbs_g: 0,
			meal_fiber_g: 0,
			micros: {},
		};
	}

	const lpString = buildLpModel(input);
	const highs = await getHighs();
	const result = highs.solve(lpString);

	if (result.Status !== 'Optimal') {
		return {
			status: 'infeasible',
			ingredients: [],
			meal_calories_kcal: 0,
			meal_protein_g: 0,
			meal_fat_g: 0,
			meal_carbs_g: 0,
			meal_fiber_g: 0,
			micros: {},
		};
	}

	// Extract gram values from solution columns
	const solvedIngredients: SolvedIngredient[] = [];
	let totalCal = 0;
	let totalPro = 0;
	let totalFat = 0;
	let totalCarb = 0;
	let totalFiber = 0;

	for (const ing of input.ingredients) {
		const colName = `g_${ing.key}`;
		const col = result.Columns[colName];
		const grams = col?.Primal ?? 0;

		const food = input.foods[ing.key];
		const cal = grams * food.calories_kcal_per_100g / 100;
		const pro = grams * food.protein_g_per_100g / 100;
		const fat = grams * food.fat_g_per_100g / 100;
		const carb = grams * food.carbs_g_per_100g / 100;
		const fiber = grams * food.fiber_g_per_100g / 100;

		solvedIngredients.push({
			key: ing.key,
			grams,
			calories_kcal: cal,
			protein_g: pro,
			fat_g: fat,
			carbs_g: carb,
			fiber_g: fiber,
		});

		totalCal += cal;
		totalPro += pro;
		totalFat += fat;
		totalCarb += carb;
		totalFiber += fiber;
	}

	// Compute micro results for all 20 tracked nutrients
	const sex = input.sex ?? 'male';
	const ageGroup = input.age_group ?? '19-30';
	const optimizeNutrients = input.optimize_nutrients ?? [];
	const pinnedMicros = input.pinned_micros ?? {};

	const micros = computeMicroResults(
		solvedIngredients,
		input.foods,
		sex,
		ageGroup,
		optimizeNutrients,
		pinnedMicros,
	);

	return {
		status: 'optimal',
		ingredients: solvedIngredients,
		meal_calories_kcal: totalCal,
		meal_protein_g: totalPro,
		meal_fat_g: totalFat,
		meal_carbs_g: totalCarb,
		meal_fiber_g: totalFiber,
		micros,
	};
}
