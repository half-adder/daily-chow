"""CP-SAT constraint solver for daily meal macro optimization.

Finds integer gram quantities for each enabled ingredient such that
the meal's total calories, protein, and fiber hit the given targets
within tolerance.  Optionally adds a soft penalty for micronutrient
shortfall as a secondary objective.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from daily_chow.food_db import Food

# Scaling factor: nutrition coefficients are stored as per-100g floats.
# Multiply by SCALE/100 and round to get integer per-gram coefficients.
# SCALE=100 means coefficients are in "centi-units" (e.g. centi-kcal per gram).
SCALE = 100

# Higher precision scale for micronutrients (values like 0.05 mg/100g).
MICRO_SCALE = 10_000

# Normalization base: weight per nutrient = MICRO_NORM // target_scaled.
# Ensures 100% shortfall of any nutrient contributes ~MICRO_NORM to penalty.
MICRO_NORM = 100_000_000

# Percentage scale for minimax: 0 = 0.00%, 10_000 = 100.00%
PCT_SCALE = 10_000

# Priority constants for lexicographic objective ordering
PRIORITY_MICROS = "micros"
PRIORITY_TOTAL_WEIGHT = "total_weight"
DEFAULT_PRIORITIES = [PRIORITY_MICROS, PRIORITY_TOTAL_WEIGHT]


@dataclass(frozen=True, slots=True)
class Targets:
    meal_calories_kcal: int = 2780  # kcal (daily 3500 minus smoothie 720)
    meal_protein_g: int = 130  # g (daily 160 minus smoothie 30)
    meal_fiber_min_g: int = 26  # g (daily 40 minus smoothie 14)
    cal_tolerance: int = 50  # kcal
    protein_tolerance: int = 5  # g


@dataclass(frozen=True, slots=True)
class IngredientInput:
    key: int  # FDC ID
    food: Food
    min_g: int
    max_g: int


@dataclass(frozen=True, slots=True)
class SolvedIngredient:
    key: int  # FDC ID
    grams: int
    calories_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    fiber_g: float


@dataclass(frozen=True, slots=True)
class Solution:
    status: str  # "optimal", "feasible", "infeasible"
    ingredients: list[SolvedIngredient]
    meal_calories_kcal: float
    meal_protein_g: float
    meal_fat_g: float
    meal_carbs_g: float
    meal_fiber_g: float
    objective_value: float | None
    micro_totals: dict[str, float] = field(default_factory=dict)


def _scaled_coeff(per_100g: float) -> int:
    """Convert a per-100g nutrient value to an integer per-gram coefficient."""
    return round(per_100g * SCALE / 100)


def _micro_coeff(per_100g: float) -> int:
    """Convert a per-100g micronutrient value to an integer per-gram coefficient."""
    return round(per_100g * MICRO_SCALE / 100)


def solve(
    ingredients: list[IngredientInput],
    targets: Targets = Targets(),
    micro_targets: dict[str, float] | None = None,
    micro_uls: dict[str, float] | None = None,
    priorities: list[str] | None = None,
    solver_timeout_s: float = 5.0,
) -> Solution:
    """Build and solve the CP-SAT model.

    Args:
        ingredients: Enabled ingredients with their bounds.
        targets: Calorie/protein/fiber targets and tolerances.
        micro_targets: Nutrient key -> remaining DRI target (after smoothie).
            Only checked nutrients are included. None or empty disables micro opt.
        micro_uls: Nutrient key -> remaining UL (after smoothie).
            Hard constraint: total nutrient <= UL for each entry.
        priorities: Ordered list of objective priorities for lexicographic
            optimization. Valid values: "micros", "total_weight".
            Default: ["micros", "total_weight"].
        solver_timeout_s: Maximum solver time in seconds.

    Returns:
        Solution with per-ingredient grams and computed macros.
    """
    if priorities is None:
        priorities = list(DEFAULT_PRIORITIES)
    if not ingredients:
        return Solution(
            status="infeasible",
            ingredients=[],
            meal_calories_kcal=0,
            meal_protein_g=0,
            meal_fat_g=0,
            meal_carbs_g=0,
            meal_fiber_g=0,
            objective_value=None,
        )

    model = cp_model.CpModel()

    # ── Decision variables ────────────────────────────────────────────
    gram_vars: dict[int, cp_model.IntVar] = {}
    for ing in ingredients:
        gram_vars[ing.key] = model.new_int_var(ing.min_g, ing.max_g, str(ing.key))

    # ── Precompute scaled coefficients ────────────────────────────────
    cal_coeffs = {ing.key: _scaled_coeff(ing.food.calories_kcal_per_100g) for ing in ingredients}
    pro_coeffs = {ing.key: _scaled_coeff(ing.food.protein_g_per_100g) for ing in ingredients}
    fib_coeffs = {ing.key: _scaled_coeff(ing.food.fiber_g_per_100g) for ing in ingredients}

    # ── Linear expressions for totals (in scaled units) ───────────────
    total_cal = sum(cal_coeffs[ing.key] * gram_vars[ing.key] for ing in ingredients)
    total_pro = sum(pro_coeffs[ing.key] * gram_vars[ing.key] for ing in ingredients)
    total_fib = sum(fib_coeffs[ing.key] * gram_vars[ing.key] for ing in ingredients)

    # ── Calorie constraint: |total - target| <= tolerance ─────────────
    cal_target_scaled = targets.meal_calories_kcal * SCALE
    cal_tol_scaled = targets.cal_tolerance * SCALE

    cal_dev = model.new_int_var(-cal_tol_scaled, cal_tol_scaled, "cal_dev")
    model.add(total_cal - cal_target_scaled == cal_dev)

    # ── Protein constraint: |total - target| <= tolerance ─────────────
    pro_target_scaled = targets.meal_protein_g * SCALE
    pro_tol_scaled = targets.protein_tolerance * SCALE

    pro_dev = model.new_int_var(-pro_tol_scaled, pro_tol_scaled, "pro_dev")
    model.add(total_pro - pro_target_scaled == pro_dev)

    # ── Fiber constraint: total >= minimum ────────────────────────────
    fib_min_scaled = targets.meal_fiber_min_g * SCALE
    model.add(total_fib >= fib_min_scaled)

    # ── UL hard constraints ──────────────────────────────────────────
    # Precompute per-nutrient total expressions (micro-scaled) for reuse
    _nutrient_exprs: dict[str, cp_model.LinearExprT] = {}

    def _get_nutrient_expr(key: str) -> cp_model.LinearExprT:
        if key not in _nutrient_exprs:
            coeffs: dict[int, int] = {}
            for ing in ingredients:
                c = _micro_coeff(ing.food.micros.get(key, 0.0))
                if c > 0:
                    coeffs[ing.key] = c
            if coeffs:
                _nutrient_exprs[key] = sum(coeffs[k] * gram_vars[k] for k in coeffs)
            else:
                _nutrient_exprs[key] = 0
        return _nutrient_exprs[key]

    if micro_uls:
        for key, ul_val in micro_uls.items():
            ul_scaled = round(ul_val * MICRO_SCALE)
            if ul_scaled <= 0:
                continue
            model.add(_get_nutrient_expr(key) <= ul_scaled)

    # ── Micronutrient minimax objective ────────────────────────────────
    # Minimax: minimize the worst percentage shortfall across all checked
    # nutrients, with sum-of-shortfalls as a tiebreaker.
    worst_pct_var: cp_model.IntVar | None = None
    max_worst_pct = 0
    micro_penalty: cp_model.LinearExprT = 0
    max_micro_penalty = 0

    if micro_targets:
        pct_short_vars: list[cp_model.IntVar] = []
        shortfall_terms: list[cp_model.LinearExprT] = []
        for key, target_val in micro_targets.items():
            target_scaled = round(target_val * MICRO_SCALE)
            if target_scaled <= 0:
                continue

            total_nutrient = _get_nutrient_expr(key)

            # Shortfall variable (minimization pushes to max(0, target - total))
            shortfall = model.new_int_var(0, target_scaled, f"{key}_short")
            model.add(shortfall >= target_scaled - total_nutrient)

            # Percentage shortfall: pct_short in [0, PCT_SCALE]
            # Encodes: pct_short / PCT_SCALE >= shortfall / target_scaled
            # i.e.     pct_short * target_scaled >= shortfall * PCT_SCALE
            pct_short = model.new_int_var(0, PCT_SCALE, f"{key}_pct_short")
            model.add(pct_short * target_scaled >= shortfall * PCT_SCALE)
            pct_short_vars.append(pct_short)

            # Sum-of-shortfalls tiebreaker (same as before)
            weight = max(1, MICRO_NORM // target_scaled)
            shortfall_terms.append(shortfall * weight)
            max_micro_penalty += target_scaled * weight

        if pct_short_vars:
            worst_pct_var = model.new_int_var(0, PCT_SCALE, "worst_pct")
            for ps in pct_short_vars:
                model.add(worst_pct_var >= ps)
            max_worst_pct = PCT_SCALE

        if shortfall_terms:
            micro_penalty = shortfall_terms[0]
            for term in shortfall_terms[1:]:
                micro_penalty = micro_penalty + term

    # ── Objective ─────────────────────────────────────────────────────
    # Lexicographic optimization via user-specified priority order.
    # Implemented via weight hierarchy where each level's weight exceeds
    # the maximum possible contribution of all lower levels.
    max_total = sum(ing.max_g for ing in ingredients)
    total_grams = sum(gram_vars[k] for k in gram_vars)

    # Build terms list in priority order
    terms: list[tuple[cp_model.LinearExprT, int]] = []
    for p in priorities:
        if p == PRIORITY_MICROS:
            if worst_pct_var is not None and max_worst_pct > 0:
                terms.append((worst_pct_var, max_worst_pct))
            if max_micro_penalty > 0:
                terms.append((micro_penalty, max_micro_penalty))
        elif p == PRIORITY_TOTAL_WEIGHT:
            terms.append((total_grams, max_total))

    # Fallback: if no terms (e.g. no micros checked and total_weight not in list),
    # minimize total grams as a sensible default.
    if not terms:
        terms.append((total_grams, max_total))

    # Compute weights: w[-1]=1, w[i] = max[i+1] * w[i+1] + 1
    weights = [1] * len(terms)
    for i in range(len(terms) - 2, -1, -1):
        _, lower_max = terms[i + 1]
        weights[i] = lower_max * weights[i + 1] + 1

    final_obj: cp_model.LinearExprT = 0
    for (expr, _), w in zip(terms, weights):
        final_obj = final_obj + expr * w
    model.minimize(final_obj)

    # ── Solve ─────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = solver_timeout_s

    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return Solution(
            status="infeasible",
            ingredients=[],
            meal_calories_kcal=0,
            meal_protein_g=0,
            meal_fat_g=0,
            meal_carbs_g=0,
            meal_fiber_g=0,
            objective_value=None,
        )

    # ── Extract solution ──────────────────────────────────────────────
    solved: list[SolvedIngredient] = []
    total_cal_real = 0.0
    total_pro_real = 0.0
    total_fat_real = 0.0
    total_carb_real = 0.0
    total_fib_real = 0.0

    for ing in ingredients:
        grams = solver.value(gram_vars[ing.key])
        cal = grams * ing.food.calories_kcal_per_100g / 100
        pro = grams * ing.food.protein_g_per_100g / 100
        fat = grams * ing.food.fat_g_per_100g / 100
        carb = grams * ing.food.carbs_g_per_100g / 100
        fib = grams * ing.food.fiber_g_per_100g / 100
        total_cal_real += cal
        total_pro_real += pro
        total_fat_real += fat
        total_carb_real += carb
        total_fib_real += fib
        solved.append(SolvedIngredient(
            key=ing.key,
            grams=grams,
            calories_kcal=round(cal, 1),
            protein_g=round(pro, 1),
            fat_g=round(fat, 1),
            carbs_g=round(carb, 1),
            fiber_g=round(fib, 1),
        ))

    # ── Compute micronutrient totals (all tracked nutrients) ──────────
    micro_totals: dict[str, float] = {}
    for ing in ingredients:
        grams = solver.value(gram_vars[ing.key])
        for key, per_100g in ing.food.micros.items():
            micro_totals[key] = micro_totals.get(key, 0.0) + grams * per_100g / 100

    # Round micro totals
    micro_totals = {k: round(v, 2) for k, v in micro_totals.items()}

    status_str = "optimal" if status == cp_model.OPTIMAL else "feasible"

    return Solution(
        status=status_str,
        ingredients=solved,
        meal_calories_kcal=round(total_cal_real, 1),
        meal_protein_g=round(total_pro_real, 1),
        meal_fat_g=round(total_fat_real, 1),
        meal_carbs_g=round(total_carb_real, 1),
        meal_fiber_g=round(total_fib_real, 1),
        objective_value=solver.objective_value if solver.objective_value is not None else None,
        micro_totals=micro_totals,
    )
