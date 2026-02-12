"""Trim the full USDA Foundation Foods JSON down to a compact lookup table.

Reads the raw FoodData Central export and produces a slim JSON file keyed by
fdcId, containing only the food description, category, and a curated set of
nutrient amounts (per 100 g).
"""

from __future__ import annotations

import json
from pathlib import Path

# -- Paths -----------------------------------------------------------------
SOURCE = Path.home() / "Downloads" / "FoodData_Central_foundation_food_json_2025-12-18.json"
OUTPUT = Path(__file__).resolve().parent.parent / "src" / "daily_chow" / "data" / "usda_foundation.json"

# -- Nutrient IDs to keep --------------------------------------------------
KEEP_NUTRIENT_IDS: set[int] = {
    # Energy
    2047,  # Energy (Atwater General Factors)
    1008,  # Energy (fallback)
    # Macros
    1003,  # Protein
    1004,  # Total lipid (fat)
    1005,  # Carbohydrate, by difference
    1079,  # Fiber, total dietary
    # Tier 1 - Major Minerals
    1087,  # Calcium, Ca
    1089,  # Iron, Fe
    1090,  # Magnesium, Mg
    1091,  # Phosphorus, P
    1092,  # Potassium, K
    1093,  # Sodium, Na
    1095,  # Zinc, Zn
    1098,  # Copper, Cu
    1101,  # Manganese, Mn
    1103,  # Selenium, Se
    # Tier 2 - B-Vitamins + C
    1162,  # Vitamin C, total ascorbic acid
    1165,  # Thiamin
    1166,  # Riboflavin
    1167,  # Niacin
    1175,  # Vitamin B-6
    1177,  # Folate, total
    1178,  # Vitamin B-12
    1176,  # Biotin
    # Tier 3 - Fat-soluble vitamins
    1106,  # Vitamin A, RAE
    1114,  # Vitamin D (D2 + D3)
    1109,  # Vitamin E (alpha-tocopherol)
    1185,  # Vitamin K (phylloquinone)
}


def main() -> None:
    print(f"Reading {SOURCE}  ({SOURCE.stat().st_size / 1_048_576:.1f} MB)")
    with open(SOURCE) as f:
        raw = json.load(f)

    foods_raw: list[dict] = raw["FoundationFoods"]
    print(f"Found {len(foods_raw)} Foundation Foods in source file")

    result: dict[str, dict] = {}
    total_nutrient_count = 0

    for food in foods_raw:
        fdc_id = str(food["fdcId"])
        nutrients: dict[str, float] = {}

        for fn in food.get("foodNutrients", []):
            nid = fn.get("nutrient", {}).get("id")
            if nid in KEEP_NUTRIENT_IDS and "amount" in fn:
                nutrients[str(nid)] = fn["amount"]

        total_nutrient_count += len(nutrients)

        result[fdc_id] = {
            "description": food["description"],
            "category": food.get("foodCategory", {}).get("description", ""),
            "nutrients": nutrients,
        }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(result, f, separators=(",", ":"))

    file_size = OUTPUT.stat().st_size
    avg_nutrients = total_nutrient_count / len(result) if result else 0

    print()
    print("=== Summary ===")
    print(f"  Total foods:            {len(result)}")
    print(f"  Avg nutrients per food: {avg_nutrients:.1f}")
    print(f"  Output file:            {OUTPUT}")
    print(f"  Output size:            {file_size:,} bytes ({file_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
