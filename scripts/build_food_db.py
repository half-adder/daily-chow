# /// script
# requires-python = ">=3.11"
# dependencies = ["rich"]
# ///
"""Build the unified food database from USDA FoodData Central exports.

Merges Foundation Foods (preferred) and SR Legacy (fallback) by NDB number,
extracts tracked nutrients, generates short names via Claude Code headless
mode (claude -p --model haiku), and outputs a compact JSON file for the app.

Usage:
    uv run scripts/build_food_db.py [--skip-names] [--skip-commonness] [--skip-groups]

Expects raw USDA JSON files in ~/Downloads/:
    - FoodData_Central_foundation_food_json_2025-12-18.json
    - FoodData_Central_sr_legacy_food_json_2018-04.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn

console = Console()

# -- Paths -----------------------------------------------------------------
DOWNLOADS = Path.home() / "Downloads"
FOUNDATION_PATH = DOWNLOADS / "FoodData_Central_foundation_food_json_2025-12-18.json"
SR_LEGACY_PATH = DOWNLOADS / "FoodData_Central_sr_legacy_food_json_2018-04.json"
OUTPUT = Path(__file__).resolve().parent.parent / "src" / "daily_chow" / "data" / "foods.json"
NAME_CACHE_PATH = Path(__file__).resolve().parent.parent / "src" / "daily_chow" / "data" / "name_cache.json"
COMMONNESS_CACHE_PATH = Path(__file__).resolve().parent.parent / "src" / "daily_chow" / "data" / "commonness_cache.json"
GROUP_CACHE_PATH = Path(__file__).resolve().parent.parent / "src" / "daily_chow" / "data" / "group_cache.json"
PORTION_CACHE_PATH = Path(__file__).resolve().parent.parent / "src" / "daily_chow" / "data" / "portion_cache.json"

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
    "Spices and Herbs",
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
    # Baking ingredients — not direct meal ingredients
    "flour",
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


def _extract_portions(food_portions: list[dict]) -> list[dict]:
    """Extract portion data from a USDA foodPortions array."""
    portions: list[dict] = []
    for fp in food_portions:
        modifier = fp.get("modifier", "")
        gram_weight = fp.get("gramWeight")
        amount = fp.get("amount")
        if modifier and gram_weight and amount:
            portions.append({
                "amount": amount,
                "modifier": modifier,
                "g": gram_weight,
            })
    return portions


def _parse_food(food: dict) -> dict:
    """Parse a single USDA food entry into our compact format."""
    parsed = {
        "fdc_id": food["fdcId"],
        "ndb_number": food.get("ndbNumber"),
        "description": food["description"],
        "category": food.get("foodCategory", {}).get("description", ""),
        "nutrients": _extract_nutrients(food.get("foodNutrients", [])),
    }
    portions = _extract_portions(food.get("foodPortions", []))
    if portions:
        parsed["portions"] = portions
    return parsed


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


def _backfill_nutrients(foundation_food: dict, sr_food: dict) -> int:
    """Copy missing nutrients from SR Legacy into a Foundation food entry.

    Only backfills nutrients in KEEP_NUTRIENT_IDS that Foundation is missing.
    Returns the number of nutrients added.
    """
    added = 0
    for nid, amount in sr_food["nutrients"].items():
        if nid not in foundation_food["nutrients"] and int(nid) in KEEP_NUTRIENT_IDS:
            foundation_food["nutrients"][nid] = amount
            added += 1
    return added


def merge_foods(foundation: dict[int, dict], sr_legacy: dict[int, dict]) -> dict[int, dict]:
    """Merge datasets: Foundation preferred, SR Legacy fallback for missing nutrients."""
    merged: dict[int, dict] = {}
    foundation_kept = 0
    sr_only = 0
    backfill_foods = 0
    backfill_nutrients = 0

    # Start with all Foundation foods, backfilling missing nutrients and portions from SR Legacy
    for ndb, food in foundation.items():
        if ndb in sr_legacy:
            added = _backfill_nutrients(food, sr_legacy[ndb])
            if added:
                backfill_foods += 1
                backfill_nutrients += added
            # Backfill portions from SR Legacy (Foundation portions are mostly RACC)
            if "portions" not in food and "portions" in sr_legacy[ndb]:
                food["portions"] = sr_legacy[ndb]["portions"]
        merged[food["fdc_id"]] = food
        foundation_kept += 1

    # Add SR Legacy foods that aren't in Foundation
    for ndb, food in sr_legacy.items():
        if ndb not in foundation:
            merged[food["fdc_id"]] = food
            sr_only += 1

    print(f"\n  Merged: {foundation_kept} Foundation + {sr_only} SR Legacy-only = {len(merged)} total")
    if backfill_foods:
        print(f"  Backfilled {backfill_nutrients} nutrients across {backfill_foods} Foundation foods from SR Legacy")

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
    import os
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    result = subprocess.run(
        ["claude", "-p", "--model", "haiku"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr}")
    return result.stdout.strip()


def _extract_json(text: str) -> str:
    """Extract a JSON object or array from text that may contain surrounding prose."""
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    # Try parsing as-is first
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Find the outermost { ... } or [ ... ]
    for open_ch, close_ch in [("{", "}"), ("[", "]")]:
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue

    return text


def generate_names(foods: dict[int, dict], cache_path: Path, skip: bool = False) -> dict[str, dict[str, str]]:
    """Generate short names via Claude Haiku, with caching.

    Returns dict keyed by fdc_id (str) -> {"name": ..., "subtitle": ...}
    """
    cache: dict[str, dict[str, str]] = {}
    if cache_path.exists():
        with open(cache_path) as f:
            cache = json.load(f)
        print(f"\n  Name cache: {len(cache)} entries loaded")

    if skip:
        for fdc_id, food in foods.items():
            key = str(fdc_id)
            if key not in cache:
                cache[key] = {"name": food["description"], "subtitle": ""}
        return cache

    needs_names: list[tuple[int, str]] = []
    for fdc_id, food in foods.items():
        if str(fdc_id) not in cache:
            needs_names.append((fdc_id, food["description"]))

    if not needs_names:
        print("  All foods already have cached names")
        return cache

    print(f"  Generating names for {len(needs_names)} foods via Haiku...")

    batch_size = 50
    max_workers = 10
    lock = threading.Lock()
    processed = 0
    errors = 0

    def _make_prompt(batch: list[tuple[int, str]]) -> str:
        lines = [f"{fdc_id}|{desc}" for fdc_id, desc in batch]
        prompt_text = "\n".join(lines)
        return f"""For each USDA food description below, generate a short display name and subtitle.

