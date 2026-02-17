"""Tests for the CP-SAT meal solver."""

from daily_chow.food_db import load_foods
from daily_chow.solver import (
    IngredientInput,
    MacroConstraint,
    MacroRatio,
    PRIORITY_INGREDIENT_DIVERSITY,
    PRIORITY_MACRO_RATIO,
    PRIORITY_MICROS,
    PRIORITY_TOTAL_WEIGHT,
    Solution,
    Targets,
    solve,
)

FOODS = load_foods()


def _find_food(name_substr: str) -> int:
    """Find a food FDC ID by name substring."""
    for fdc_id, food in FOODS.items():
        if name_substr.lower() in food.name.lower():
            return fdc_id
    raise KeyError(f"No food matching '{name_substr}'")


def _default_ingredients() -> list[IngredientInput]:
    """A representative set of ingredients for testing."""
    specs = [
        ("White Rice", 0, 400),
        ("Broccoli", 200, 400),
        ("Carrots", 150, 300),
        ("Zucchini", 250, 500),
        ("Avocado Oil", 0, 100),
        ("Black Beans", 150, 400),
        ("Split Peas", 60, 150),
        ("Ground Beef", 0, 1000),
        ("Chicken Thigh", 0, 1000),
    ]
    return [
        IngredientInput(_find_food(name), FOODS[_find_food(name)], min_g, max_g)
        for name, min_g, max_g in specs
    ]


def _grams_for(sol: Solution, name_substr: str) -> int:
    fdc_id = _find_food(name_substr)
    for ing in sol.ingredients:
        if ing.key == fdc_id:
            return ing.grams
    raise KeyError(f"Ingredient {name_substr} (FDC {fdc_id}) not in solution")


class TestSolverFeasibility:
    def test_default_ingredients_feasible(self):
        sol = solve(_default_ingredients())
        assert sol.status in ("optimal", "feasible")

    def test_empty_ingredients_infeasible(self):
        sol = solve([])
        assert sol.status == "infeasible"


class TestSolverConstraints:
    def test_calories_within_tolerance(self):
        targets = Targets()
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        assert abs(sol.meal_calories_kcal - targets.meal_calories_kcal) <= targets.cal_tolerance + 1

    def test_protein_meets_floor(self):
        constraints = [MacroConstraint("protein", "gte", 130, hard=True)]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_protein_g >= 130 - 1

    def test_fiber_meets_minimum(self):
        constraints = [MacroConstraint("fiber", "gte", 26, hard=True)]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_fiber_g >= 26 - 1


class TestSolverObjectives:
    def test_priority_ordering_affects_solution(self):
        """Micros-first vs weight-first should produce different solutions
        when there's slack for the solver to trade off between them."""
        ingredients = _default_ingredients()
        micro_targets = {"iron_mg": 4.9, "calcium_mg": 500.0, "magnesium_mg": 200.0}

        sol_micros_first = solve(
            ingredients,
            micro_targets=micro_targets,
            priorities=[PRIORITY_MICROS, PRIORITY_TOTAL_WEIGHT],
        )
        sol_weight_first = solve(
            ingredients,
            micro_targets=micro_targets,
            priorities=[PRIORITY_TOTAL_WEIGHT, PRIORITY_MICROS],
        )
        assert sol_micros_first.status in ("optimal", "feasible")
        assert sol_weight_first.status in ("optimal", "feasible")

        # When micros are top priority, total grams should be >= weight-first
        total_micros_first = sum(i.grams for i in sol_micros_first.ingredients)
        total_weight_first = sum(i.grams for i in sol_weight_first.ingredients)
        assert total_weight_first <= total_micros_first


