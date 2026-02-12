"""Persistence layer for Daily Chow.

Auto-saves/loads app state to ~/.config/daily-chow/state.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from daily_chow.food_db import FOODS
from daily_chow.solver import Objective, Targets

STATE_DIR = Path.home() / ".config" / "daily-chow"
STATE_FILE = STATE_DIR / "state.json"


@dataclass
class IngredientState:
    key: str
    enabled: bool = True
    min_g: int = 0
    max_g: int = 500


@dataclass
class SmoothieState:
    calories: int = 720
    protein: int = 30
    fiber: int = 14


@dataclass
class AppState:
    daily_calories: int = 3500
    daily_protein: int = 160
    daily_fiber_min: int = 40
    cal_tolerance: int = 50
    protein_tolerance: int = 5
    smoothie: SmoothieState = field(default_factory=SmoothieState)
    objective: str = Objective.MINIMIZE_OIL.value
    ingredients: list[IngredientState] = field(default_factory=list)

    @property
    def targets(self) -> Targets:
        return Targets(
            meal_calories=self.daily_calories - self.smoothie.calories,
            meal_protein=self.daily_protein - self.smoothie.protein,
            meal_fiber_min=self.daily_fiber_min - self.smoothie.fiber,
            cal_tolerance=self.cal_tolerance,
            protein_tolerance=self.protein_tolerance,
        )


# ── Default ingredient set (from spec) ────────────────────────────────

DEFAULT_INGREDIENTS = [
    IngredientState("white_rice_dry", True, 0, 400),
    IngredientState("broccoli_raw", True, 200, 400),
    IngredientState("carrots_raw", True, 150, 300),
    IngredientState("zucchini_raw", True, 250, 500),
    IngredientState("avocado_oil", True, 0, 100),
    IngredientState("black_beans_cooked", True, 150, 400),
    IngredientState("yellow_split_peas_dry", True, 60, 150),
    IngredientState("ground_beef_80_20_raw", True, 0, 1000),
    IngredientState("chicken_thigh_raw", True, 0, 1000),
]


def _state_to_dict(state: AppState) -> dict[str, Any]:
    return {
        "daily_calories": state.daily_calories,
        "daily_protein": state.daily_protein,
        "daily_fiber_min": state.daily_fiber_min,
        "cal_tolerance": state.cal_tolerance,
        "protein_tolerance": state.protein_tolerance,
        "smoothie": {
            "calories": state.smoothie.calories,
            "protein": state.smoothie.protein,
            "fiber": state.smoothie.fiber,
        },
        "objective": state.objective,
        "ingredients": [
            {
                "key": ing.key,
                "enabled": ing.enabled,
                "min_g": ing.min_g,
                "max_g": ing.max_g,
            }
            for ing in state.ingredients
        ],
    }


def _dict_to_state(data: dict[str, Any]) -> AppState:
    smoothie_data = data.get("smoothie", {})
    smoothie = SmoothieState(
        calories=smoothie_data.get("calories", 720),
        protein=smoothie_data.get("protein", 30),
        fiber=smoothie_data.get("fiber", 14),
    )
    ingredients = [
        IngredientState(
            key=ing["key"],
            enabled=ing.get("enabled", True),
            min_g=ing.get("min_g", 0),
            max_g=ing.get("max_g", 500),
        )
        for ing in data.get("ingredients", [])
        if ing.get("key") in FOODS  # skip ingredients removed from database
    ]
    return AppState(
        daily_calories=data.get("daily_calories", 3500),
        daily_protein=data.get("daily_protein", 160),
        daily_fiber_min=data.get("daily_fiber_min", 40),
        cal_tolerance=data.get("cal_tolerance", 50),
        protein_tolerance=data.get("protein_tolerance", 5),
        smoothie=smoothie,
        objective=data.get("objective", Objective.MINIMIZE_OIL.value),
        ingredients=ingredients,
    )


def load_state() -> AppState:
    """Load state from disk, or return defaults if no state file exists."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            return _dict_to_state(data)
        except (json.JSONDecodeError, KeyError):
            pass

    return AppState(ingredients=list(DEFAULT_INGREDIENTS))


def save_state(state: AppState) -> None:
    """Write state to disk."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(_state_to_dict(state), indent=2) + "\n")