Rules:
- The name should be natural English, not inverted USDA style (e.g. "Avocado oil" not "Oil, avocado")
- Keep the name short (1-4 words). It should identify the food clearly.
- The subtitle should contain key qualifiers like preparation state (raw/cooked/dry), variety, or other distinguishing info. Keep it brief.
- If the description is already short and natural, use it as-is with empty subtitle.

Respond with ONLY a JSON array of objects, one per input line, in the same order:
[{{"fdc_id": 123, "name": "Short Name", "subtitle": "qualifier"}}]

Input (fdc_id|description):
{prompt_text}"""

    batches = [needs_names[i : i + batch_size] for i in range(0, len(needs_names), batch_size)]

    def _process_batch(
        batch: list[tuple[int, str]],
        progress: Progress,
        task_id: int,
    ) -> None:
        nonlocal processed, errors
        prompt = _make_prompt(batch)

        try:
            response_text = _call_haiku(prompt)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            with lock:
                errors += 1
                for fdc_id, desc in batch:
                    if str(fdc_id) not in cache:
                        cache[str(fdc_id)] = {"name": desc, "subtitle": ""}
                processed += len(batch)
                progress.update(task_id, advance=len(batch), description=f"[red]Error: {e!s:.40s}")
            return

        extracted = _extract_json(response_text)
        with lock:
            try:
                results = json.loads(extracted)
                sample_name = None
                for item in results:
                    cache[str(item["fdc_id"])] = {
                        "name": item["name"],
                        "subtitle": item.get("subtitle", ""),
                    }
                    if sample_name is None:
                        sample_name = item["name"]
                progress.update(task_id, advance=len(batch), description=f"[cyan]{sample_name}" if sample_name else "OK")
            except (json.JSONDecodeError, KeyError):
                errors += 1
                for fdc_id, desc in batch:
                    if str(fdc_id) not in cache:
                        cache[str(fdc_id)] = {"name": desc, "subtitle": ""}
                progress.update(task_id, advance=len(batch), description="[red]Parse error")

            processed += len(batch)
            if processed % (batch_size * 50) == 0 or processed == len(needs_names):
                with open(cache_path, "w") as f:
                    json.dump(cache, f, indent=2)

    console.print(f"  Running [bold]{len(batches)}[/bold] batches with [bold]{max_workers}[/bold] parallel workers")
    with Progress(
        TextColumn("[progress.description]{task.description}", justify="right"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Starting...", total=len(needs_names))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_process_batch, batch, progress, task_id): idx for idx, batch in enumerate(batches)}
            for future in as_completed(futures):
                future.result()

    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)

    if errors:
        console.print(f"  [yellow]⚠ {errors} batches fell back to raw description[/yellow]")
    console.print(f"  [green]✓ {len(cache)} names cached[/green]")

    return cache


def generate_commonness(foods: dict[int, dict], cache_path: Path, skip: bool = False) -> dict[str, int]:
    """Generate commonness scores (1-5) via Claude Haiku, with caching.

    Returns dict keyed by fdc_id (str) -> int score.
    """
    cache: dict[str, int] = {}
    if cache_path.exists():
        with open(cache_path) as f:
            cache = json.load(f)
        print(f"\n  Commonness cache: {len(cache)} entries loaded")

    if skip:
        for fdc_id in foods:
            key = str(fdc_id)
            if key not in cache:
                cache[key] = 3
        return cache

    needs_scores: list[tuple[int, str]] = []
    for fdc_id, food in foods.items():
        if str(fdc_id) not in cache:
            needs_scores.append((fdc_id, food["description"]))

    if not needs_scores:
        print("  All foods already have cached commonness scores")
        return cache

    print(f"  Generating commonness scores for {len(needs_scores)} foods via Haiku...")

    batch_size = 5
    max_workers = 10
    lock = threading.Lock()
    processed = 0
    errors = 0

    def _make_prompt(batch: list[tuple[int, str]]) -> str:
        lines = [f"{fdc_id}|{desc}" for fdc_id, desc in batch]
        prompt_text = "\n".join(lines)
        return f"""Output ONLY a JSON object. No explanation, no markdown, no text before or after.

