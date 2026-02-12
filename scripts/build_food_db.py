"""Build the unified food database from USDA FoodData Central exports.

Merges Foundation Foods (preferred) and SR Legacy (fallback) by NDB number,
extracts tracked nutrients, generates short names via Claude Code headless
mode (claude -p --model haiku), and outputs a compact JSON file for the app.

Usage:
    uv run scripts/build_food_db.py [--skip-names]

Expects raw USDA JSON files in ~/Downloads/:
    - FoodData_Central_foundation_food_json_2025-12-18.json
    - FoodData_Central_sr_legacy_food_json_2018-04.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

# -- Paths -----------------------------------------------------------------
DOWNLOADS = Path.home() / "Downloads"
FOUNDATION_PATH = DOWNLOADS / "FoodData_Central_foundation_food_json_2025-12-18.json"
SR_LEGACY_PATH = DOWNLOADS / "FoodData_Central_sr_legacy_food_json_2018-04.json"
OUTPUT = Path(__file__).resolve().parent.parent / "src" / "daily_chow" / "data" / "foods.json"
NAME_CACHE_PATH = Path(__file__).resolve().parent.parent / "src" / "daily_chow" / "data" / "name_cache.json"

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
    # Tier 3 - Fat-soluble vitamins
    1106,  # Vitamin A, RAE
    1114,  # Vitamin D (D2 + D3)
    1109,  # Vitamin E (alpha-tocopherol)
    1185,  # Vitamin K (phylloquinone)
}

# Categories to exclude — keep only whole/unprocessed foods
EXCLUDE_CATEGORIES: set[str] = {
    "Baby Foods",
    "Baked Products",
    "Beverages",
    "Breakfast Cereals",
    "Fast Foods",
    "Meals, Entrees, and Side Dishes",
    "Restaurant Foods",
    "Sausages and Luncheon Meats",
    "Snacks",
    "Soups, Sauces, and Gravies",
    "Sweets",
    "American Indian/Alaska Native Foods",
}

# Description substrings (lowercased) that indicate processed items within kept categories
# Note: USDA uses inverted format ("Milk shakes" not "milkshake", "Yogurt, frozen" not "frozen yogurt")
EXCLUDE_DESCRIPTION_PATTERNS: list[str] = [
    # Frozen/dessert dairy
    "ice cream", "ice milk", "yogurt, frozen", "milk shake", "sherbet",
    "dessert topping", "whipped topping", "milk dessert",
    "dulce de leche", "creamsicle",
    # Imitation / substitute / filled
    ", imitation", "substitute", "milk, filled",
    # Processed cheese products
    "cheese food", "cheese spread", "cheese sauce", "cheez whiz", "velveeta",
    "kraft free", "parmesan topping",
    # Supplements / powdered drinks
    "muscle milk", "instant breakfast", "nutritional supplement",
    "eggnog", "hot cocoa",
    # Other
    "milk, human", "sour dressing",
]


def _is_excluded_by_description(description: str) -> bool:
    """Check if a food should be excluded based on its description."""
    desc_lower = description.lower()
    return any(pat in desc_lower for pat in EXCLUDE_DESCRIPTION_PATTERNS)


def _extract_nutrients(food_nutrients: list[dict]) -> dict[str, float]:
    """Extract tracked nutrient values from a USDA foodNutrients array."""
    nutrients: dict[str, float] = {}
    for fn in food_nutrients:
        nid = fn.get("nutrient", {}).get("id")
        if nid in KEEP_NUTRIENT_IDS and "amount" in fn:
            nutrients[str(nid)] = fn["amount"]
    return nutrients


def _parse_food(food: dict) -> dict:
    """Parse a single USDA food entry into our compact format."""
    return {
        "fdc_id": food["fdcId"],
        "ndb_number": food.get("ndbNumber"),
        "description": food["description"],
        "category": food.get("foodCategory", {}).get("description", ""),
        "nutrients": _extract_nutrients(food.get("foodNutrients", [])),
    }


def load_foundation(path: Path) -> dict[int, dict]:
    """Load Foundation Foods, keyed by NDB number."""
    print(f"Reading Foundation Foods: {path}  ({path.stat().st_size / 1_048_576:.1f} MB)")
    with open(path) as f:
        raw = json.load(f)

    foods: dict[int, dict] = {}
    for food in raw["FoundationFoods"]:
        parsed = _parse_food(food)
        ndb = parsed["ndb_number"]
        if ndb is not None:
            foods[ndb] = parsed
        else:
            # Use fdc_id as key for foods without NDB number
            foods[-parsed["fdc_id"]] = parsed

    print(f"  Loaded {len(foods)} Foundation Foods")
    return foods


def load_sr_legacy(path: Path) -> dict[int, dict]:
    """Load SR Legacy Foods, keyed by NDB number."""
    print(f"Reading SR Legacy: {path}  ({path.stat().st_size / 1_048_576:.1f} MB)")
    with open(path) as f:
        raw = json.load(f)

    foods: dict[int, dict] = {}
    for food in raw["SRLegacyFoods"]:
        parsed = _parse_food(food)
        ndb = parsed["ndb_number"]
        if ndb is not None:
            foods[ndb] = parsed
        else:
            foods[-parsed["fdc_id"]] = parsed

    print(f"  Loaded {len(foods)} SR Legacy Foods")
    return foods


def merge_foods(foundation: dict[int, dict], sr_legacy: dict[int, dict]) -> dict[int, dict]:
    """Merge datasets: Foundation preferred, SR Legacy fallback."""
    merged: dict[int, dict] = {}
    foundation_kept = 0
    sr_only = 0

    # Start with all Foundation foods
    for ndb, food in foundation.items():
        merged[food["fdc_id"]] = food
        foundation_kept += 1

    # Add SR Legacy foods that aren't in Foundation
    for ndb, food in sr_legacy.items():
        if ndb not in foundation:
            merged[food["fdc_id"]] = food
            sr_only += 1

    print(f"\n  Merged: {foundation_kept} Foundation + {sr_only} SR Legacy-only = {len(merged)} total")

    # Filter out excluded categories
    before = len(merged)
    merged = {fdc_id: f for fdc_id, f in merged.items() if f["category"] not in EXCLUDE_CATEGORIES}
    cat_excluded = before - len(merged)
    if cat_excluded:
        print(f"  Excluded {cat_excluded} foods by category")

    # Filter out processed items by description
    before = len(merged)
    merged = {fdc_id: f for fdc_id, f in merged.items() if not _is_excluded_by_description(f["description"])}
    desc_excluded = before - len(merged)
    if desc_excluded:
        print(f"  Excluded {desc_excluded} foods by description pattern")

    return merged


def _call_haiku(prompt: str) -> str:
    """Call Claude Haiku via Claude Code headless mode."""
    result = subprocess.run(
        ["claude", "-p", "--model", "haiku"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr}")
    return result.stdout.strip()


def generate_names(foods: dict[int, dict], cache_path: Path, skip: bool = False) -> dict[str, dict[str, str]]:
    """Generate short names via Claude Haiku, with caching.

    Returns dict keyed by fdc_id (str) -> {"name": ..., "subtitle": ...}
    """
    # Load existing cache
    cache: dict[str, dict[str, str]] = {}
    if cache_path.exists():
        with open(cache_path) as f:
            cache = json.load(f)
        print(f"\n  Name cache: {len(cache)} entries loaded")

    if skip:
        # Fill missing entries with simple fallback
        for fdc_id, food in foods.items():
            key = str(fdc_id)
            if key not in cache:
                desc = food["description"]
                cache[key] = {"name": desc, "subtitle": ""}
        return cache

    # Find foods that need names
    needs_names: list[tuple[int, str]] = []
    for fdc_id, food in foods.items():
        if str(fdc_id) not in cache:
            needs_names.append((fdc_id, food["description"]))

    if not needs_names:
        print("  All foods already have cached names")
        return cache

    print(f"  Generating names for {len(needs_names)} foods via Haiku...")

    batch_size = 50
    processed = 0

    for i in range(0, len(needs_names), batch_size):
        batch = needs_names[i : i + batch_size]
        lines = [f"{fdc_id}|{desc}" for fdc_id, desc in batch]
        prompt_text = "\n".join(lines)

        prompt = f"""For each USDA food description below, generate a short display name and subtitle.

