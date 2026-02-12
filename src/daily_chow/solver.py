"""CP-SAT constraint solver for daily meal macro optimization.

Finds integer gram quantities for each enabled ingredient such that
the meal's total calories, protein, and fiber hit the given targets
within tolerance.  Optionally adds a soft penalty for micronutrient
shortfall as a secondary objective.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

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


class Objective(Enum):
    MINIMIZE_OIL = "minimize_oil"
    MINIMIZE_TOTAL_GRAMS = "minimize_total_grams"


@dataclass(frozen=True, slots=True)
class Targets:
    meal_calories: int = 2780  # kcal (daily 3500 minus smoothie 720)
    meal_protein: int = 130  # g (daily 160 minus smoothie 30)
    meal_fiber_min: int = 26  # g (daily 40 minus smoothie 14)
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
    calories: float
    protein: float
    fat: float
    carbs: float
    fiber: float


@dataclass(frozen=True, slots=True)
class Solution:
    status: str  # "optimal", "feasible", "infeasible"
    ingredients: list[SolvedIngredient]
    meal_calories: float
    meal_protein: float
    meal_fat: float
    meal_carbs: float
    meal_fiber: float
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
    objective: Objective = Objective.MINIMIZE_OIL,
    micro_targets: dict[str, float] | None = None,
    solver_timeout_s: float = 5.0,
) -> Solution:
    """Build and solve the CP-SAT model.

    Args:
        ingredients: Enabled ingredients with their bounds.
        targets: Calorie/protein/fiber targets and tolerances.
        objective: Which objective function to use.
        micro_targets: Nutrient key -> remaining DRI target (after smoothie).
            Only checked nutrients are included. None or empty disables micro opt.
        solver_timeout_s: Maximum solver time in seconds.

    Returns:
        Solution with per-ingredient grams and computed macros.
    """
    if not ingredients:
        return Solution(
            status="infeasible",
            ingredients=[],
            meal_calories=0,
            meal_protein=0,
            meal_fat=0,
            meal_carbs=0,
            meal_fiber=0,
            objective_value=None,
        )

    model = cp_model.CpModel()

    # ── Decision variables ────────────────────────────────────────────
    gram_vars: dict[int, cp_model.IntVar] = {}
    for ing in ingredients:
        gram_vars[ing.key] = model.new_int_var(ing.min_g, ing.max_g, str(ing.key))

    # ── Precompute scaled coefficients ────────────────────────────────
    cal_coeffs = {ing.key: _scaled_coeff(ing.food.cal_per_100g) for ing in ingredients}
    pro_coeffs = {ing.key: _scaled_coeff(ing.food.protein_per_100g) for ing in ingredients}
    fib_coeffs = {ing.key: _scaled_coeff(ing.food.fiber_per_100g) for ing in ingredients}

    # ── Linear expressions for totals (in scaled units) ───────────────
    total_cal = sum(cal_coeffs[ing.key] * gram_vars[ing.key] for ing in ingredients)
    total_pro = sum(pro_coeffs[ing.key] * gram_vars[ing.key] for ing in ingredients)
    total_fib = sum(fib_coeffs[ing.key] * gram_vars[ing.key] for ing in ingredients)

    # ── Calorie constraint: |total - target| <= tolerance ─────────────
    cal_target_scaled = targets.meal_calories * SCALE
    cal_tol_scaled = targets.cal_tolerance * SCALE

    cal_dev = model.new_int_var(-cal_tol_scaled, cal_tol_scaled, "cal_dev")
    model.add(total_cal - cal_target_scaled == cal_dev)

    # ── Protein constraint: |total - target| <= tolerance ─────────────
    pro_target_scaled = targets.meal_protein * SCALE
    pro_tol_scaled = targets.protein_tolerance * SCALE

    pro_dev = model.new_int_var(-pro_tol_scaled, pro_tol_scaled, "pro_dev")
    model.add(total_pro - pro_target_scaled == pro_dev)

    # ── Fiber constraint: total >= minimum ────────────────────────────
    fib_min_scaled = targets.meal_fiber_min * SCALE
    model.add(total_fib >= fib_min_scaled)

    # ── Micronutrient soft penalty ────────────────────────────────────
    # For each checked nutrient, compute shortfall = max(0, target - total).
    # Since we're minimizing, the solver will set shortfall to the tightest
    # lower bound, which is exactly max(0, target - total).
    micro_penalty: cp_model.LinearExprT = 0
    max_micro_penalty = 0

    if micro_targets:
        shortfall_terms: list[cp_model.LinearExprT] = []
        for key, target_val in micro_targets.items():
            target_scaled = round(target_val * MICRO_SCALE)
            if target_scaled <= 0:
                continue

            # Per-gram coefficients for this nutrient
            coeffs: dict[str, int] = {}
            for ing in ingredients:
                c = _micro_coeff(ing.food.micros.get(key, 0.0))
                if c > 0:
                    coeffs[ing.key] = c

            # Total nutrient from the meal (in micro-scaled units)
            total_nutrient: cp_model.LinearExprT = 0
            if coeffs:
                total_nutrient = sum(
                    coeffs[k] * gram_vars[k] for k in coeffs
                )

            # Shortfall variable (minimization pushes this to max(0, target - total))
            shortfall = model.new_int_var(0, target_scaled, f"{key}_short")
            model.add(shortfall >= target_scaled - total_nutrient)

            # Normalize: weight so 100% shortfall ≈ MICRO_NORM for all nutrients
            weight = max(1, MICRO_NORM // target_scaled)
            shortfall_terms.append(shortfall * weight)
            max_micro_penalty += target_scaled * weight

        if shortfall_terms:
            micro_penalty = shortfall_terms[0]
            for term in shortfall_terms[1:]:
                micro_penalty = micro_penalty + term

    # ── Objective ─────────────────────────────────────────────────────
    # Three-level lexicographic: primary >> micro >> tiebreaker.
    # Implemented via weight hierarchy where each level's weight exceeds
    # the maximum possible contribution of all lower levels.
    max_total = sum(ing.max_g for ing in ingredients)
    total_grams = sum(gram_vars[k] for k in gram_vars)

    # Compute primary expression based on objective type
    if objective == Objective.MINIMIZE_OIL:
        oil_keys = [
            ing.key for ing in ingredients if ing.food.category == "Fats and Oils"
        ]
        if oil_keys:
            primary_expr: cp_model.LinearExprT = sum(
                gram_vars[k] for k in oil_keys
            )
            max_primary = sum(
                ing.max_g for ing in ingredients if ing.key in set(oil_keys)
            )
        else:
            abs_cal_dev = model.new_int_var(0, cal_tol_scaled, "abs_cal_dev")
            model.add_abs_equality(abs_cal_dev, cal_dev)
            primary_expr = abs_cal_dev
            max_primary = cal_tol_scaled

    else:  # MINIMIZE_TOTAL_GRAMS
        primary_expr = total_grams
        max_primary = max_total

    # Build lexicographic objective: primary >> secondary
    # When micro optimization is active, blend micro shortfall with total
    # grams so the solver balances nutrient coverage against meal size.
    # Filling one full nutrient gap is worth ~200g of extra food.
    GRAMS_PER_GAP = 200
    terms: list[tuple[cp_model.LinearExprT, int]] = [(primary_expr, max_primary)]

    if max_micro_penalty > 0:
        grams_cost = max(1, MICRO_NORM // GRAMS_PER_GAP)
        blended = micro_penalty + total_grams * grams_cost
        max_blended = max_micro_penalty + max_total * grams_cost
        terms.append((blended, max_blended))
    elif objective != Objective.MINIMIZE_TOTAL_GRAMS:
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
            meal_calories=0,
            meal_protein=0,
            meal_fat=0,
            meal_carbs=0,
            meal_fiber=0,
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
        cal = grams * ing.food.cal_per_100g / 100
        pro = grams * ing.food.protein_per_100g / 100
        fat = grams * ing.food.fat_per_100g / 100
        carb = grams * ing.food.carbs_per_100g / 100
        fib = grams * ing.food.fiber_per_100g / 100
        total_cal_real += cal
        total_pro_real += pro
        total_fat_real += fat
        total_carb_real += carb
        total_fib_real += fib
        solved.append(SolvedIngredient(
            key=ing.key,
            grams=grams,
            calories=round(cal, 1),
            protein=round(pro, 1),
            fat=round(fat, 1),
            carbs=round(carb, 1),
            fiber=round(fib, 1),
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
        meal_calories=round(total_cal_real, 1),
        meal_protein=round(total_pro_real, 1),
        meal_fat=round(total_fat_real, 1),
        meal_carbs=round(total_carb_real, 1),
        meal_fiber=round(total_fib_real, 1),
        objective_value=solver.objective_value if solver.objective_value is not None else None,
        micro_totals=micro_totals,
    )