Rate each food on how commonly a typical US grocery shopper would buy it (1-5).
Score the SPECIFIC form described, not the base ingredient:
5 = everyday staple in its common form (whole eggs, whole milk, raw chicken breast, white rice, fresh bananas)
4 = common (salmon fillet, sweet potatoes, Greek yogurt, rolled oats)
3 = moderately common (lamb, beets, mango, quinoa)
2 = uncommon (rabbit, jicama, teff, duck, frozen pasteurized eggs)
1 = specialty/obscure (dried egg powder, dehydrated onion flakes, game meats, canned frog legs)

Key: frozen, canned, dried, dehydrated, powdered, freeze-dried, and other processed/preserved forms score LOWER than their fresh/whole counterparts. "Egg, whole, raw, frozen" is NOT the same as fresh eggs.
Descriptions use USDA inverted format ("Cheese, cheddar" means cheddar cheese).

Input (fdc_id|description):
{prompt_text}

Output a JSON object mapping each fdc_id to its integer score, nothing else: {{"fdc_id": score, ...}}"""

    batches = [needs_scores[i : i + batch_size] for i in range(0, len(needs_scores), batch_size)]

    def _process_batch(
        batch: list[tuple[int, str]],
        progress: Progress,
        task_id: int,
    ) -> None:
        nonlocal processed, errors
        prompt = _make_prompt(batch)
        batch_lookup = {str(fdc_id): desc for fdc_id, desc in batch}

        try:
            response_text = _call_haiku(prompt)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            with lock:
                errors += 1
                for fdc_id, _ in batch:
                    if str(fdc_id) not in cache:
                        cache[str(fdc_id)] = 3
                processed += len(batch)
                progress.update(task_id, advance=len(batch), description=f"[red]Error: {e!s:.40s}")
            return

        extracted = _extract_json(response_text)
        with lock:
            try:
                results = json.loads(extracted)
                sample_desc = None
                for fdc_id_str, score in results.items():
                    clamped = max(1, min(5, int(score)))
                    cache[fdc_id_str] = clamped
                    if sample_desc is None:
                        sample_desc = f"{batch_lookup.get(fdc_id_str, '?')} → [cyan]{clamped}"
                if len(results) < len(batch):
                    for fdc_id, _ in batch:
                        if str(fdc_id) not in cache:
                            cache[str(fdc_id)] = 3
                progress.update(task_id, advance=len(batch), description=sample_desc or "OK")
            except (json.JSONDecodeError, ValueError, TypeError):
                errors += 1
                for fdc_id, _ in batch:
                    if str(fdc_id) not in cache:
                        cache[str(fdc_id)] = 3
                progress.update(task_id, advance=len(batch), description="[red]Parse error")

            processed += len(batch)
            if processed % (batch_size * 50) == 0 or processed == len(needs_scores):
                with open(cache_path, "w") as f:
                    json.dump(cache, f, indent=2)

    console.print(f"  Running [bold]{len(batches)}[/bold] batches with [bold]{max_workers}[/bold] parallel workers")
    with Progress(
        TextColumn("[progress.description]{task.description}", justify="right"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Starting...", total=len(needs_scores))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_process_batch, batch, progress, task_id): idx for idx, batch in enumerate(batches)}
            for future in as_completed(futures):
                future.result()

    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)

    if errors:
        console.print(f"  [yellow]⚠ {errors} batches fell back to score 3[/yellow]")
    console.print(f"  [green]✓ {len(cache)} commonness scores cached[/green]")

    return cache


def generate_groups(
    foods: dict[int, dict],
    names: dict[str, dict[str, str]],
    cache_path: Path,
    skip: bool = False,
) -> dict[str, str]:
    """Generate canonical group names via Claude Haiku, with caching.

    Returns dict keyed by fdc_id (str) -> group name string.
    """
    cache: dict[str, str] = {}
    if cache_path.exists():
        with open(cache_path) as f:
            cache = json.load(f)
        print(f"\n  Group cache: {len(cache)} entries loaded")

    if skip:
        for fdc_id in foods:
            key = str(fdc_id)
            if key not in cache:
                name_entry = names.get(key, {"name": foods[fdc_id]["description"]})
                cache[key] = name_entry.get("name", foods[fdc_id]["description"])
        return cache

    needs_groups: list[tuple[int, str, str, str]] = []
    for fdc_id, food in foods.items():
        if str(fdc_id) not in cache:
            name_entry = names.get(str(fdc_id), {"name": food["description"], "subtitle": ""})
            needs_groups.append((
                fdc_id,
                name_entry.get("name", food["description"]),
                name_entry.get("subtitle", ""),
                food["description"],
            ))

    if not needs_groups:
        print("  All foods already have cached group names")
        return cache

    print(f"  Generating group names for {len(needs_groups)} foods via Haiku...")

    batch_size = 5
    max_workers = 10
    lock = threading.Lock()
    processed = 0

    def _make_prompt(batch: list[tuple[int, str, str, str]]) -> str:
        lines = [f"{fdc_id}|{name}|{subtitle}|{usda_desc}" for fdc_id, name, subtitle, usda_desc in batch]
        prompt_text = "\n".join(lines)
        return f"""Output ONLY a JSON object. No explanation, no markdown, no text before or after.

