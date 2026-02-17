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

# Percentage scale for minimax: 0 = 0.00%, 10_000 = 100.00%
PCT_SCALE = 10_000

# Priority constants for lexicographic objective ordering
PRIORITY_MICROS = "micros"
PRIORITY_MACRO_RATIO = "macro_ratio"
PRIORITY_INGREDIENT_DIVERSITY = "ingredient_diversity"
PRIORITY_TOTAL_WEIGHT = "total_weight"
DEFAULT_PRIORITIES = [PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_INGREDIENT_DIVERSITY, PRIORITY_TOTAL_WEIGHT]


@dataclass(frozen=True, slots=True)
class Targets:
    meal_calories_kcal: int = 2780  # kcal (daily 3500 minus smoothie 720)
    cal_tolerance: int = 50  # kcal


@dataclass(frozen=True, slots=True)
class MacroRatio:
    carb_pct: int = 50
    protein_pct: int = 25
    fat_pct: int = 25
    # Pinned meal macros (grams) — added as constants so the solver
    # optimizes the full-day ratio, not just the meal portion.
    pinned_carb_g: float = 0.0
    pinned_protein_g: float = 0.0
    pinned_fat_g: float = 0.0


@dataclass(frozen=True, slots=True)
class MacroConstraint:
    nutrient: str   # 'carbs', 'protein', 'fat', 'fiber'
    mode: str       # 'gte', 'lte', 'eq', 'none'
    grams: int      # target gram value (ignored when mode='none')
    hard: bool = True  # True = hard constraint, False = soft objective


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
    macro_ratio: MacroRatio | None = None,
    priorities: list[str] | None = None,
    solver_timeout_s: float = 5.0,
    macro_constraints: list[MacroConstraint] | None = None,
    micro_strategy: str = "depth",
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
    fat_coeffs = {ing.key: _scaled_coeff(ing.food.fat_g_per_100g) for ing in ingredients}
    carb_coeffs = {ing.key: _scaled_coeff(ing.food.carbs_g_per_100g) for ing in ingredients}

    # ── Linear expressions for totals (in scaled units) ───────────────
    total_cal = sum(cal_coeffs[ing.key] * gram_vars[ing.key] for ing in ingredients)
    total_pro = sum(pro_coeffs[ing.key] * gram_vars[ing.key] for ing in ingredients)
    total_fib = sum(fib_coeffs[ing.key] * gram_vars[ing.key] for ing in ingredients)
    total_fat = sum(fat_coeffs[ing.key] * gram_vars[ing.key] for ing in ingredients)
    total_carb = sum(carb_coeffs[ing.key] * gram_vars[ing.key] for ing in ingredients)

    # ── Calorie constraint: |total - target| <= tolerance ─────────────
    cal_target_scaled = targets.meal_calories_kcal * SCALE
    cal_tol_scaled = targets.cal_tolerance * SCALE

    cal_dev = model.new_int_var(-cal_tol_scaled, cal_tol_scaled, "cal_dev")
    model.add(total_cal - cal_target_scaled == cal_dev)

    # ── Macro constraints (protein, fat, carbs, fiber) ─────────────────
    macro_exprs = {
        "carbs": total_carb,
        "protein": total_pro,
        "fat": total_fat,
        "fiber": total_fib,
    }

    # Compute upper bound for any macro: sum of (max_g * scaled_coeff) over all
    # ingredients.  Used to bound loose deviation variables.
    macro_coeff_map = {
        "carbs": carb_coeffs,
        "protein": pro_coeffs,
        "fat": fat_coeffs,
        "fiber": fib_coeffs,
    }

    loose_dev_vars: list[cp_model.IntVar] = []
    max_loose_dev = 0

    if macro_constraints:
        for mc in macro_constraints:
            if mc.mode == "none":
                continue
            expr = macro_exprs[mc.nutrient]
            target_scaled = mc.grams * SCALE
            if mc.hard:
                if mc.mode == "gte":
                    model.add(expr >= target_scaled)
                elif mc.mode == "lte":
                    model.add(expr <= target_scaled)
                elif mc.mode == "eq":
                    model.add(expr >= target_scaled)
                    model.add(expr <= target_scaled)
            else:
                # Soft / loose constraint: penalize deviation as an objective.
                # Normalize to [0, PCT_SCALE] to prevent int64 overflow in
                # the lexicographic weight calculation.
                coeffs_for_nutrient = macro_coeff_map[mc.nutrient]
                max_possible = sum(
                    ing.max_g * coeffs_for_nutrient[ing.key]
                    for ing in ingredients
                )
                dev_bound = max(max_possible, target_scaled)
                name = f"loose_{mc.nutrient}_{mc.mode}"
                dev = model.new_int_var(0, dev_bound, name)

                if mc.mode == "gte":
                    # Penalize being below target: dev >= target - actual
                    model.add(dev >= target_scaled - expr)
                elif mc.mode == "lte":
                    # Penalize being above target: dev >= actual - target
                    model.add(dev >= expr - target_scaled)
                elif mc.mode == "eq":
                    # Penalize any deviation: dev >= |actual - target|
                    diff_var = model.new_int_var(
                        -dev_bound, dev_bound, f"{name}_diff"
                    )
                    model.add(diff_var == expr - target_scaled)
                    model.add_abs_equality(dev, diff_var)

                # Normalize deviation to [0, PCT_SCALE].
                # For gte: max deviation is target_scaled (when actual=0),
                # so normalize by target for full-range sensitivity.
                # For lte/eq: deviation can exceed target, so normalize by
                # dev_bound to keep pct_dev within [0, PCT_SCALE].
                norm_denom = target_scaled if mc.mode == "gte" else dev_bound
                norm_denom = max(norm_denom, 1)  # guard against zero target
                pct_dev = model.new_int_var(0, PCT_SCALE, f"{name}_pct")
                model.add(pct_dev * norm_denom >= dev * PCT_SCALE)

                loose_dev_vars.append(pct_dev)
                if PCT_SCALE > max_loose_dev:
                    max_loose_dev = PCT_SCALE

    # Minimax over loose deviations
    worst_loose_var: cp_model.IntVar | None = None
    max_worst_loose = 0

    if loose_dev_vars:
        worst_loose_var = model.new_int_var(0, max_loose_dev, "worst_loose")
        for dv in loose_dev_vars:
            model.add(worst_loose_var >= dv)
        max_worst_loose = max_loose_dev

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
    # nutrients, with sum-of-percentage-shortfalls as a tiebreaker.
    worst_pct_var: cp_model.IntVar | None = None
    max_worst_pct = 0
    micro_pct_sum: cp_model.LinearExprT = 0
    max_micro_pct_sum = 0

    # Compact percentage scale for micro objectives.  1% precision is
    # plenty for nutrition and keeps the lex weight chain within int64
    # even with UL proximity + coverage + sum + other priority levels.
    _MICRO_PCT = 100

    if micro_targets:
        pct_short_vars: list[cp_model.IntVar] = []
        for key, target_val in micro_targets.items():
            target_scaled = round(target_val * MICRO_SCALE)
            if target_scaled <= 0:
                continue

            total_nutrient = _get_nutrient_expr(key)

            # Shortfall variable (minimization pushes to max(0, target - total))
            shortfall = model.new_int_var(0, target_scaled, f"{key}_short")
            model.add(shortfall >= target_scaled - total_nutrient)

            # Percentage shortfall: pct_short in [0, _MICRO_PCT]
            # Encodes: pct_short / _MICRO_PCT >= shortfall / target_scaled
            # i.e.     pct_short * target_scaled >= shortfall * _MICRO_PCT
            pct_short = model.new_int_var(0, _MICRO_PCT, f"{key}_pct_short")
            model.add(pct_short * target_scaled >= shortfall * _MICRO_PCT)
            pct_short_vars.append(pct_short)

        if pct_short_vars:
            worst_pct_var = model.new_int_var(0, _MICRO_PCT, "worst_pct")
            for ps in pct_short_vars:
                model.add(worst_pct_var >= ps)
            max_worst_pct = _MICRO_PCT

            # Sum-of-percentage-shortfalls: already at compact scale,
            # so just sum the pct_short_vars directly.
            micro_pct_sum = pct_short_vars[0]
            for ps in pct_short_vars[1:]:
                micro_pct_sum = micro_pct_sum + ps
            max_micro_pct_sum = len(pct_short_vars) * _MICRO_PCT

    # ── UL proximity penalty ────────────────────────────────────────────
    # For nutrients with a UL, penalize accumulation past DRI toward UL.
    # This is a minimax: minimize the worst (excess / headroom) ratio
    # across all nutrients that have both a DRI target and a UL.
    # Placed as the first sub-term within the micros lex level so the
    # solver prioritizes UL avoidance over coverage optimization.
    _UL_PROX_SCALE = 100
    worst_ul_prox_var: cp_model.IntVar | None = None
    max_worst_ul_prox = 0

    if micro_targets and micro_uls:
        ul_prox_vars: list[cp_model.IntVar] = []
        for key, target_val in micro_targets.items():
            ul_val = micro_uls.get(key)
            if ul_val is None:
                continue
            target_scaled = round(target_val * MICRO_SCALE)
            ul_scaled = round(ul_val * MICRO_SCALE)
            headroom = ul_scaled - target_scaled
            if headroom <= 0:
                continue

            total_nutrient = _get_nutrient_expr(key)

            # excess = max(0, total - target)
            excess = model.new_int_var(0, headroom, f"{key}_ul_excess")
            model.add(excess >= total_nutrient - target_scaled)

            # ul_prox / _UL_PROX_SCALE >= excess / headroom
            # => ul_prox * headroom >= excess * _UL_PROX_SCALE
            ul_prox = model.new_int_var(0, _UL_PROX_SCALE, f"{key}_ul_prox")
            model.add(ul_prox * headroom >= excess * _UL_PROX_SCALE)
            ul_prox_vars.append(ul_prox)

        if ul_prox_vars:
            worst_ul_prox_var = model.new_int_var(0, _UL_PROX_SCALE, "worst_ul_prox")
            for up in ul_prox_vars:
                model.add(worst_ul_prox_var >= up)
            max_worst_ul_prox = _UL_PROX_SCALE

    # ── Macro ratio minimax objective ──────────────────────────────────
    macro_worst_var: cp_model.IntVar | None = None
    max_macro_worst = 0

    if macro_ratio is not None:
        # Include pinned meal macros as constants so the solver optimizes
        # the full-day ratio (meal + pinned), not just the meal portion.
        pinned_carb_cal = round(macro_ratio.pinned_carb_g * 4 * SCALE)
        pinned_pro_cal = round(macro_ratio.pinned_protein_g * 4 * SCALE)
        pinned_fat_cal = round(macro_ratio.pinned_fat_g * 9 * SCALE)

        day_carb_cal = total_carb * 4 + pinned_carb_cal
        day_pro_cal = total_pro * 4 + pinned_pro_cal
        day_fat_cal = total_fat * 9 + pinned_fat_cal
        day_total_cal = day_carb_cal + day_pro_cal + day_fat_cal

        max_cal = sum(
            (ing.max_g * _scaled_coeff(ing.food.carbs_g_per_100g) * 4
             + ing.max_g * _scaled_coeff(ing.food.protein_g_per_100g) * 4
             + ing.max_g * _scaled_coeff(ing.food.fat_g_per_100g) * 9)
            for ing in ingredients
        ) + pinned_carb_cal + pinned_pro_cal + pinned_fat_cal

        # Use total daily calorie target as a constant denominator for
        # percentage deviation.  Pinned cals are constant and meal cals are
        # tightly bounded by the band constraint, so this is an excellent
        # approximation that keeps the model fully linear.
        pinned_cal = pinned_carb_cal + pinned_pro_cal + pinned_fat_cal
        cal_denom = targets.meal_calories_kcal * SCALE + pinned_cal

        # Exclude macros that have any active constraint from ratio
        # optimization — the constraint already governs that macro.
        ratio_excluded: set[str] = set()
        if macro_constraints:
            for mc in macro_constraints:
                if mc.mode != "none":
                    ratio_excluded.add(mc.nutrient)

        _ratio_name_to_nutrient = {"carb": "carbs", "pro": "protein", "fat": "fat"}

        macro_dev_vars: list[cp_model.IntVar] = []
        for name, cal_expr, target_pct in [
            ("carb", day_carb_cal, macro_ratio.carb_pct),
            ("pro", day_pro_cal, macro_ratio.protein_pct),
            ("fat", day_fat_cal, macro_ratio.fat_pct),
        ]:
            if _ratio_name_to_nutrient[name] in ratio_excluded:
                continue
            diff_expr = cal_expr * 100 - day_total_cal * target_pct
            bound = max_cal * 100
            diff_var = model.new_int_var(-bound, bound, f"macro_{name}_diff")
            model.add(diff_var == diff_expr)

            abs_diff = model.new_int_var(0, bound, f"macro_{name}_abs")
            model.add_abs_equality(abs_diff, diff_var)

            # diff_expr = total_cal * (actual_pct - target_pct), so
            # abs_diff = total_cal * |deviation_in_pp|.
            # We want pct_dev in [0, PCT_SCALE] where PCT_SCALE = 100pp.
            # pct_dev / PCT_SCALE >= |deviation_pp| / 100
            #   = abs_diff / (total_cal * 100)
            #   ≈ abs_diff / (cal_denom * 100)
            # => pct_dev * cal_denom * 100 >= abs_diff * PCT_SCALE
            pct_dev = model.new_int_var(0, PCT_SCALE, f"macro_{name}_pctdev")
            model.add(pct_dev * cal_denom * 100 >= abs_diff * PCT_SCALE)
            macro_dev_vars.append(pct_dev)

        if macro_dev_vars:
            macro_worst_var = model.new_int_var(0, PCT_SCALE, "macro_worst")
            for dv in macro_dev_vars:
                model.add(macro_worst_var >= dv)
            max_macro_worst = PCT_SCALE

    # ── Objective ─────────────────────────────────────────────────────
    # Lexicographic optimization via user-specified priority order.
    # Implemented via weight hierarchy where each level's weight exceeds
    # the maximum possible contribution of all lower levels.
    max_total = sum(ing.max_g for ing in ingredients)
    total_grams = sum(gram_vars[k] for k in gram_vars)

    # Combine macro ratio and loose deviations into a single minimax
    # variable to avoid adding extra terms to the lex weight chain (which
    # can cause int64 overflow with many objective tiers).
    combined_macro_var: cp_model.IntVar | None = None
    max_combined_macro = 0

    macro_pieces = []
    if macro_worst_var is not None and max_macro_worst > 0:
        macro_pieces.append((macro_worst_var, max_macro_worst))
    if worst_loose_var is not None and max_worst_loose > 0:
        macro_pieces.append((worst_loose_var, max_worst_loose))

    if len(macro_pieces) == 1:
        combined_macro_var = macro_pieces[0][0]
        max_combined_macro = macro_pieces[0][1]
    elif len(macro_pieces) > 1:
        max_combined_macro = max(m for _, m in macro_pieces)
        combined_macro_var = model.new_int_var(0, max_combined_macro, "combined_macro")
        for var, _ in macro_pieces:
            model.add(combined_macro_var >= var)

    # ── Ingredient diversity (minimax) ───────────────────────────────
    # Minimize the maximum gram amount across all ingredients.
    # This directly prevents any single ingredient from dominating
    # and is purely linear (no multiplication constraints).
    diversity_var: cp_model.IntVar | None = None
    max_diversity = 0
    if PRIORITY_INGREDIENT_DIVERSITY in priorities:
        max_possible = max(ing.max_g for ing in ingredients)
        diversity_var = model.new_int_var(0, max_possible, "max_gram")
        for ing in ingredients:
            model.add(diversity_var >= gram_vars[ing.key])
        max_diversity = max_possible

    # Build terms list in priority order.
    # Diversity and total_weight are independent lex levels so the user
    # can reorder them freely without one leaking influence into the other.
    # The micro_pct_sum tiebreaker uses a compact scale (above) to keep
    # the lex weight chain within int64 even with many priority levels.
    terms: list[tuple[cp_model.LinearExprT, int]] = []
    for p in priorities:
        if p == PRIORITY_MICROS:
            # UL avoidance first — minimize worst proximity to UL
            if worst_ul_prox_var is not None and max_worst_ul_prox > 0:
                terms.append((worst_ul_prox_var, max_worst_ul_prox))
            # "depth" = minimax primary, sum tiebreaker (best worst-case)
            # "breadth" = sum primary, minimax tiebreaker (best overall coverage)
            if micro_strategy == "breadth":
                if max_micro_pct_sum > 0:
                    terms.append((micro_pct_sum, max_micro_pct_sum))
                if worst_pct_var is not None and max_worst_pct > 0:
                    terms.append((worst_pct_var, max_worst_pct))
            else:
                if worst_pct_var is not None and max_worst_pct > 0:
                    terms.append((worst_pct_var, max_worst_pct))
                if max_micro_pct_sum > 0:
                    terms.append((micro_pct_sum, max_micro_pct_sum))
        elif p == PRIORITY_MACRO_RATIO:
            if combined_macro_var is not None and max_combined_macro > 0:
                terms.append((combined_macro_var, max_combined_macro))
        elif p == PRIORITY_INGREDIENT_DIVERSITY:
            if diversity_var is not None and max_diversity > 0:
                terms.append((diversity_var, max_diversity))
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

    # Verify the weighted objective fits in int64 to prevent silent corruption
    max_obj = sum(max_val * w for (_, max_val), w in zip(terms, weights))
    assert max_obj < 2**62, (
        f"Lexicographic objective would overflow int64: {max_obj} >= 2^62. "
        f"Reduce ingredient count/max_g or number of micro targets."
    )

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
