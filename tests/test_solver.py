"""Tests for the CP-SAT meal solver."""

from daily_chow.dri import AgeGroup, Sex, remaining_targets
from daily_chow.usda import load_foods

FOODS = load_foods()
from daily_chow.solver import (
    IngredientInput,
    Objective,
    Solution,
    Targets,
    solve,
)


def _default_ingredients() -> list[IngredientInput]:
    """The 9 default ingredients from the spec with their default bounds."""
    return [
        IngredientInput("white_rice_dry", FOODS["white_rice_dry"], 0, 400),
        IngredientInput("broccoli_raw", FOODS["broccoli_raw"], 200, 400),
        IngredientInput("carrots_raw", FOODS["carrots_raw"], 150, 300),
        IngredientInput("zucchini_raw", FOODS["zucchini_raw"], 250, 500),
        IngredientInput("avocado_oil", FOODS["avocado_oil"], 0, 100),
        IngredientInput("black_beans_cooked", FOODS["black_beans_cooked"], 150, 400),
        IngredientInput("yellow_split_peas_dry", FOODS["yellow_split_peas_dry"], 60, 150),
        IngredientInput("ground_beef_80_20_raw", FOODS["ground_beef_80_20_raw"], 0, 1000),
        IngredientInput("chicken_thigh_raw", FOODS["chicken_thigh_raw"], 0, 1000),
    ]


def _grams_for(sol: Solution, key: str) -> int:
    for ing in sol.ingredients:
        if ing.key == key:
            return ing.grams
    raise KeyError(f"Ingredient {key} not in solution")


class TestSolverFeasibility:
    def test_default_ingredients_feasible(self):
        sol = solve(_default_ingredients())
        assert sol.status in ("optimal", "feasible")
        assert len(sol.ingredients) == 9

    def test_empty_ingredients_infeasible(self):
        sol = solve([])
        assert sol.status == "infeasible"

    def test_impossible_bounds_infeasible(self):
        """Very tight bounds that can't possibly hit targets."""
        ingredients = [
            IngredientInput("broccoli_raw", FOODS["broccoli_raw"], 10, 10),
        ]
        sol = solve(ingredients)
        assert sol.status == "infeasible"


class TestSolverConstraints:
    def test_calories_within_tolerance(self):
        targets = Targets()
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        assert abs(sol.meal_calories - targets.meal_calories) <= targets.cal_tolerance + 1

    def test_protein_within_tolerance(self):
        targets = Targets()
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        # +3 slack accounts for accumulated integer rounding across ingredients
        assert abs(sol.meal_protein - targets.meal_protein) <= targets.protein_tolerance + 3

    def test_fiber_meets_minimum(self):
        targets = Targets()
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        # Allow small rounding slack from integer scaling
        assert sol.meal_fiber >= targets.meal_fiber_min - 1

    def test_respects_min_bounds(self):
        ingredients = _default_ingredients()
        sol = solve(ingredients)
        assert sol.status in ("optimal", "feasible")
        assert _grams_for(sol, "broccoli_raw") >= 200
        assert _grams_for(sol, "carrots_raw") >= 150
        assert _grams_for(sol, "zucchini_raw") >= 250

    def test_respects_max_bounds(self):
        ingredients = _default_ingredients()
        sol = solve(ingredients)
        assert sol.status in ("optimal", "feasible")
        assert _grams_for(sol, "avocado_oil") <= 100
        assert _grams_for(sol, "white_rice_dry") <= 400


class TestSolverObjectives:
    def test_minimize_oil_produces_less_oil(self):
        ingredients = _default_ingredients()
        sol_oil = solve(ingredients, objective=Objective.MINIMIZE_OIL)
        sol_grams = solve(ingredients, objective=Objective.MINIMIZE_TOTAL_GRAMS)
        assert sol_oil.status in ("optimal", "feasible")
        assert sol_grams.status in ("optimal", "feasible")
        oil_min = _grams_for(sol_oil, "avocado_oil")
        oil_other = _grams_for(sol_grams, "avocado_oil")
        assert oil_min <= oil_other

    def test_minimize_rice_deviation(self):
        ingredients = _default_ingredients()
        preferred = 200
        sol = solve(
            ingredients,
            objective=Objective.MINIMIZE_RICE_DEVIATION,
            preferred_rice_g=preferred,
        )
        assert sol.status in ("optimal", "feasible")
        rice_g = _grams_for(sol, "white_rice_dry")
        # Should be reasonably close to preferred
        assert abs(rice_g - preferred) <= 150