Assign each food a canonical group name for clustering variants in a grocery app.

The group name should answer: "If a shopper wanted THIS ingredient, what would they search for?"

Rules:
- Group foods that a meal planner would consider interchangeable options
- Group all cuts of the same animal together (chicken breast + chicken thigh + whole chicken → "Chicken")
- Group all varieties of the same dairy/grain/vegetable together (cheddar + swiss + mozzarella → "Cheese")
- Keep different species/sources SEPARATE (cow milk ≠ coconut milk ≠ soy milk)
- Keep genuinely different products SEPARATE (chocolate milk ≠ plain milk, butter ≠ cheese)
- The group name should be 1-3 words, natural English, no brand names
- Think: "what section of a grocery list would this go under?"

Examples:
  "Nonfat Milk, fortified" → "Milk"
  "2% Milk, reduced fat" → "Milk"
  "Whole Milk, 3.25% fat" → "Milk"
  "Chocolate Milk, lowfat" → "Chocolate Milk"
  "Coconut Milk, canned" → "Coconut Milk"
  "Soymilk, original" → "Soy Milk"
  "SILK Soymilk, vanilla" → "Soy Milk"
  "Chicken Breast, raw" → "Chicken"
  "Chicken Thigh, roasted" → "Chicken"
  "Whole Chicken, raw" → "Chicken"
  "Ground Beef, 80% lean" → "Beef"
  "Beef Round, roasted" → "Beef"
  "Beef Rib Eye, grilled" → "Beef"
  "Ham, extra lean, roasted" → "Ham"
  "Ham, canned" → "Ham"
  "Greek Yogurt, plain" → "Yogurt"
  "Greek Yogurt, strawberry" → "Yogurt"
  "Cheddar Cheese" → "Cheese"
  "Swiss Cheese" → "Cheese"
  "Mozzarella" → "Cheese"
  "Cream Cheese" → "Cream Cheese"
  "Sweet Corn, canned" → "Sweet Corn"
  "Sweet Corn, frozen" → "Sweet Corn"
  "Atlantic Salmon, raw" → "Salmon"
  "Sockeye Salmon, canned" → "Salmon"
  "Lamb Shoulder, roasted" → "Lamb"
  "Lamb Leg, braised" → "Lamb"

