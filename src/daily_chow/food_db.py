"""Food database for Daily Chow.

Each FoodEntry maps to a USDA Foundation Food via usda_fdc_id. For foods
without a USDA match, manual macro values are provided as fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class FoodEntry:
    key: str
    name: str
    category: str
    unit_note: str = ""
    default_min: int = 0
    default_max: int = 500
    usda_fdc_id: int | None = None
    # Fallback macros for foods without USDA data (per 100g)
    manual_cal: float | None = None
    manual_protein: float | None = None
    manual_fat: float | None = None
    manual_carbs: float | None = None
    manual_fiber: float | None = None
    # Fallback micros for foods without USDA Foundation Foods data (per 100g)
    manual_micros: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Food:
    """Resolved food with all nutrition data (built by usda.py loader)."""

    name: str
    unit_note: str
    cal_per_100g: float
    protein_per_100g: float
    fat_per_100g: float
    carbs_per_100g: float
    fiber_per_100g: float
    category: str
    default_min: int = 0
    default_max: int = 500
    micros: dict[str, float] = field(default_factory=dict)


# ── Database ──────────────────────────────────────────────────────────

FOOD_ENTRIES: dict[str, FoodEntry] = {
    # ── Grains ────────────────────────────────────────────────────────
    "white_rice_dry": FoodEntry(
        key="white_rice_dry", name="White rice", category="grains",
        unit_note="dry", default_max=400, usda_fdc_id=2512381,
    ),
    "brown_rice_dry": FoodEntry(
        key="brown_rice_dry", name="Brown rice", category="grains",
        unit_note="dry", default_max=400, usda_fdc_id=2512380,
    ),
    "oats_dry": FoodEntry(
        key="oats_dry", name="Oats", category="grains",
        unit_note="dry", default_max=300, usda_fdc_id=2346396,
        manual_fiber=10.6,
    ),
    "quinoa_dry": FoodEntry(
        key="quinoa_dry", name="Quinoa", category="grains",
        unit_note="dry", default_max=300,
        manual_cal=368, manual_protein=14.1, manual_fat=6.1,
        manual_carbs=64.0, manual_fiber=7.0,
    ),
    "pasta_dry": FoodEntry(
        key="pasta_dry", name="Pasta", category="grains",
        unit_note="dry", default_max=400,
        manual_cal=371, manual_protein=13.0, manual_fat=1.5,
        manual_carbs=75.0, manual_fiber=1.8,
    ),
    "bread_whole_wheat": FoodEntry(
        key="bread_whole_wheat", name="Whole wheat bread", category="grains",
        unit_note="sliced", default_max=300, usda_fdc_id=335240,
    ),
    "corn_tortilla": FoodEntry(
        key="corn_tortilla", name="Corn tortilla", category="grains",
        default_max=300,
        manual_cal=218, manual_protein=5.7, manual_fat=2.8,
        manual_carbs=44.0, manual_fiber=5.2,
    ),
    "sweet_potato_raw": FoodEntry(
        key="sweet_potato_raw", name="Sweet potato", category="grains",
        unit_note="raw", default_max=500, usda_fdc_id=2346404,
        manual_fiber=3.0,
    ),
    "potato_raw": FoodEntry(
        key="potato_raw", name="Potato", category="grains",
        unit_note="raw", default_max=500, usda_fdc_id=2346401,
        manual_fiber=2.1,
    ),
    # ── Vegetables ────────────────────────────────────────────────────
    "broccoli_raw": FoodEntry(
        key="broccoli_raw", name="Broccoli", category="vegetables",
        unit_note="raw", default_max=400, usda_fdc_id=747447,
    ),
    "carrots_raw": FoodEntry(
        key="carrots_raw", name="Carrots", category="vegetables",
        unit_note="raw", default_max=300, usda_fdc_id=2258586,
    ),
    "zucchini_raw": FoodEntry(
        key="zucchini_raw", name="Zucchini", category="vegetables",
        unit_note="raw", default_max=500, usda_fdc_id=2685568,
    ),
    "spinach_raw": FoodEntry(
        key="spinach_raw", name="Spinach", category="vegetables",
        unit_note="raw", default_max=300, usda_fdc_id=1999633,
    ),
    "kale_raw": FoodEntry(
        key="kale_raw", name="Kale", category="vegetables",
        unit_note="raw", default_max=300, usda_fdc_id=323505,
    ),
    "bell_pepper_raw": FoodEntry(
        key="bell_pepper_raw", name="Bell pepper", category="vegetables",
        unit_note="raw", default_max=400, usda_fdc_id=2258590,
    ),
    "tomato_raw": FoodEntry(
        key="tomato_raw", name="Tomato", category="vegetables",
        unit_note="raw", default_max=500, usda_fdc_id=1999634,
    ),
    "onion_raw": FoodEntry(
        key="onion_raw", name="Onion", category="vegetables",
        unit_note="raw", default_max=300, usda_fdc_id=790646,
    ),
    "cauliflower_raw": FoodEntry(
        key="cauliflower_raw", name="Cauliflower", category="vegetables",
        unit_note="raw", default_max=400, usda_fdc_id=2685573,
    ),
    "cabbage_raw": FoodEntry(
        key="cabbage_raw", name="Cabbage", category="vegetables",
        unit_note="raw", default_max=400, usda_fdc_id=2346407,
        manual_fiber=2.5,
    ),
    "cucumber_raw": FoodEntry(
        key="cucumber_raw", name="Cucumber", category="vegetables",
        unit_note="raw", default_max=400, usda_fdc_id=2346406,
        manual_fiber=0.5,
    ),
    "mushrooms_raw": FoodEntry(
        key="mushrooms_raw", name="Mushrooms", category="vegetables",
        unit_note="raw", default_max=300, usda_fdc_id=1999629,
    ),
    "green_beans_raw": FoodEntry(
        key="green_beans_raw", name="Green beans", category="vegetables",
        unit_note="raw", default_max=400, usda_fdc_id=2346400,
    ),
    "asparagus_raw": FoodEntry(
        key="asparagus_raw", name="Asparagus", category="vegetables",
        unit_note="raw", default_max=400, usda_fdc_id=2710823,
    ),
    "brussels_sprouts_raw": FoodEntry(
        key="brussels_sprouts_raw", name="Brussels sprouts", category="vegetables",
        unit_note="raw", default_max=400, usda_fdc_id=2685575,
    ),
    # ── Legumes ───────────────────────────────────────────────────────
    "black_beans_cooked": FoodEntry(
        key="black_beans_cooked", name="Black beans", category="legumes",
        unit_note="cooked", default_max=400, usda_fdc_id=2644285,
        manual_fiber=8.7,
    ),
    "yellow_split_peas_dry": FoodEntry(
        key="yellow_split_peas_dry", name="Yellow split peas", category="legumes",
        unit_note="dry", default_max=150,
        manual_cal=352, manual_protein=24.0, manual_fat=1.2,
        manual_carbs=60.0, manual_fiber=25.0,
        # SR Legacy NDB 16085 — no Foundation Foods entry
        manual_micros={
            "calcium_mg": 55.0, "iron_mg": 4.43, "magnesium_mg": 115.0,
            "phosphorus_mg": 366.0, "potassium_mg": 981.0, "zinc_mg": 3.01,
            "copper_mg": 0.86, "manganese_mg": 1.21, "selenium_mcg": 1.6,
            "vitamin_c_mg": 1.8, "thiamin_mg": 0.73, "riboflavin_mg": 0.22,
            "niacin_mg": 2.89, "vitamin_b6_mg": 0.17, "folate_mcg": 274.0,
            "vitamin_b12_mcg": 0.0, "vitamin_a_mcg": 7.0, "vitamin_d_mcg": 0.0,
            "vitamin_e_mg": 0.39, "vitamin_k_mcg": 14.5,
        },
    ),
    "lentils_dry": FoodEntry(
        key="lentils_dry", name="Lentils", category="legumes",
        unit_note="dry", default_max=200, usda_fdc_id=2644283,
        manual_fiber=10.7,
    ),
    "chickpeas_cooked": FoodEntry(
        key="chickpeas_cooked", name="Chickpeas", category="legumes",
        unit_note="cooked", default_max=400, usda_fdc_id=2644288,
        manual_fiber=7.6,
    ),
    "kidney_beans_cooked": FoodEntry(
        key="kidney_beans_cooked", name="Kidney beans", category="legumes",
        unit_note="cooked", default_max=400, usda_fdc_id=2644289,
        manual_fiber=6.4,
    ),
    "pinto_beans_cooked": FoodEntry(
        key="pinto_beans_cooked", name="Pinto beans", category="legumes",
        unit_note="cooked", default_max=400, usda_fdc_id=2644292,
        manual_fiber=9.0,
    ),
    "edamame_shelled": FoodEntry(
        key="edamame_shelled", name="Edamame", category="legumes",
        unit_note="shelled", default_max=400,
        manual_cal=121, manual_protein=11.9, manual_fat=5.2,
        manual_carbs=8.9, manual_fiber=5.2,
    ),
    # ── Meats ─────────────────────────────────────────────────────────
    "ground_beef_80_20_raw": FoodEntry(
        key="ground_beef_80_20_raw", name="Ground beef 80/20", category="meats",
        unit_note="raw", default_max=1000, usda_fdc_id=2514744,
    ),
    "ground_beef_90_10_raw": FoodEntry(
        key="ground_beef_90_10_raw", name="Ground beef 90/10", category="meats",
        unit_note="raw", default_max=1000, usda_fdc_id=2514743,
    ),
    "chicken_thigh_raw": FoodEntry(
        key="chicken_thigh_raw", name="Chicken thigh", category="meats",
        unit_note="raw, boneless skinless", default_max=1000, usda_fdc_id=2646171,
    ),
    "chicken_breast_raw": FoodEntry(
        key="chicken_breast_raw", name="Chicken breast", category="meats",
        unit_note="raw, boneless skinless", default_max=1000, usda_fdc_id=2646170,
    ),
    "turkey_ground_93_raw": FoodEntry(
        key="turkey_ground_93_raw", name="Ground turkey 93/7", category="meats",
        unit_note="raw", default_max=1000, usda_fdc_id=2514747,
    ),
    "pork_loin_raw": FoodEntry(
        key="pork_loin_raw", name="Pork loin", category="meats",
        unit_note="raw", default_max=1000, usda_fdc_id=2646168,
    ),
    "pork_shoulder_raw": FoodEntry(
        key="pork_shoulder_raw", name="Pork shoulder", category="meats",
        unit_note="raw", default_max=1000,
        manual_cal=236, manual_protein=16.0, manual_fat=17.0,
        manual_carbs=0.0, manual_fiber=0.0,
    ),
    "steak_sirloin_raw": FoodEntry(
        key="steak_sirloin_raw", name="Sirloin steak", category="meats",
        unit_note="raw", default_max=1000, usda_fdc_id=2727574,
    ),
    # ── Seafood ───────────────────────────────────────────────────────
    "salmon_raw": FoodEntry(
        key="salmon_raw", name="Salmon", category="seafood",
        unit_note="raw, Atlantic", default_max=500, usda_fdc_id=2684441,
    ),
    "shrimp_raw": FoodEntry(
        key="shrimp_raw", name="Shrimp", category="seafood",
        unit_note="raw", default_max=500, usda_fdc_id=2684443,
    ),
    "tuna_canned": FoodEntry(
        key="tuna_canned", name="Tuna", category="seafood",
        unit_note="canned in water, drained", default_max=400, usda_fdc_id=334194,
    ),
    "tilapia_raw": FoodEntry(
        key="tilapia_raw", name="Tilapia", category="seafood",
        unit_note="raw", default_max=500, usda_fdc_id=2684442,
    ),
    "cod_raw": FoodEntry(
        key="cod_raw", name="Cod", category="seafood",
        unit_note="raw", default_max=500, usda_fdc_id=2684444,
    ),
    # ── Oils & Fats ───────────────────────────────────────────────────
    "avocado_oil": FoodEntry(
        key="avocado_oil", name="Avocado oil", category="oils_fats",
        default_max=100,
        manual_cal=884, manual_protein=0.0, manual_fat=100.0,
        manual_carbs=0.0, manual_fiber=0.0,
    ),
    "olive_oil": FoodEntry(
        key="olive_oil", name="Olive oil", category="oils_fats",
        default_max=100, usda_fdc_id=748608,
        # USDA entry has sparse nutrients; provide manual macros as fallback
        manual_cal=884, manual_protein=0.0, manual_fat=100.0,
        manual_carbs=0.0, manual_fiber=0.0,
    ),
    "coconut_oil": FoodEntry(
        key="coconut_oil", name="Coconut oil", category="oils_fats",
        default_max=100, usda_fdc_id=330458,
    ),
    "butter": FoodEntry(
        key="butter", name="Butter", category="oils_fats",
        default_max=100, usda_fdc_id=789828,
    ),
    # ── Dairy ─────────────────────────────────────────────────────────
    "whole_milk": FoodEntry(
        key="whole_milk", name="Whole milk", category="dairy",
        default_max=500, usda_fdc_id=746782,
    ),
    "greek_yogurt_whole": FoodEntry(
        key="greek_yogurt_whole", name="Greek yogurt (whole)", category="dairy",
        default_max=500, usda_fdc_id=2259794,
    ),
    "cottage_cheese": FoodEntry(
        key="cottage_cheese", name="Cottage cheese", category="dairy",
        unit_note="2% milkfat", default_max=500, usda_fdc_id=2346384,
    ),
    "cheddar_cheese": FoodEntry(
        key="cheddar_cheese", name="Cheddar cheese", category="dairy",
        default_max=200, usda_fdc_id=328637,
    ),
    "eggs_whole": FoodEntry(
        key="eggs_whole", name="Eggs", category="dairy",
        unit_note="whole, raw (~50g each)", default_max=400, usda_fdc_id=748967,
    ),
    # ── Nuts & Seeds ──────────────────────────────────────────────────
    "almonds": FoodEntry(
        key="almonds", name="Almonds", category="nuts_seeds",
        unit_note="raw", default_max=150, usda_fdc_id=2346393,
    ),
    "peanut_butter": FoodEntry(
        key="peanut_butter", name="Peanut butter", category="nuts_seeds",
        default_max=150, usda_fdc_id=2262072,
    ),
    "walnuts": FoodEntry(
        key="walnuts", name="Walnuts", category="nuts_seeds",
        unit_note="raw", default_max=150, usda_fdc_id=2346394,
    ),
    "chia_seeds": FoodEntry(
        key="chia_seeds", name="Chia seeds", category="nuts_seeds",
        default_max=100, usda_fdc_id=2710819,
        manual_fiber=34.4,
    ),
    "flax_seeds": FoodEntry(
        key="flax_seeds", name="Flax seeds", category="nuts_seeds",
        unit_note="ground", default_max=100, usda_fdc_id=2262075,
    ),
    "hemp_seeds": FoodEntry(
        key="hemp_seeds", name="Hemp seeds", category="nuts_seeds",
        unit_note="hulled", default_max=100,
        manual_cal=553, manual_protein=31.6, manual_fat=49.0,
        manual_carbs=2.8, manual_fiber=4.0,
    ),
    # ── Fruits ────────────────────────────────────────────────────────
    "banana": FoodEntry(
        key="banana", name="Banana", category="fruits",
        unit_note="raw", default_max=400, usda_fdc_id=1105314,
    ),
    "apple": FoodEntry(
        key="apple", name="Apple", category="fruits",
        unit_note="raw", default_max=400, usda_fdc_id=1750341,
    ),
    "blueberries": FoodEntry(
        key="blueberries", name="Blueberries", category="fruits",
        unit_note="raw", default_max=300, usda_fdc_id=2346411,
        manual_fiber=2.4,
    ),
    "avocado": FoodEntry(
        key="avocado", name="Avocado", category="fruits",
        unit_note="raw", default_max=300, usda_fdc_id=2710824,
        manual_fiber=6.7,
    ),
    "dates_medjool": FoodEntry(
        key="dates_medjool", name="Medjool dates", category="fruits",
        unit_note="pitted", default_max=200,
        manual_cal=277, manual_protein=1.8, manual_fat=0.2,
        manual_carbs=66.5, manual_fiber=6.7,
    ),
}


def search(query: str, limit: int = 10) -> list[tuple[str, FoodEntry]]:
    """Fuzzy-search food entries by name, unit note, or category."""
    q = query.lower().strip()
    if not q:
        return []

    prefix_matches: list[tuple[str, FoodEntry]] = []
    substring_matches: list[tuple[str, FoodEntry]] = []

    for key, entry in FOOD_ENTRIES.items():
        searchable = f"{entry.name} {entry.unit_note} {entry.category} {key}".lower()
        name_lower = entry.name.lower()
        if name_lower.startswith(q):
            prefix_matches.append((key, entry))
        elif q in searchable:
            substring_matches.append((key, entry))

    return (prefix_matches + substring_matches)[:limit]
