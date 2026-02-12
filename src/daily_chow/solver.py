"""CP-SAT constraint solver for daily meal macro optimization.

Finds integer gram quantities for each enabled ingredient such that
the meal's total calories, protein, and fiber hit the given targets
within tolerance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ortools.sat.python import cp_model

from daily_chow.food_db import Food

# Scaling factor: nutrition coefficients are stored as per-100g floats.
# Multiply by SCALE/100 and round to get integer per-gram coefficients.
# SCALE=100 means coefficients are in "centi-units" (e.g. centi-kcal per gram).
SCALE = 100


class Objective(Enum):
    MINIMIZE_OIL = "minimize_oil"
    MINIMIZE_RICE_DEVIATION = "minimize_rice_deviation"
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
    key: str
    food: Food
    min_g: int
    max_g: int


@dataclass(frozen=True, slots=True)
class SolvedIngredient:
    key: str
    grams: int
    calories: float
    protein: float
    fiber: float


@dataclass(frozen=True, slots=True)
class Solution:
    status: str  # "optimal", "feasible", "infeasible"
    ingredients: list[SolvedIngredient]
    meal_calories: float
    meal_protein: float
    meal_fiber: float
    objective_value: float | None


def _scaled_coeff(per_100g: float) -> int:
    """Convert a per-100g nutrient value to an integer per-gram coefficient."""
    return round(per_100g * SCALE / 100)


def solve(
    ingredients: list[IngredientInput],
    targets: Targets = Targets(),
    objective: Objective = Objective.MINIMIZE_OIL,
    preferred_rice_g: int = 200,
    solver_timeout_s: float = 5.0,
) -> Solution:
    """Build and solve the CP-SAT model.

    Args:
        ingredients: Enabled ingredients with their bounds.
        targets: Calorie/protein/fiber targets and tolerances.
        objective: Which objective function to use.
        preferred_rice_g: For MINIMIZE_RICE_DEVIATION, the preferred amount.
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
            meal_fiber=0,
            objective_value=None,
        )

    model = cp_model.CpModel()

    # ── Decision variables ────────────────────────────────────────────
    gram_vars: dict[str, cp_model.IntVar] = {}
    for ing in ingredients:
        gram_vars[ing.key] = model.new_int_var(ing.min_g, ing.max_g, ing.key)

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

    # ── Objective ─────────────────────────────────────────────────────
    if objective == Objective.MINIMIZE_OIL:
        oil_keys = [
            ing.key
            for ing in ingredients
            if ing.food.category == "oils_fats"
        ]
        if oil_keys:
            model.minimize(sum(gram_vars[k] for k in oil_keys))
        else:
            # No oil in model — minimize total calories deviation instead
            abs_cal_dev = model.new_int_var(0, cal_tol_scaled, "abs_cal_dev")
            model.add_abs_equality(abs_cal_dev, cal_dev)
            model.minimize(abs_cal_dev)

    elif objective == Objective.MINIMIZE_RICE_DEVIATION:
        grain_keys = [
            ing.key
            for ing in ingredients
            if ing.food.category == "grains"
        ]
        if grain_keys:
            # Minimize sum of absolute deviations from preferred amount
            abs_devs = []
            for k in grain_keys:
                max_bound = next(i.max_g for i in ingredients if i.key == k)
                dev = model.new_int_var(0, max(max_bound, preferred_rice_g), f"{k}_dev")
                diff = model.new_int_var(
                    -max(max_bound, preferred_rice_g),
                    max(max_bound, preferred_rice_g),
                    f"{k}_diff",
                )
                model.add(diff == gram_vars[k] - preferred_rice_g)
                model.add_abs_equality(dev, diff)
                abs_devs.append(dev)
            model.minimize(sum(abs_devs))
        else:
            abs_cal_dev = model.new_int_var(0, cal_tol_scaled, "abs_cal_dev")
            model.add_abs_equality(abs_cal_dev, cal_dev)
            model.minimize(abs_cal_dev)

    elif objective == Objective.MINIMIZE_TOTAL_GRAMS:
        model.minimize(sum(gram_vars[k] for k in gram_vars))

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
            meal_fiber=0,
            objective_value=None,
        )

    # ── Extract solution ──────────────────────────────────────────────
    solved: list[SolvedIngredient] = []
    total_cal_real = 0.0
    total_pro_real = 0.0
    total_fib_real = 0.0

    for ing in ingredients:
        grams = solver.value(gram_vars[ing.key])
        cal = grams * ing.food.cal_per_100g / 100
        pro = grams * ing.food.protein_per_100g / 100
        fib = grams * ing.food.fiber_per_100g / 100
        total_cal_real += cal
        total_pro_real += pro
        total_fib_real += fib
        solved.append(SolvedIngredient(
            key=ing.key,
            grams=grams,
            calories=round(cal, 1),
            protein=round(pro, 1),
            fiber=round(fib, 1),
        ))

    status_str = "optimal" if status == cp_model.OPTIMAL else "feasible"

    return Solution(
        status=status_str,
        ingredients=solved,
        meal_calories=round(total_cal_real, 1),
        meal_protein=round(total_pro_real, 1),
        meal_fiber=round(total_fib_real, 1),
        objective_value=solver.objective_value if solver.objective_value is not None else None,
    )