Input (fdc_id|name|subtitle|usda_description):
{prompt_text}

Output ONLY a JSON object mapping each fdc_id to its group name string: {{"fdc_id": "Group Name", ...}}"""

    batches = [needs_groups[i : i + batch_size] for i in range(0, len(needs_groups), batch_size)]
    total_batches = len(batches)
    errors = 0

    def _process_batch(
        batch_idx: int,
        batch: list[tuple[int, str, str, str]],
        progress: Progress,
        task_id: int,
    ) -> None:
        nonlocal processed, errors
        prompt = _make_prompt(batch)
        batch_lookup = {str(fdc_id): name for fdc_id, name, _, _ in batch}

        try:
            response_text = _call_haiku(prompt)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            with lock:
                errors += 1
                for fdc_id, name, _, _ in batch:
                    if str(fdc_id) not in cache:
                        cache[str(fdc_id)] = name
                processed += len(batch)
                progress.update(task_id, advance=len(batch), description=f"[red]Error: {e!s:.40s}")
            return

        extracted = _extract_json(response_text)
        with lock:
            try:
                results = json.loads(extracted)
                for fdc_id_str, group_name in results.items():
                    cache[fdc_id_str] = str(group_name).strip()
                if len(results) < len(batch):
                    for fdc_id, name, _, _ in batch:
                        if str(fdc_id) not in cache:
                            cache[str(fdc_id)] = name
                # Show a sample from this batch in the progress description
                sample = next(iter(results.items()), None)
                if sample:
                    desc = batch_lookup.get(sample[0], "?")
                    progress.update(task_id, advance=len(batch), description=f"{desc} → [cyan]{sample[1]}")
                else:
                    progress.update(task_id, advance=len(batch))
            except (json.JSONDecodeError, ValueError, TypeError):
                errors += 1
                for fdc_id, name, _, _ in batch:
                    if str(fdc_id) not in cache:
                        cache[str(fdc_id)] = name
                progress.update(task_id, advance=len(batch), description="[red]Parse error")

            processed += len(batch)

            # Save cache every 50 batches
            if processed % (batch_size * 50) == 0 or processed == len(needs_groups):
                with open(cache_path, "w") as f:
                    json.dump(cache, f, indent=2)

    console.print(f"  Running [bold]{total_batches}[/bold] batches with [bold]{max_workers}[/bold] parallel workers")
    with Progress(
        TextColumn("[progress.description]{task.description}", justify="right"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Starting...", total=len(needs_groups))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_process_batch, idx, batch, progress, task_id): idx
                for idx, batch in enumerate(batches)
            }
            for future in as_completed(futures):
                future.result()  # propagate exceptions

    # Final save
    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)

    if errors:
        console.print(f"  [yellow]⚠ {errors} batches fell back to food name[/yellow]")
    console.print(f"  [green]✓ {len(cache)} groups cached[/green]")

    return cache


def generate_portions(
    foods: dict[int, dict],
    names: dict[str, dict[str, str]],
    cache_path: Path,
    skip: bool = False,
) -> dict[str, dict]:
    """Generate grocery-friendly portion units via Claude Haiku, with caching.

    Uses USDA portion data as grounding, then asks Haiku to pick the best
    grocery-shopping unit and clean up the modifier text.

    Returns dict keyed by fdc_id (str) -> {"unit": str, "g": float} or None.
    """
    cache: dict[str, dict | None] = {}
    if cache_path.exists():
        with open(cache_path) as f:
            cache = json.load(f)
        print(f"\n  Portion cache: {len(cache)} entries loaded")

    if skip:
        for fdc_id in foods:
            key = str(fdc_id)
            if key not in cache:
                cache[key] = None
        return cache

    needs_portions: list[tuple[int, str, str, list[dict]]] = []
    for fdc_id, food in foods.items():
        key = str(fdc_id)
        if key not in cache:
            name_entry = names.get(key, {"name": food["description"]})
            portions = food.get("portions", [])
            needs_portions.append((
                fdc_id,
                name_entry.get("name", food["description"]),
                food["description"],
                portions,
            ))

    if not needs_portions:
        print("  All foods already have cached portions")
        return cache

    print(f"  Generating portions for {len(needs_portions)} foods via Haiku...")

    batch_size = 20
    max_workers = 10
    lock = threading.Lock()
    processed = 0
    errors = 0

    def _make_prompt(batch: list[tuple[int, str, str, list[dict]]]) -> str:
        lines = []
        for fdc_id, name, usda_desc, portions in batch:
            if portions:
                portion_strs = [
                    f"{p['amount']} {p['modifier']} = {p['g']}g"
                    for p in portions
                ]
                lines.append(f"{fdc_id}|{name}|{usda_desc}|{'; '.join(portion_strs)}")
            else:
                lines.append(f"{fdc_id}|{name}|{usda_desc}|NO_PORTIONS")
        prompt_text = "\n".join(lines)
        return f"""Output ONLY a JSON object. No explanation, no markdown, no text before or after.

