"""Tests for the CP-SAT meal solver."""

from daily_chow.food_db import load_foods
from daily_chow.solver import (
    IngredientInput,
    MacroRatio,
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
        targets = Targets()
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_protein_g >= targets.meal_protein_min_g - 1

    def test_fiber_meets_minimum(self):
        targets = Targets()
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_fiber_g >= targets.meal_fiber_min_g - 1


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
        targets = Targets(meal_protein_min_g=130)
        sol = solve(_default_ingredients(), targets)
        assert sol.status in ("optimal", "feasible")
        assert sol.meal_protein_g >= 130 - 1

    def test_protein_can_exceed_floor(self):
        targets = Targets(meal_protein_min_g=80)
        sol = solve(_default_ingredients(), targets)
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
