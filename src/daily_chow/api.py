"""FastAPI backend for Daily Chow solver."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from daily_chow.food_db import FOODS
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
    key: str
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


class SolvedIngredientResponse(BaseModel):
    key: str
    grams: int
    calories: float
    protein: float
    fat: float
    carbs: float
    fiber: float


class SolveResponse(BaseModel):
    status: str
    ingredients: list[SolvedIngredientResponse]
    meal_calories: float
    meal_protein: float
    meal_fat: float
    meal_carbs: float
    meal_fiber: float


class FoodResponse(BaseModel):
    name: str
    unit_note: str
    cal_per_100g: float
    protein_per_100g: float
    fat_per_100g: float
    carbs_per_100g: float
    fiber_per_100g: float
    category: str
    default_min: int
    default_max: int


# ── Endpoints ─────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/foods")
def get_foods() -> dict[str, FoodResponse]:
    return {
        key: FoodResponse(
            name=f.name,
            unit_note=f.unit_note,
            cal_per_100g=f.cal_per_100g,
            protein_per_100g=f.protein_per_100g,
            fat_per_100g=f.fat_per_100g,
            carbs_per_100g=f.carbs_per_100g,
            fiber_per_100g=f.fiber_per_100g,
            category=f.category,
            default_min=f.default_min,
            default_max=f.default_max,
        )
        for key, f in FOODS.items()
    }


@app.post("/solve")
def post_solve(req: SolveRequest) -> SolveResponse:
    ingredient_inputs = []
    for ing in req.ingredients:
        food = FOODS.get(ing.key)
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

    objective = Objective(req.objective)
    solution = solve(ingredient_inputs, targets, objective)

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
    )
