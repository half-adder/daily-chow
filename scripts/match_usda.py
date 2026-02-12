"""Match Daily Chow foods to USDA Foundation Foods by fdcId.

Prints the proposed mapping and flags any foods without a match.
"""

from __future__ import annotations

import json
from pathlib import Path

USDA_PATH = Path(__file__).resolve().parent.parent / "src" / "daily_chow" / "data" / "usda_foundation.json"

with open(USDA_PATH) as f:
    USDA = json.load(f)

# Build reverse index: description -> fdcId
desc_to_fdc: dict[str, str] = {v["description"]: k for k, v in USDA.items()}

# Hand-curated mapping: our key -> USDA description (or None if no match)
MAPPING: dict[str, str | None] = {
    # Grains
    "white_rice_dry": "Rice, white, long grain, unenriched, raw",
    "brown_rice_dry": "Rice, brown, long grain, unenriched, raw",
    "oats_dry": "Oats, whole grain, rolled, old fashioned",
    "quinoa_dry": None,  # No raw quinoa grain in Foundation Foods
    "pasta_dry": None,  # No dry pasta in Foundation Foods
    "bread_whole_wheat": "Bread, whole-wheat, commercially prepared",
    "corn_tortilla": None,  # No corn tortilla
    "sweet_potato_raw": "Sweet potatoes, orange flesh, without skin, raw",
    "potato_raw": "Potatoes, russet, without skin, raw",
    # Vegetables
    "broccoli_raw": "Broccoli, raw",
    "carrots_raw": "Carrots, mature, raw",
    "zucchini_raw": "Squash, summer, green, zucchini, includes skin, raw",
    "spinach_raw": "Spinach, mature",
    "kale_raw": "Kale, raw",
    "bell_pepper_raw": "Peppers, bell, red, raw",
    "tomato_raw": "Tomato, roma",
    "onion_raw": "Onions, yellow, raw",
    "cauliflower_raw": "Cauliflower, raw",
    "cabbage_raw": "Cabbage, green, raw",
    "cucumber_raw": "Cucumber, with peel, raw",
    "mushrooms_raw": "Mushrooms, white button",
    "green_beans_raw": "Beans, snap, green, raw",
    "asparagus_raw": "Asparagus, green, raw",
    "brussels_sprouts_raw": "Brussels sprouts, raw",
    # Legumes
    "black_beans_cooked": "Beans, black, canned, sodium added, drained and rinsed",
    "yellow_split_peas_dry": None,  # No split peas
    "lentils_dry": "Lentils, dry",
    "chickpeas_cooked": "Chickpeas (garbanzo beans, bengal gram), canned, sodium added, drained and rinsed",
    "kidney_beans_cooked": "Beans, kidney, dark red, canned, sodium added, sugar added, drained and rinsed",
    "pinto_beans_cooked": "Beans, pinto, canned, sodium added, drained and rinsed",
    "edamame_shelled": None,  # No edamame
    # Meats
    "ground_beef_80_20_raw": "Beef, ground, 80% lean meat / 20% fat, raw",
    "ground_beef_90_10_raw": "Beef, ground, 90% lean meat / 10% fat, raw",
    "chicken_thigh_raw": "Chicken, thigh, boneless, skinless, raw",
    "chicken_breast_raw": "Chicken, breast, boneless, skinless, raw",
    "turkey_ground_93_raw": "Turkey, ground, 93% lean/ 7% fat, raw",
    "pork_loin_raw": "Pork, loin, boneless, raw",
    "pork_shoulder_raw": None,  # No pork shoulder
    "steak_sirloin_raw": "Beef, top sirloin steak, raw",
    # Seafood
    "salmon_raw": "Fish, salmon, Atlantic, farm raised, raw",
    "shrimp_raw": "Crustaceans, shrimp, farm raised, raw",
    "tuna_canned": "Fish, tuna, light, canned in water, drained solids",
    "tilapia_raw": "Fish, tilapia, farm raised, raw",
    "cod_raw": "Fish, cod, Atlantic, wild caught, raw",
    # Oils & Fats
    "avocado_oil": None,  # No avocado oil in Foundation Foods
    "olive_oil": "Oil, olive, extra virgin",
    "coconut_oil": "Oil, coconut",
    "butter": "Butter, stick, unsalted",
    # Dairy
    "whole_milk": "Milk, whole, 3.25% milkfat, with added vitamin D",
    "greek_yogurt_whole": "Yogurt, Greek, plain, whole milk",
    "cottage_cheese": "Cottage cheese, full fat, large or small curd",
    "cheddar_cheese": "Cheese, cheddar",
    "eggs_whole": "Eggs, Grade A, Large, egg whole",
    # Nuts & Seeds
    "almonds": "Nuts, almonds, whole, raw",
    "peanut_butter": "Peanut butter, creamy",
    "walnuts": "Nuts, walnuts, English, halves, raw",
    "chia_seeds": "Chia seeds, dry, raw",
    "flax_seeds": "Flaxseed, ground",
    "hemp_seeds": None,  # No hemp seeds
    # Fruits
    "banana": "Bananas, ripe and slightly ripe, raw",
    "apple": "Apples, gala, with skin, raw",
    "blueberries": "Blueberries, raw",
    "avocado": "Avocado, Hass, peeled, raw",
    "dates_medjool": None,  # No dates
}


def main() -> None:
    matched = 0
    unmatched = 0

    print("=== Food Mapping: our key -> USDA fdcId ===\n")

    for key, usda_desc in MAPPING.items():
        if usda_desc is None:
            print(f"  {key:<30} -> NO MATCH (will use manual macro values)")
            unmatched += 1
        elif usda_desc in desc_to_fdc:
            fdc_id = desc_to_fdc[usda_desc]
            nutrients = USDA[fdc_id]["nutrients"]
            n_count = len(nutrients)
            print(f"  {key:<30} -> {fdc_id:<10} ({n_count:>2} nutrients)  {usda_desc}")
            matched += 1
        else:
            print(f"  {key:<30} -> DESCRIPTION NOT FOUND: {usda_desc!r}")
            unmatched += 1

    print(f"\n=== Summary: {matched} matched, {unmatched} unmatched out of {len(MAPPING)} ===")

    # Output the Python dict literal for copy-paste into food_db.py
    print("\n\n# --- Copy-paste mapping for food_db.py ---")
    print("USDA_FDC_IDS: dict[str, int | None] = {")
    for key, usda_desc in MAPPING.items():
        if usda_desc and usda_desc in desc_to_fdc:
            fdc_id = desc_to_fdc[usda_desc]
            print(f'    "{key}": {fdc_id},')
        else:
            print(f'    "{key}": None,')
    print("}")


if __name__ == "__main__":
    main()