class TestMicroOptimization:
    def test_micro_targets_feasible(self):
        sol = solve(_default_ingredients(), micro_targets={"iron_mg": 4.9})
        assert sol.status in ("optimal", "feasible")

    def test_micro_totals_populated(self):
        sol = solve(_default_ingredients())
        assert sol.status in ("optimal", "feasible")
        assert len(sol.micro_totals) > 0
        assert "calcium_mg" in sol.micro_totals

    def test_minimax_distributes_shortfall(self):
        """Minimax should distribute coverage across nutrients rather than
        satisfying some fully while leaving others at 0%."""
        # Use targets that can't all be 100% satisfied — forces tradeoff
        sol = solve(
            _default_ingredients(),
            micro_targets={
                "calcium_mg": 800.0,
                "iron_mg": 10.0,
                "magnesium_mg": 500.0,
                "vitamin_c_mg": 200.0,
            },
        )
        assert sol.status in ("optimal", "feasible")
        # Each nutrient should get some coverage (none near 0%)
        for key, target in [("calcium_mg", 800.0), ("iron_mg", 10.0),
                            ("magnesium_mg", 500.0), ("vitamin_c_mg", 200.0)]:
            total = sol.micro_totals.get(key, 0.0)
            pct = total / target * 100
            assert pct > 5, f"{key} got only {pct:.1f}% — minimax should prevent deep gaps"

    def test_ul_prevents_excess(self):
        """A tight UL on iron should cap the solver's iron intake."""
        # First solve without UL to find unconstrained iron
        sol_free = solve(
            _default_ingredients(),
            micro_targets={"iron_mg": 10.0},
        )
        assert sol_free.status in ("optimal", "feasible")
        free_iron = sol_free.micro_totals.get("iron_mg", 0.0)

        # Set UL midway between unconstrained result and what minimums force
        # (min-grams alone give ~12.8 mg, unconstrained ~18.6 mg)
        iron_ul = free_iron * 0.85
        sol = solve(
            _default_ingredients(),
            micro_targets={"iron_mg": 10.0},
            micro_uls={"iron_mg": iron_ul},
        )
        assert sol.status in ("optimal", "feasible")
        iron_total = sol.micro_totals.get("iron_mg", 0.0)
        # Allow small floating-point tolerance from integer rounding
        assert iron_total <= iron_ul + 0.1, (
            f"Iron {iron_total:.2f} exceeded UL {iron_ul}"
        )
        # Confirm the UL actually constrained the result
        assert iron_total < free_iron, (
            f"UL should have reduced iron from {free_iron:.2f}"
        )

    def test_ul_does_not_break_feasibility(self):
        """A loose UL should not prevent finding a solution."""
        sol = solve(
            _default_ingredients(),
            micro_targets={"iron_mg": 4.0, "calcium_mg": 500.0},
            micro_uls={"iron_mg": 45.0, "calcium_mg": 2500.0},
        )
        assert sol.status in ("optimal", "feasible")


class TestProteinFloor:
    def test_protein_floor_met(self):
        constraints = [MacroConstraint("protein", "gte", 130, hard=True)]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_protein_g >= 130 - 1

    def test_protein_can_exceed_floor(self):
        constraints = [MacroConstraint("protein", "gte", 80, hard=True)]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_protein_g >= 80 - 1


