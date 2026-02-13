"""Tests for the CP-SAT meal solver."""

from daily_chow.food_db import load_foods
from daily_chow.solver import (
    IngredientInput,
    Objective,
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

    def test_protein_within_tolerance(self):
        targets = Targets()
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        assert abs(sol.meal_protein_g - targets.meal_protein_g) <= targets.protein_tolerance + 3

    def test_fiber_meets_minimum(self):
        targets = Targets()
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_fiber_g >= targets.meal_fiber_min_g - 1


class TestSolverObjectives:
    def test_minimize_oil_produces_less_oil(self):
        ingredients = _default_ingredients()
        sol_oil = solve(ingredients, objective=Objective.MINIMIZE_OIL)
        sol_grams = solve(ingredients, objective=Objective.MINIMIZE_TOTAL_GRAMS)
        assert sol_oil.status in ("optimal", "feasible")
        assert sol_grams.status in ("optimal", "feasible")
        oil_min = _grams_for(sol_oil, "Avocado Oil")
        oil_other = _grams_for(sol_grams, "Avocado Oil")
        assert oil_min <= oil_other


class TestMicroOptimization:
    def test_micro_targets_feasible(self):
        sol = solve(_default_ingredients(), micro_targets={"iron_mg": 4.9})
        assert sol.status in ("optimal", "feasible")

    def test_micro_totals_populated(self):
        sol = solve(_default_ingredients())
        assert sol.status in ("optimal", "feasible")
        assert len(sol.micro_totals) > 0
        assert "calcium_mg" in sol.micro_totals
