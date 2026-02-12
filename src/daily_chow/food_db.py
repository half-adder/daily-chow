"""Food database for Daily Chow.

Loads the pre-built foods.json (produced by scripts/build_food_db.py)
which contains all USDA foods with tracked nutrient values.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from daily_chow.dri import MICRO_INFO

_DATA_PATH = Path(__file__).parent / "data" / "foods.json"

# Map USDA nutrient IDs to our macro field names
_MACRO_USDA_IDS: dict[str, list[int]] = {
    "cal": [2047, 1008],  # prefer Atwater General, fallback to Energy
    "protein": [1003],
    "fat": [1004],
    "carbs": [1005],
    "fiber": [1079],
}

# Reverse map: usda_id -> canonical micro key
_USDA_ID_TO_MICRO: dict[int, str] = {
    info.usda_id: key for key, info in MICRO_INFO.items()
}


@dataclass(frozen=True, slots=True)
class Food:
    """A food item with full nutrition data."""

    fdc_id: int
    name: str  # short display name (Haiku-generated)
    subtitle: str  # qualifier (raw, cooked, etc.)
    usda_description: str  # original USDA description
    category: str  # USDA food category
    cal_per_100g: float
    protein_per_100g: float
    fat_per_100g: float
    carbs_per_100g: float
    fiber_per_100g: float
    micros: dict[str, float] = field(default_factory=dict)


def _extract_macro(nutrients: dict[str, float], usda_ids: list[int]) -> float:
    """Get the first available macro value from a list of USDA IDs."""
    for uid in usda_ids:
        val = nutrients.get(str(uid))
        if val is not None:
            return val
    return 0.0


def _extract_micros(nutrients: dict[str, float]) -> dict[str, float]:
    """Extract micronutrient values using our canonical keys."""
    micros: dict[str, float] = {}
    for uid_str, amount in nutrients.items():
        uid = int(uid_str)
        micro_key = _USDA_ID_TO_MICRO.get(uid)
        if micro_key is not None:
            micros[micro_key] = amount
    return micros


def _build_food(entry: dict) -> Food:
    """Build a Food from a foods.json entry."""
    nutrients = entry.get("nutrients", {})
    return Food(
        fdc_id=entry["fdc_id"],
        name=entry["name"],
        subtitle=entry.get("subtitle", ""),
        usda_description=entry.get("usda_description", entry["name"]),
        category=entry.get("category", ""),
        cal_per_100g=_extract_macro(nutrients, _MACRO_USDA_IDS["cal"]),
        protein_per_100g=_extract_macro(nutrients, _MACRO_USDA_IDS["protein"]),
        fat_per_100g=_extract_macro(nutrients, _MACRO_USDA_IDS["fat"]),
        carbs_per_100g=_extract_macro(nutrients, _MACRO_USDA_IDS["carbs"]),
        fiber_per_100g=_extract_macro(nutrients, _MACRO_USDA_IDS["fiber"]),
        micros=_extract_micros(nutrients),
    )


@cache
def load_foods() -> dict[int, Food]:
    """Load all foods from the pre-built foods.json."""
    with open(_DATA_PATH) as f:
        raw: list[dict] = json.load(f)
    return {entry["fdc_id"]: _build_food(entry) for entry in raw}