For each food, pick the single best grocery-shopping unit from the available USDA portions.
The gram weight MUST come from the USDA data provided. Do not invent gram weights.

Rules:
- Pick the unit a grocery shopper would use to buy this item
- Prefer natural counting units: "egg", "breast", "fillet", "banana", "slice" over "oz" or "cup" for countable items
- For liquids, prefer "cup" over "fl oz" or "tbsp"
- For bulk/dry goods (rice, oats, flour), prefer "cup"
- Clean up the modifier to a short, clean label (e.g., "breast, skin not eaten" -> "breast", "large (8\" to 8-7/8\" long)" -> "large", "cup, chopped" -> "cup")
- If the amount is not 1.0, normalize: e.g., "0.5 fillet = 154g" -> unit="fillet", g=308
- If a food has NO_PORTIONS or no useful grocery unit, output null for that food
- Skip "NLEA serving" units, they are not grocery-relevant

Output a JSON object mapping each fdc_id to either {{"unit": "clean label", "g": grams_per_one_unit}} or null:
{{"123": {{"unit": "large egg", "g": 50}}, "456": {{"unit": "cup", "g": 240}}, "789": null}}

Input (fdc_id|name|usda_description|portions):
{prompt_text}"""

    batches = [needs_portions[i : i + batch_size] for i in range(0, len(needs_portions), batch_size)]

    def _process_batch(
        batch: list[tuple[int, str, str, list[dict]]],
        progress: Progress,
        task_id: int,
    ) -> None:
        nonlocal processed, errors
        prompt = _make_prompt(batch)
        batch_lookup = {str(fdc_id): name for fdc_id, name, _, _ in batch}

        try:
            response_text = _call_haiku(prompt)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            with lock:
                errors += 1
                for fdc_id, _, _, _ in batch:
                    if str(fdc_id) not in cache:
                        cache[str(fdc_id)] = None
                processed += len(batch)
                progress.update(task_id, advance=len(batch), description=f"[red]Error: {e!s:.40s}")
            return

        extracted = _extract_json(response_text)
        with lock:
            try:
                results = json.loads(extracted)
                sample_desc = None
                for fdc_id_str, portion in results.items():
                    if portion is not None:
                        # Validate structure
                        if isinstance(portion, dict) and "unit" in portion and "g" in portion:
                            cache[fdc_id_str] = {"unit": str(portion["unit"]), "g": float(portion["g"])}
                        else:
                            cache[fdc_id_str] = None
                    else:
                        cache[fdc_id_str] = None
                    if sample_desc is None and cache.get(fdc_id_str) is not None:
                        sample_desc = f"{batch_lookup.get(fdc_id_str, '?')} -> [cyan]{cache[fdc_id_str]['unit']}"
                if len(results) < len(batch):
                    for fdc_id, _, _, _ in batch:
                        if str(fdc_id) not in cache:
                            cache[str(fdc_id)] = None
                progress.update(task_id, advance=len(batch), description=sample_desc or "OK")
            except (json.JSONDecodeError, ValueError, TypeError):
                errors += 1
                for fdc_id, _, _, _ in batch:
                    if str(fdc_id) not in cache:
                        cache[str(fdc_id)] = None
                progress.update(task_id, advance=len(batch), description="[red]Parse error")

            processed += len(batch)
            if processed % (batch_size * 50) == 0 or processed == len(needs_portions):
                with open(cache_path, "w") as f:
                    json.dump(cache, f, indent=2)

    console.print(f"  Running [bold]{len(batches)}[/bold] batches with [bold]{max_workers}[/bold] parallel workers")
    with Progress(
        TextColumn("[progress.description]{task.description}", justify="right"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Starting...", total=len(needs_portions))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_process_batch, batch, progress, task_id): idx for idx, batch in enumerate(batches)}
            for future in as_completed(futures):
                future.result()

    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)

    has_portion = sum(1 for v in cache.values() if v is not None)
    if errors:
        console.print(f"  [yellow]⚠ {errors} batches fell back to null[/yellow]")
    console.print(f"  [green]✓ {has_portion}/{len(cache)} foods have grocery portions[/green]")

    return cache


def build_output(foods: dict[int, dict], names: dict[str, dict[str, str]], commonness: dict[str, int] | None = None, groups: dict[str, str] | None = None, portions: dict[str, dict | None] | None = None) -> list[dict]:
    """Build the final output list."""
    output: list[dict] = []
    for fdc_id, food in foods.items():
        key = str(fdc_id)
        name_entry = names.get(key, {"name": food["description"], "subtitle": ""})
        entry = {
            "fdc_id": fdc_id,
            "name": name_entry["name"],
            "subtitle": name_entry.get("subtitle", ""),
            "usda_description": food["description"],
            "category": food["category"],
            "nutrients": food["nutrients"],
        }
        if commonness is not None:
            entry["commonness"] = commonness.get(key, 3)
        if groups is not None:
            entry["group"] = groups.get(key, name_entry["name"])
        if portions is not None:
            portion = portions.get(key)
            if portion is not None:
                entry["portion"] = portion
        output.append(entry)

    # Sort by name for stable output
    output.sort(key=lambda f: f["name"].lower())
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build food database from USDA data")
    parser.add_argument("--skip-names", action="store_true", help="Skip Haiku name generation (use raw descriptions)")
    parser.add_argument("--skip-commonness", action="store_true", help="Skip Haiku commonness score generation (default to 3)")
    parser.add_argument("--skip-groups", action="store_true", help="Skip Haiku group name generation (default to food name)")
    parser.add_argument("--skip-portions", action="store_true", help="Skip Haiku portion generation")
    args = parser.parse_args()

    foundation = load_foundation(FOUNDATION_PATH)
    sr_legacy = load_sr_legacy(SR_LEGACY_PATH)
    merged = merge_foods(foundation, sr_legacy)

    names = generate_names(merged, NAME_CACHE_PATH, skip=args.skip_names)
    commonness = generate_commonness(merged, COMMONNESS_CACHE_PATH, skip=args.skip_commonness)
    groups = generate_groups(merged, names, GROUP_CACHE_PATH, skip=args.skip_groups)
    portions = generate_portions(merged, names, PORTION_CACHE_PATH, skip=args.skip_portions)

    output = build_output(merged, names, commonness, groups, portions)

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