class TestMacroRatioObjective:
    def test_macro_ratio_feasible(self):
        ratio = MacroRatio(carb_pct=50, protein_pct=25, fat_pct=25)
        sol = solve(
            _default_ingredients(),
            macro_ratio=ratio,
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol.status in ("optimal", "feasible")

    def test_macro_ratio_steers_solution(self):
        high_fat = MacroRatio(carb_pct=30, protein_pct=20, fat_pct=50)
        low_fat = MacroRatio(carb_pct=60, protein_pct=25, fat_pct=15)
        sol_hf = solve(
            _default_ingredients(),
            macro_ratio=high_fat,
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        sol_lf = solve(
            _default_ingredients(),
            macro_ratio=low_fat,
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol_hf.status in ("optimal", "feasible")
        assert sol_lf.status in ("optimal", "feasible")
        assert sol_hf.meal_fat_g > sol_lf.meal_fat_g

    def test_macro_ratio_priority_ordering(self):
        ratio = MacroRatio(carb_pct=50, protein_pct=25, fat_pct=25)
        sol = solve(
            _default_ingredients(),
            macro_ratio=ratio,
            priorities=[PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
            micro_targets={"iron_mg": 4.9},
        )
        assert sol.status in ("optimal", "feasible")


class TestMacroConstraints:
    def test_hard_gte_protein(self):
        """Hard >= should enforce minimum protein."""
        constraints = [MacroConstraint("protein", "gte", 130, hard=True)]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_protein_g >= 130 - 1

    def test_hard_lte_protein(self):
        """Hard <= should cap protein."""
        constraints = [
            MacroConstraint("protein", "gte", 60, hard=True),
            MacroConstraint("protein", "lte", 140, hard=True),
        ]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_protein_g <= 140 + 1

    def test_hard_eq_fat(self):
        """Hard = should fix fat within +/-2g (integer rounding tolerance)."""
        constraints = [MacroConstraint("fat", "eq", 80, hard=True)]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")
        assert abs(sol.meal_fat_g - 80) <= 2

    def test_hard_lte_fiber(self):
        """Hard <= should cap fiber."""
        # Ingredient minimums force ~30g fiber, so cap at 40g
        constraints = [MacroConstraint("fiber", "lte", 40, hard=True)]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_fiber_g <= 40 + 1

    def test_none_mode_no_constraint(self):
        """Mode 'none' should not add any constraint."""
        constraints = [MacroConstraint("protein", "none", 0, hard=True)]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")

    def test_backward_compat_no_constraints(self):
        """Solve still works with empty macro_constraints."""
        sol = solve(_default_ingredients())
        assert sol.status in ("optimal", "feasible")


class TestLooseConstraints:
    def test_loose_lte_prefers_lower(self):
        """Loose <= should push protein below unconstrained baseline.

        Unconstrained baseline is ~102g protein.  A loose lte target of 70g
        should cause the solver to actively reduce protein even though the
        hard version of that constraint is infeasible.
        """
        constraints_loose = [
            MacroConstraint("protein", "lte", 70, hard=False),
        ]
        sol_loose = solve(
            _default_ingredients(),
            macro_constraints=constraints_loose,
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        sol_none = solve(
            _default_ingredients(),
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol_loose.status in ("optimal", "feasible")
        assert sol_none.status in ("optimal", "feasible")
        # Loose cap must actively reduce protein vs unconstrained
        assert sol_loose.meal_protein_g < sol_none.meal_protein_g - 1, (
            f"Loose lte should reduce protein: got {sol_loose.meal_protein_g}g "
            f"vs unconstrained {sol_none.meal_protein_g}g"
        )

    def test_loose_gte_prefers_higher(self):
        """Loose >= should push fiber above unconstrained baseline.

        Unconstrained baseline is ~50.8g fiber.  A loose gte target of 80g
        should cause the solver to actively increase fiber.
        """
        constraints_loose = [
            MacroConstraint("fiber", "gte", 80, hard=False),
        ]
        sol_loose = solve(
            _default_ingredients(),
            macro_constraints=constraints_loose,
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        sol_none = solve(
            _default_ingredients(),
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol_loose.status in ("optimal", "feasible")
        assert sol_none.status in ("optimal", "feasible")
        # Loose floor must actively increase fiber vs unconstrained
        assert sol_loose.meal_fiber_g > sol_none.meal_fiber_g + 1, (
            f"Loose gte should increase fiber: got {sol_loose.meal_fiber_g}g "
            f"vs unconstrained {sol_none.meal_fiber_g}g"
        )

    def test_loose_does_not_cause_infeasibility(self):
        """Loose constraint with impossible value should still find a solution."""
        constraints = [
            MacroConstraint("protein", "lte", 1, hard=False),  # impossibly low
        ]
        sol = solve(_default_ingredients(), macro_constraints=constraints)
        assert sol.status in ("optimal", "feasible")

    def test_loose_gte_with_micros_and_ratio(self):
        """Loose >= protein with micros + macro_ratio must not overflow int64.

        When all objective tiers are active (micros, macro_ratio with loose
        deviations, total_weight), the lexicographic weights can overflow if
        loose deviation bounds are in raw scaled units instead of normalized
        [0, PCT_SCALE] range.  A hard constraint with the same value should
        produce an equivalent result.
        """
        micro_targets = {
            "iron_mg": 10.0, "calcium_mg": 800.0, "magnesium_mg": 300.0,
            "zinc_mg": 8.0, "vitamin_c_mg": 60.0,
        }
        ratio = MacroRatio(carb_pct=50, protein_pct=25, fat_pct=25)

        # Hard version should work
        hard = [MacroConstraint("protein", "gte", 130, hard=True)]
        sol_hard = solve(
            _default_ingredients(),
            micro_targets=micro_targets,
            macro_ratio=ratio,
            macro_constraints=hard,
        )
        assert sol_hard.status in ("optimal", "feasible")

        # Loose version must also work (not infeasible due to overflow)
        loose = [MacroConstraint("protein", "gte", 130, hard=False)]
        sol_loose = solve(
            _default_ingredients(),
            micro_targets=micro_targets,
            macro_ratio=ratio,
            macro_constraints=loose,
        )
        assert sol_loose.status in ("optimal", "feasible")


class TestRatioExclusion:
    def test_hard_eq_excluded_from_ratio(self):
        """Hard = macro should not participate in ratio optimization."""
        constraints = [MacroConstraint("fat", "eq", 80, hard=True)]
        ratio = MacroRatio(carb_pct=50, protein_pct=25, fat_pct=25)
        sol = solve(
            _default_ingredients(),
            macro_ratio=ratio,
            macro_constraints=constraints,
            priorities=[PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol.status in ("optimal", "feasible")
        # Fat should be ~80g regardless of ratio (integer rounding tolerance)
        assert abs(sol.meal_fat_g - 80) <= 3


class TestIngredientDiversity:
    def test_diversity_spreads_grams(self):
        """With diversity enabled, no single ingredient should dominate.

        Compare solutions with and without diversity priority.
        The diversity-enabled solution should have a lower max-ingredient
        gram count (more even spread).
        """
        ingredients = _default_ingredients()
        sol_no_div = solve(
            ingredients,
            priorities=[PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        sol_div = solve(
            ingredients,
            priorities=[PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_INGREDIENT_DIVERSITY, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol_no_div.status in ("optimal", "feasible")
        assert sol_div.status in ("optimal", "feasible")

        max_no_div = max(i.grams for i in sol_no_div.ingredients)
        max_div = max(i.grams for i in sol_div.ingredients)
        assert max_div <= max_no_div, (
            f"Diversity should reduce max ingredient: {max_div}g vs {max_no_div}g"
        )

    def test_diversity_does_not_degrade_micros(self):
        """Micros priority is above diversity — micro coverage should not suffer."""
        ingredients = _default_ingredients()
        micro_targets = {"iron_mg": 4.9, "calcium_mg": 500.0}

        sol_no_div = solve(
            ingredients,
            micro_targets=micro_targets,
            priorities=[PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_TOTAL_WEIGHT],
        )
        sol_div = solve(
            ingredients,
            micro_targets=micro_targets,
            priorities=[PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_INGREDIENT_DIVERSITY, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol_div.status in ("optimal", "feasible")

        # Micro coverage should be equal or better (within rounding)
        for key in micro_targets:
            no_div_val = sol_no_div.micro_totals.get(key, 0.0)
            div_val = sol_div.micro_totals.get(key, 0.0)
            assert div_val >= no_div_val - 0.5, (
                f"{key}: diversity degraded coverage {div_val:.1f} vs {no_div_val:.1f}"
            )

    def test_diversity_feasible_with_all_priorities_and_20_micros(self):
        """Diversity must not overflow int64 with all 20 micro targets.

        This is the real-world scenario: the frontend optimizes all 20
        micronutrients by default, plus macro ratio, loose constraints,
        diversity, and total weight.  The lex weight chain must fit in
        int64 even with micro_pct_sum max = 20 * PCT_SCALE = 200,000.
        """
        ingredients = _default_ingredients()
        # All 20 micro targets — matches real frontend usage
        micro_targets = {
            "calcium_mg": 1000.0, "iron_mg": 8.0, "magnesium_mg": 400.0,
            "phosphorus_mg": 700.0, "potassium_mg": 3400.0, "zinc_mg": 11.0,
            "copper_mg": 0.9, "manganese_mg": 2.3, "selenium_mcg": 55.0,
            "vitamin_c_mg": 90.0, "thiamin_mg": 1.2, "riboflavin_mg": 1.3,
            "niacin_mg": 16.0, "vitamin_b6_mg": 1.3, "folate_mcg": 400.0,
            "vitamin_b12_mcg": 2.4, "vitamin_a_mcg": 900.0,
            "vitamin_d_mcg": 15.0, "vitamin_e_mg": 15.0,
            "vitamin_k_mcg": 120.0,
        }
        ratio = MacroRatio(carb_pct=50, protein_pct=25, fat_pct=25)
        constraints = [MacroConstraint("protein", "gte", 130, hard=False)]

        sol = solve(
            ingredients,
            micro_targets=micro_targets,
            macro_ratio=ratio,
            macro_constraints=constraints,
            priorities=[PRIORITY_MICROS, PRIORITY_MACRO_RATIO, PRIORITY_INGREDIENT_DIVERSITY, PRIORITY_TOTAL_WEIGHT],
        )
        assert sol.status in ("optimal", "feasible")
