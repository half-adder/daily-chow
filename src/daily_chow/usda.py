"""USDA FoodData Central loader.

Loads the trimmed USDA Foundation Foods JSON at startup, joins with our
FoodEntry mappings to build resolved Food objects with macros + micros.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from daily_chow.dri import MICRO_INFO
from daily_chow.food_db import FOOD_ENTRIES, Food, FoodEntry

_DATA_PATH = Path(__file__).parent / "data" / "usda_foundation.json"

# Map USDA nutrient IDs to our macro field names
_MACRO_USDA_IDS = {
    "cal": [2047, 1008],      # prefer Atwater General, fallback to Energy
    "protein": [1003],
    "fat": [1004],
    "carbs": [1005],
    "fiber": [1079],
}

# Build reverse map: usda_id -> canonical micro key
_USDA_ID_TO_MICRO: dict[int, str] = {
    info.usda_id: key for key, info in MICRO_INFO.items()
}


@cache
def _load_usda_json() -> dict[str, dict]:
    """Load and cache the trimmed USDA JSON."""
    with open(_DATA_PATH) as f:
        return json.load(f)


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


def _build_food(entry: FoodEntry, usda_data: dict[str, dict]) -> Food:
    """Build a Food from a FoodEntry + USDA data."""
    nutrients: dict[str, float] = {}
    micros: dict[str, float] = {}

    if entry.usda_fdc_id is not None:
        usda_food = usda_data.get(str(entry.usda_fdc_id))
        if usda_food is not None:
            nutrients = usda_food.get("nutrients", {})
            micros = _extract_micros(nutrients)

    # Macros: use USDA if available, otherwise fall back to manual values
    cal = _extract_macro(nutrients, _MACRO_USDA_IDS["cal"])
    protein = _extract_macro(nutrients, _MACRO_USDA_IDS["protein"])
    fat = _extract_macro(nutrients, _MACRO_USDA_IDS["fat"])
    carbs = _extract_macro(nutrients, _MACRO_USDA_IDS["carbs"])
    fiber = _extract_macro(nutrients, _MACRO_USDA_IDS["fiber"])

    # Fall back to manual values if USDA data is missing or zero
    if cal == 0.0 and entry.manual_cal is not None:
        cal = entry.manual_cal
    if protein == 0.0 and entry.manual_protein is not None:
        protein = entry.manual_protein
    if fat == 0.0 and entry.manual_fat is not None:
        fat = entry.manual_fat
    if carbs == 0.0 and entry.manual_carbs is not None:
        carbs = entry.manual_carbs
    if fiber == 0.0 and entry.manual_fiber is not None:
        fiber = entry.manual_fiber

    # Merge manual micros as fallback for missing USDA data
    if entry.manual_micros:
        for mk, mv in entry.manual_micros.items():
            if mk not in micros:
                micros[mk] = mv

    return Food(
        name=entry.name,
        unit_note=entry.unit_note,
        cal_per_100g=cal,
        protein_per_100g=protein,
        fat_per_100g=fat,
        carbs_per_100g=carbs,
        fiber_per_100g=fiber,
        category=entry.category,
        default_min=entry.default_min,
        default_max=entry.default_max,
        micros=micros,
    )


@cache
def load_foods() -> dict[str, Food]:
    """Load all foods, joining FoodEntry metadata with USDA nutrition data."""
    usda_data = _load_usda_json()
    return {key: _build_food(entry, usda_data) for key, entry in FOOD_ENTRIES.items()}
