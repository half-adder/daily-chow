"""FastAPI backend for Daily Chow solver."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from daily_chow.dri import (
    DRI_TARGETS,
    MICRO_INFO,
    SMOOTHIE_MICROS,
    AgeGroup,
    Sex,
    remaining_targets,
)
from daily_chow.food_db import load_foods
from daily_chow.solver import IngredientInput, Objective, Targets, solve

app = FastAPI(title="Daily Chow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────


class IngredientRequest(BaseModel):
    key: int  # FDC ID
    min_g: int
    max_g: int


class TargetsRequest(BaseModel):
    meal_calories: int = 2780
    meal_protein: int = 130
    meal_fiber_min: int = 26
    cal_tolerance: int = 50
    protein_tolerance: int = 5


class SolveRequest(BaseModel):
    ingredients: list[IngredientRequest]
    targets: TargetsRequest = TargetsRequest()
    objective: str = "minimize_oil"
    sex: str = "male"
    age_group: str = "19-30"
    optimize_nutrients: list[str] = []


class SolvedIngredientResponse(BaseModel):
    key: int  # FDC ID
    grams: int
    calories: float
    protein: float
    fat: float
    carbs: float
    fiber: float


class MicroResult(BaseModel):
    total: float  # amount from the meal
    smoothie: float  # amount from smoothie
    dri: float  # full daily target
    remaining: float  # max(0, dri - smoothie)
    pct: float  # (total + smoothie) / dri * 100
    optimized: bool  # whether this was in optimize_nutrients


class SolveResponse(BaseModel):
    status: str
    ingredients: list[SolvedIngredientResponse]
    meal_calories: float
    meal_protein: float
    meal_fat: float
    meal_carbs: float
    meal_fiber: float
    micros: dict[str, MicroResult] = {}


class FoodResponse(BaseModel):
    fdc_id: int
    name: str
    subtitle: str
    usda_description: str
    cal_per_100g: float
    protein_per_100g: float
    fat_per_100g: float
    carbs_per_100g: float
    fiber_per_100g: float
    category: str
    micros: dict[str, float] = {}


# ── Endpoints ─────────────────────────────────────────────────────────


@app.get("/foods")
def get_foods() -> dict[int, FoodResponse]:
    foods = load_foods()
    return {
        fdc_id: FoodResponse(
            fdc_id=f.fdc_id,
            name=f.name,
            subtitle=f.subtitle,
            usda_description=f.usda_description,
            cal_per_100g=f.cal_per_100g,
            protein_per_100g=f.protein_per_100g,
            fat_per_100g=f.fat_per_100g,
            carbs_per_100g=f.carbs_per_100g,
            fiber_per_100g=f.fiber_per_100g,
            category=f.category,
            micros=f.micros,
        )
        for fdc_id, f in foods.items()
    }


@app.post("/solve")
def post_solve(req: SolveRequest) -> SolveResponse:
    foods = load_foods()
    ingredient_inputs = []
    for ing in req.ingredients:
        food = foods.get(ing.key)
        if food is None:
            continue
        min_g = min(ing.min_g, ing.max_g)
        max_g = max(ing.min_g, ing.max_g)
        ingredient_inputs.append(IngredientInput(ing.key, food, min_g, max_g))

    targets = Targets(
        meal_calories=req.targets.meal_calories,
        meal_protein=req.targets.meal_protein,
        meal_fiber_min=req.targets.meal_fiber_min,
        cal_tolerance=req.targets.cal_tolerance,
        protein_tolerance=req.targets.protein_tolerance,
    )

    # Build micro targets for checked nutrients
    sex = Sex(req.sex)
    age_group = AgeGroup(req.age_group)
    all_remaining = remaining_targets(sex, age_group)

    micro_targets: dict[str, float] | None = None
    if req.optimize_nutrients:
        micro_targets = {
            k: all_remaining[k]
            for k in req.optimize_nutrients
            if k in all_remaining
        }

    objective = Objective(req.objective)
    solution = solve(ingredient_inputs, targets, objective, micro_targets=micro_targets)

    # Build micro results for all 20 tracked nutrients
    dri = DRI_TARGETS[(sex, age_group)]
    optimized_set = set(req.optimize_nutrients)
    micros: dict[str, MicroResult] = {}
    for key in MICRO_INFO:
        dri_val = dri.get(key, 0.0)
        smoothie_val = SMOOTHIE_MICROS.get(key, 0.0)
        remaining_val = max(0.0, dri_val - smoothie_val)
        meal_total = solution.micro_totals.get(key, 0.0)
        pct = (meal_total + smoothie_val) / dri_val * 100 if dri_val > 0 else 0.0
        micros[key] = MicroResult(
            total=round(meal_total, 2),
            smoothie=round(smoothie_val, 2),
            dri=round(dri_val, 2),
            remaining=round(remaining_val, 2),
            pct=round(pct, 1),
            optimized=key in optimized_set,
        )

    return SolveResponse(
        status=solution.status,
        ingredients=[
            SolvedIngredientResponse(
                key=si.key,
                grams=si.grams,
                calories=si.calories,
                protein=si.protein,
                fat=si.fat,
                carbs=si.carbs,
                fiber=si.fiber,
            )
            for si in solution.ingredients
        ],
        meal_calories=solution.meal_calories,
        meal_protein=solution.meal_protein,
        meal_fat=solution.meal_fat,
        meal_carbs=solution.meal_carbs,
        meal_fiber=solution.meal_fiber,
        micros=micros,
    )