Rules:
- The name should be natural English, not inverted USDA style (e.g. "Avocado oil" not "Oil, avocado")
- Keep the name short (1-4 words). It should identify the food clearly.
- The subtitle should contain key qualifiers like preparation state (raw/cooked/dry), variety, or other distinguishing info. Keep it brief.
- If the description is already short and natural, use it as-is with empty subtitle.

Respond with ONLY a JSON array of objects, one per input line, in the same order:
[{{"fdc_id": 123, "name": "Short Name", "subtitle": "qualifier"}}]

Input (fdc_id|description):
{prompt_text}"""

        try:
            response_text = _call_haiku(prompt)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f"  WARNING: Haiku call failed for batch {i // batch_size + 1}: {e}")
            for fdc_id, desc in batch:
                if str(fdc_id) not in cache:
                    cache[str(fdc_id)] = {"name": desc, "subtitle": ""}
            processed += len(batch)
            continue

        # Handle markdown code blocks
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1]
            if response_text.endswith("```"):
                response_text = response_text[: -len("```")]
            response_text = response_text.strip()

        try:
            results = json.loads(response_text)
            for item in results:
                cache[str(item["fdc_id"])] = {
                    "name": item["name"],
                    "subtitle": item.get("subtitle", ""),
                }
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  WARNING: Failed to parse batch {i // batch_size + 1}: {e}")
            # Fall back to raw descriptions for this batch
            for fdc_id, desc in batch:
                if str(fdc_id) not in cache:
                    cache[str(fdc_id)] = {"name": desc, "subtitle": ""}

        processed += len(batch)
        if processed % 500 == 0 or processed == len(needs_names):
            print(f"    {processed}/{len(needs_names)} done")

        # Save cache after each batch (resume-friendly)
        with open(cache_path, "w") as f:
            json.dump(cache, f, indent=2)

    return cache


def build_output(foods: dict[int, dict], names: dict[str, dict[str, str]]) -> list[dict]:
    """Build the final output list."""
    output: list[dict] = []
    for fdc_id, food in foods.items():
        key = str(fdc_id)
        name_entry = names.get(key, {"name": food["description"], "subtitle": ""})
        output.append(
            {
                "fdc_id": fdc_id,
                "name": name_entry["name"],
                "subtitle": name_entry.get("subtitle", ""),
                "usda_description": food["description"],
                "category": food["category"],
                "nutrients": food["nutrients"],
            }
        )

    # Sort by name for stable output
    output.sort(key=lambda f: f["name"].lower())
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build food database from USDA data")
    parser.add_argument("--skip-names", action="store_true", help="Skip Haiku name generation (use raw descriptions)")
    args = parser.parse_args()

    foundation = load_foundation(FOUNDATION_PATH)
    sr_legacy = load_sr_legacy(SR_LEGACY_PATH)
    merged = merge_foods(foundation, sr_legacy)

    names = generate_names(merged, NAME_CACHE_PATH, skip=args.skip_names)

    output = build_output(merged, names)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    file_size = OUTPUT.stat().st_size
    total_nutrients = sum(len(f["nutrients"]) for f in output)
    avg_nutrients = total_nutrients / len(output) if output else 0

    print()
    print("=== Summary ===")
    print(f"  Total foods:            {len(output)}")
    print(f"  Avg nutrients per food: {avg_nutrients:.1f}")
    print(f"  Output file:            {OUTPUT}")
    print(f"  Output size:            {file_size:,} bytes ({file_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
