"""FastAPI backend for Daily Chow solver."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from daily_chow.dri import (
    DRI_EAR,
    DRI_TARGETS,
    DRI_UL,
    MICRO_INFO,
    AgeGroup,
    Sex,
)
from daily_chow.food_db import load_foods
from daily_chow.solver import DEFAULT_PRIORITIES, IngredientInput, Targets, solve

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
    meal_calories_kcal: int = 2780
    meal_protein_g: int = 130
    meal_fiber_min_g: int = 26
    cal_tolerance: int = 50
    protein_tolerance: int = 5


class SolveRequest(BaseModel):
    ingredients: list[IngredientRequest]
    targets: TargetsRequest = TargetsRequest()
    priorities: list[str] = list(DEFAULT_PRIORITIES)
    sex: str = "male"
    age_group: str = "19-30"
    optimize_nutrients: list[str] = []
    pinned_micros: dict[str, float] = {}


class SolvedIngredientResponse(BaseModel):
    key: int  # FDC ID
    grams: int
    calories_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    fiber_g: float


class MicroResult(BaseModel):
    total: float
    pinned: float
    dri: float
    remaining: float
    pct: float
    optimized: bool
    ear: float | None = None
    ul: float | None = None


class SolveResponse(BaseModel):
    status: str
    ingredients: list[SolvedIngredientResponse]
    meal_calories_kcal: float
    meal_protein_g: float
    meal_fat_g: float
    meal_carbs_g: float
    meal_fiber_g: float
    micros: dict[str, MicroResult] = {}


class FoodResponse(BaseModel):
    fdc_id: int
    name: str
    subtitle: str
    usda_description: str
    calories_kcal_per_100g: float
    protein_g_per_100g: float
    fat_g_per_100g: float
    carbs_g_per_100g: float
    fiber_g_per_100g: float
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
            calories_kcal_per_100g=f.calories_kcal_per_100g,
            protein_g_per_100g=f.protein_g_per_100g,
            fat_g_per_100g=f.fat_g_per_100g,
            carbs_g_per_100g=f.carbs_g_per_100g,
            fiber_g_per_100g=f.fiber_g_per_100g,
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
        meal_calories_kcal=req.targets.meal_calories_kcal,
        meal_protein_g=req.targets.meal_protein_g,
        meal_fiber_min_g=req.targets.meal_fiber_min_g,
        cal_tolerance=req.targets.cal_tolerance,
        protein_tolerance=req.targets.protein_tolerance,
    )

    # Build micro targets for checked nutrients
    sex = Sex(req.sex)
    age_group = AgeGroup(req.age_group)
    dri = DRI_TARGETS[(sex, age_group)]

    micro_targets: dict[str, float] | None = None
    if req.optimize_nutrients:
        micro_targets = {}
        for k in req.optimize_nutrients:
            dri_val = dri.get(k, 0.0)
            pinned_val = req.pinned_micros.get(k, 0.0)
            remaining = max(0.0, dri_val - pinned_val)
            if remaining > 0 and k in dri:
                micro_targets[k] = remaining

    # Build UL constraints: for each nutrient with a UL, subtract pinned amounts
    ul_table = DRI_UL.get((sex, age_group), {})
    micro_uls: dict[str, float] | None = None
    if ul_table:
        micro_uls = {}
        for k, ul_val in ul_table.items():
            pinned_val = req.pinned_micros.get(k, 0.0)
            remaining_ul = ul_val - pinned_val
            if remaining_ul > 0:
                micro_uls[k] = remaining_ul

    solution = solve(
        ingredient_inputs, targets,
        micro_targets=micro_targets, micro_uls=micro_uls,
        priorities=req.priorities,
    )

    # Build micro results for all 20 tracked nutrients
    optimized_set = set(req.optimize_nutrients)
    ear_table = DRI_EAR.get((sex, age_group), {})
    micros: dict[str, MicroResult] = {}
    for key in MICRO_INFO:
        dri_val = dri.get(key, 0.0)
        pinned_val = req.pinned_micros.get(key, 0.0)
        remaining_val = max(0.0, dri_val - pinned_val)
        meal_total = solution.micro_totals.get(key, 0.0)
        pct = (meal_total + pinned_val) / dri_val * 100 if dri_val > 0 else 0.0
        micros[key] = MicroResult(
            total=round(meal_total, 2),
            pinned=round(pinned_val, 2),
            dri=round(dri_val, 2),
            remaining=round(remaining_val, 2),
            pct=round(pct, 1),
            optimized=key in optimized_set,
            ear=ear_table.get(key),
            ul=ul_table.get(key),
        )

    return SolveResponse(
        status=solution.status,
        ingredients=[
            SolvedIngredientResponse(
                key=si.key,
                grams=si.grams,
                calories_kcal=si.calories_kcal,
                protein_g=si.protein_g,
                fat_g=si.fat_g,
                carbs_g=si.carbs_g,
                fiber_g=si.fiber_g,
            )
            for si in solution.ingredients
        ],
        meal_calories_kcal=solution.meal_calories_kcal,
        meal_protein_g=solution.meal_protein_g,
        meal_fat_g=solution.meal_fat_g,
        meal_carbs_g=solution.meal_carbs_g,
        meal_fiber_g=solution.meal_fiber_g,
        micros=micros,
    )