class TestSolverCustomTargets:
    def test_higher_calorie_target(self):
        targets = Targets(meal_calories=3000, meal_protein=150, meal_fiber_min=30)
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        assert abs(sol.meal_calories - 3000) <= targets.cal_tolerance + 1

    def test_tight_tolerance_still_feasible(self):
        targets = Targets(cal_tolerance=20, protein_tolerance=3)
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")

    def test_bound_change_affects_solution(self):
        """Raising oil minimum should increase oil in solution."""
        base = _default_ingredients()
        sol_base = solve(base)
        assert sol_base.status in ("optimal", "feasible")
        base_oil = _grams_for(sol_base, "avocado_oil")

        # Force high oil minimum
        modified = [
            IngredientInput(i.key, i.food, 50 if i.key == "avocado_oil" else i.min_g, i.max_g)
            for i in base
        ]
        sol_mod = solve(modified)
        assert sol_mod.status in ("optimal", "feasible")
        mod_oil = _grams_for(sol_mod, "avocado_oil")
        assert mod_oil >= 50
        assert mod_oil >= base_oil


class TestMicroOptimization:
    def test_micro_targets_feasible(self):
        """Solver remains feasible when micro targets are added."""
        targets_remaining = remaining_targets(Sex.MALE, AgeGroup.AGE_19_30)
        sol = solve(_default_ingredients(), micro_targets=targets_remaining)
        assert sol.status in ("optimal", "feasible")
        assert len(sol.ingredients) == 9

    def test_micro_totals_populated(self):
        """Solution includes micro totals for all nutrients in ingredients."""
        sol = solve(_default_ingredients())
        assert sol.status in ("optimal", "feasible")
        # Default ingredients include foods with USDA micros
        assert len(sol.micro_totals) > 0
        # Calcium should be present (most foods have it)
        assert "calcium_mg" in sol.micro_totals
        assert sol.micro_totals["calcium_mg"] > 0

    def test_micro_targets_empty_dict(self):
        """Empty micro_targets dict behaves same as None."""
        sol_none = solve(_default_ingredients(), micro_targets=None)
        sol_empty = solve(_default_ingredients(), micro_targets={})
        assert sol_none.status == sol_empty.status
        # Same primary objective, so same solution
        for ing_a, ing_b in zip(sol_none.ingredients, sol_empty.ingredients):
            assert ing_a.grams == ing_b.grams

    def test_hard_constraints_preserved_with_micros(self):
        """Macro hard constraints are still respected with micro optimization."""
        targets = Targets()
        targets_remaining = remaining_targets(Sex.MALE, AgeGroup.AGE_19_30)
        sol = solve(_default_ingredients(), targets, micro_targets=targets_remaining)
        assert sol.status in ("optimal", "feasible")
        assert abs(sol.meal_calories - targets.meal_calories) <= targets.cal_tolerance + 3
        assert sol.meal_fiber >= targets.meal_fiber_min - 1

    def test_micro_optimization_improves_nutrients(self):
        """With micro targets, solution should have better nutrient coverage
        than without (or at least not worse), given same primary objective."""
        ingredients = _default_ingredients()
        targets_remaining = remaining_targets(Sex.MALE, AgeGroup.AGE_19_30)

        sol_no_micro = solve(ingredients, micro_targets=None)
        sol_with_micro = solve(ingredients, micro_targets=targets_remaining)

        assert sol_no_micro.status in ("optimal", "feasible")
        assert sol_with_micro.status in ("optimal", "feasible")

        # Compare total nutrient coverage (sum of min(total/target, 1) for each)
        def coverage_score(sol: Solution) -> float:
            score = 0.0
            for key, target in targets_remaining.items():
                if target > 0:
                    actual = sol.micro_totals.get(key, 0.0)
                    score += min(actual / target, 1.0)
            return score

        score_no = coverage_score(sol_no_micro)
        score_with = coverage_score(sol_with_micro)
        # Micro optimization should not make things worse
        assert score_with >= score_no - 0.1  # small tolerance for rounding

    def test_single_nutrient_target(self):
        """Optimizing for a single nutrient works."""
        sol = solve(
            _default_ingredients(),
            micro_targets={"iron_mg": 4.9},
        )
        assert sol.status in ("optimal", "feasible")
        assert "iron_mg" in sol.micro_totals
