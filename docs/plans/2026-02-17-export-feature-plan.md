# Export Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add markdown and PDF export of meal plans with nutrition dashboard and shopping list, generated server-side.

**Architecture:** New `src/daily_chow/export.py` module with functions for markdown and PDF generation. New `/api/export` POST endpoint in `api.py`. Frontend gets an Export button in the header that opens a popover with format/days/dashboard options, then fetches the file.

**Tech Stack:** Python (weasyprint for PDF, Jinja2 for HTML templating), SvelteKit frontend.

---

### Task 1: Add weasyprint and jinja2 dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add dependencies**

Add `weasyprint` and `jinja2` to the project dependencies in `pyproject.toml`:

```toml
dependencies = [
    "ortools>=9.15.6755",
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "weasyprint>=63.0",
    "jinja2>=3.1.0",
]
```

**Step 2: Install**

Run: `uv sync`

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add weasyprint and jinja2 dependencies for export"
```

---

### Task 2: Weight formatting utility + tests

**Files:**
- Create: `src/daily_chow/export.py`
- Create: `tests/test_export.py`

**Step 1: Write the failing tests**

In `tests/test_export.py`:

```python
from daily_chow.export import format_weight


def test_format_weight_small_grams():
    """Under 1000g: show grams + oz."""
    assert format_weight(200) == "200g (7.1 oz)"


def test_format_weight_large_grams():
    """1000g+: show grams + lbs."""
    assert format_weight(1400) == "1400g (3.1 lbs)"


def test_format_weight_exact_boundary():
    """Exactly 1000g uses lbs."""
    assert format_weight(1000) == "1000g (2.2 lbs)"


def test_format_weight_tiny():
    """Very small quantity."""
    assert format_weight(28) == "28g (1.0 oz)"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_export.py -v`
Expected: FAIL — `ImportError: cannot import name 'format_weight'`

**Step 3: Write minimal implementation**

In `src/daily_chow/export.py`:

```python
"""Export meal plans to Markdown and PDF."""

from __future__ import annotations


def format_weight(grams: float) -> str:
    """Format grams with imperial equivalent (oz < 1000g, lbs >= 1000g)."""
    g = round(grams)
    if g >= 1000:
        lbs = g / 453.6
        return f"{g}g ({lbs:.1f} lbs)"
    oz = g / 28.35
    return f"{g}g ({oz:.1f} oz)"
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_export.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add src/daily_chow/export.py tests/test_export.py
git commit -m "feat: add weight formatting utility for export"
```

---

### Task 3: Markdown export function + tests

**Files:**
- Modify: `src/daily_chow/export.py`
- Modify: `tests/test_export.py`

The markdown export function takes structured data and returns a markdown string. It needs:
- Header with date, profile, calorie target
- Daily totals table (calories, protein, fat, carbs, fiber)
- Ingredient table (name, weight, cal, pro, fat, carb, fiber)
- Shopping list grouped by category, scaled by num_days

**Step 1: Write the failing test**

Append to `tests/test_export.py`:

```python
from daily_chow.export import generate_markdown, ExportData, ExportIngredient


def test_markdown_has_header():
    data = ExportData(
        date="2026-02-17",
        sex="male",
        age_group="19-30",
        daily_cal=2000,
        total_calories=2000,
        total_protein=150,
        total_fat=67,
        total_carbs=200,
        total_fiber=35,
        ingredients=[
            ExportIngredient(
                name="Chicken Breast",
                subtitle="raw",
                category="Poultry Products",
                grams=200,
                calories=330,
                protein=62,
                fat=7,
                carbs=0,
                fiber=0,
            ),
        ],
        micros={},
        num_days=1,
    )
    md = generate_markdown(data)
    assert "# Daily Chow" in md
    assert "Male, 19-30" in md
    assert "2000 kcal" in md


def test_markdown_shopping_list_scales():
    data = ExportData(
        date="2026-02-17",
        sex="male",
        age_group="19-30",
        daily_cal=2000,
        total_calories=2000,
        total_protein=150,
        total_fat=67,
        total_carbs=200,
        total_fiber=35,
        ingredients=[
            ExportIngredient(
                name="Broccoli",
                subtitle="raw",
                category="Vegetables and Vegetable Products",
                grams=200,
                calories=68,
                protein=6,
                fat=1,
                carbs=14,
                fiber=5,
            ),
        ],
        micros={},
        num_days=7,
    )
    md = generate_markdown(data)
    # 200g * 7 = 1400g
    assert "1400g" in md
    assert "Shopping List (7 days)" in md
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_export.py::test_markdown_has_header -v`
Expected: FAIL — `ImportError`

**Step 3: Write implementation**

Add to `src/daily_chow/export.py`:

```python
from dataclasses import dataclass, field


@dataclass
class ExportIngredient:
    name: str
    subtitle: str
    category: str
    grams: float
    calories: float
    protein: float
    fat: float
    carbs: float
    fiber: float


@dataclass
class ExportMicro:
    name: str
    unit: str
    total: float
    dri: float
    pct: float


@dataclass
class ExportData:
    date: str
    sex: str
    age_group: str
    daily_cal: int
    total_calories: float
    total_protein: float
    total_fat: float
    total_carbs: float
    total_fiber: float
    ingredients: list[ExportIngredient]
    micros: dict[str, ExportMicro] = field(default_factory=dict)
    num_days: int = 1


def generate_markdown(data: ExportData) -> str:
    """Generate a markdown meal plan with shopping list."""
    lines: list[str] = []

    # Header
    sex_display = data.sex.title()
    lines.append(f"# Daily Chow — Meal Plan")
    lines.append(f"Generated: {data.date} | Profile: {sex_display}, {data.age_group} | {data.daily_cal} kcal target")
    lines.append("")

    # Daily totals
    lines.append("## Daily Totals")
    lines.append("| Calories | Protein | Fat | Carbs | Fiber |")
    lines.append("|----------|---------|-----|-------|-------|")
    lines.append(
        f"| {round(data.total_calories)} | {round(data.total_protein)}g "
        f"| {round(data.total_fat)}g | {round(data.total_carbs)}g "
        f"| {round(data.total_fiber)}g |"
    )
    lines.append("")

    # Ingredient table
    lines.append("## Ingredients")
    lines.append("| Ingredient | Weight | Cal | Pro | Fat | Carb | Fiber |")
    lines.append("|------------|--------|-----|-----|-----|------|-------|")
    for ing in data.ingredients:
        lines.append(
            f"| {ing.name} | {round(ing.grams)}g "
            f"| {round(ing.calories)} | {round(ing.protein)}g "
            f"| {round(ing.fat)}g | {round(ing.carbs)}g "
            f"| {round(ing.fiber)}g |"
        )
    lines.append("")

    # Micronutrient coverage (if any)
    if data.micros:
        lines.append("## Micronutrient Coverage")
        lines.append("| Nutrient | Amount | DRI | Coverage |")
        lines.append("|----------|--------|-----|----------|")
        for micro in data.micros.values():
            lines.append(
                f"| {micro.name} | {micro.total:.1f} {micro.unit} "
                f"| {micro.dri:.1f} {micro.unit} | {micro.pct:.0f}% |"
            )
        lines.append("")

    # Shopping list
    lines.append(f"## Shopping List ({data.num_days} day{'s' if data.num_days != 1 else ''})")

    # Group by category
    categories: dict[str, list[ExportIngredient]] = {}
    for ing in data.ingredients:
        categories.setdefault(ing.category, []).append(ing)

    for cat, items in sorted(categories.items()):
        lines.append(f"### {cat}")
        for ing in sorted(items, key=lambda i: i.name):
            total_g = ing.grams * data.num_days
            lines.append(f"- [ ] {ing.name} — {format_weight(total_g)}")
        lines.append("")

    return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_export.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add src/daily_chow/export.py tests/test_export.py
git commit -m "feat: add markdown export generation"
```

---

### Task 4: PDF HTML template

**Files:**
- Create: `src/daily_chow/templates/export.html`

This is a Jinja2 HTML template that weasyprint will render to PDF. It contains:
- Page 1 (optional): nutrition dashboard with macro bars, micro bars, ingredient table
- Page 2: shopping list with checkboxes

The template uses inline CSS for styling. Macro bars are CSS `<div>` elements with percentage widths using the same colors as the frontend (`#3b82f6`, `#ef4444`, `#22c55e`, `#f59e0b`, `#a855f7`, etc.).

**Step 1: Create the template**

Create `src/daily_chow/templates/export.html`:

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page { size: letter; margin: 0.75in; }
  body { font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; color: #1a1a1a; font-size: 10pt; line-height: 1.4; }
  h1 { font-size: 18pt; margin: 0 0 4pt; color: #111; }
  h2 { font-size: 13pt; margin: 18pt 0 6pt; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 4pt; }
  h3 { font-size: 11pt; margin: 12pt 0 4pt; color: #555; }
  .subtitle { color: #666; font-size: 9pt; margin: 0 0 16pt; }

  /* Daily totals box */
  .totals { display: flex; gap: 16pt; margin: 8pt 0 16pt; }
  .total-box { background: #f8f8f8; border-radius: 6pt; padding: 8pt 12pt; text-align: center; flex: 1; }
  .total-value { font-size: 16pt; font-weight: 700; color: #111; }
  .total-label { font-size: 8pt; color: #888; text-transform: uppercase; letter-spacing: 0.5pt; }

  /* Ingredient table */
  table { width: 100%; border-collapse: collapse; font-size: 9pt; }
  th { text-align: left; padding: 4pt 6pt; border-bottom: 2px solid #333; font-weight: 600; color: #333; }
  td { padding: 4pt 6pt; border-bottom: 1px solid #eee; }
  tr:last-child td { border-bottom: none; }
  .num { text-align: right; font-variant-numeric: tabular-nums; }

  /* Macro bars */
  .bar-container { margin: 4pt 0; }
  .bar-label { font-size: 8pt; color: #666; margin-bottom: 2pt; }
  .bar { height: 14pt; border-radius: 3pt; display: flex; overflow: hidden; background: #f0f0f0; }
  .bar-segment { height: 100%; }

  /* Micro bars */
  .micro-row { display: flex; align-items: center; margin: 2pt 0; }
  .micro-name { width: 100pt; font-size: 8pt; color: #555; }
  .micro-bar-bg { flex: 1; height: 10pt; background: #f0f0f0; border-radius: 2pt; overflow: hidden; }
  .micro-bar-fill { height: 100%; border-radius: 2pt; }
  .micro-pct { width: 36pt; text-align: right; font-size: 8pt; color: #666; }

  /* Shopping list */
  .shopping-page { page-break-before: always; }
  .check-item { margin: 4pt 0; font-size: 10pt; display: flex; align-items: center; gap: 6pt; }
  .checkbox { width: 10pt; height: 10pt; border: 1.5px solid #999; border-radius: 2pt; flex-shrink: 0; }
  .item-name { color: #222; }
  .item-weight { color: #888; font-size: 9pt; }
</style>
</head>
<body>

{% if include_dashboard %}
<!-- PAGE 1: NUTRITION DASHBOARD -->
<h1>Daily Chow — Meal Plan</h1>
<p class="subtitle">{{ date }} · {{ sex }}, {{ age_group }} · {{ daily_cal }} kcal target</p>

<div class="totals">
  <div class="total-box">
    <div class="total-value">{{ total_calories | round | int }}</div>
    <div class="total-label">Calories</div>
  </div>
  <div class="total-box">
    <div class="total-value">{{ total_protein | round | int }}g</div>
    <div class="total-label">Protein</div>
  </div>
  <div class="total-box">
    <div class="total-value">{{ total_fat | round | int }}g</div>
    <div class="total-label">Fat</div>
  </div>
  <div class="total-box">
    <div class="total-value">{{ total_carbs | round | int }}g</div>
    <div class="total-label">Carbs</div>
  </div>
  <div class="total-box">
    <div class="total-value">{{ total_fiber | round | int }}g</div>
    <div class="total-label">Fiber</div>
  </div>
</div>

<h2>Ingredients</h2>
<table>
  <thead>
    <tr>
      <th>Ingredient</th>
      <th class="num">Weight</th>
      <th class="num">Cal</th>
      <th class="num">Pro</th>
      <th class="num">Fat</th>
      <th class="num">Carb</th>
      <th class="num">Fiber</th>
    </tr>
  </thead>
  <tbody>
    {% for ing in ingredients %}
    <tr>
      <td>{{ ing.name }}</td>
      <td class="num">{{ ing.grams | round | int }}g</td>
      <td class="num">{{ ing.calories | round | int }}</td>
      <td class="num">{{ ing.protein | round | int }}g</td>
      <td class="num">{{ ing.fat | round | int }}g</td>
      <td class="num">{{ ing.carbs | round | int }}g</td>
      <td class="num">{{ ing.fiber | round | int }}g</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<!-- Macro breakdown bars -->
<h2>Macro Breakdown</h2>
{% for macro_name, segments in macro_bars.items() %}
<div class="bar-container">
  <div class="bar-label">{{ macro_name }}</div>
  <div class="bar">
    {% for seg in segments %}
    <div class="bar-segment" style="width: {{ seg.pct }}%; background: {{ seg.color }};"></div>
    {% endfor %}
  </div>
</div>
{% endfor %}

<!-- Micronutrient coverage -->
{% if micros %}
<h2>Micronutrient Coverage</h2>
{% for micro in micros %}
<div class="micro-row">
  <span class="micro-name">{{ micro.name }}</span>
  <div class="micro-bar-bg">
    <div class="micro-bar-fill" style="width: {{ [micro.pct, 100] | min }}%; background: {{ '#22c55e' if micro.pct >= 100 else '#f59e0b' if micro.pct >= 75 else '#ef4444' }};"></div>
  </div>
  <span class="micro-pct">{{ micro.pct | round | int }}%</span>
</div>
{% endfor %}
{% endif %}
{% endif %}

<!-- PAGE 2: SHOPPING LIST -->
<div {% if include_dashboard %}class="shopping-page"{% endif %}>
<h1>Shopping List{% if num_days > 1 %} — {{ num_days }} days{% endif %}</h1>
<p class="subtitle">{{ date }} · {{ daily_cal }} kcal/day{% if num_days > 1 %} · {{ (total_calories * num_days) | round | int }} kcal total{% endif %}</p>

{% for cat, items in shopping_categories %}
<h3>{{ cat }}</h3>
{% for item in items %}
<div class="check-item">
  <div class="checkbox"></div>
  <span class="item-name">{{ item.name }}</span>
  <span class="item-weight">{{ item.weight_str }}</span>
</div>
{% endfor %}
{% endfor %}
</div>

</body>
</html>
```

**Step 2: Commit**

```bash
git add src/daily_chow/templates/export.html
git commit -m "feat: add HTML/CSS template for PDF export"
```

---

### Task 5: PDF generation function + tests

**Files:**
- Modify: `src/daily_chow/export.py`
- Modify: `tests/test_export.py`

**Step 1: Write the failing test**

Append to `tests/test_export.py`:

```python
from daily_chow.export import generate_pdf, ExportMicro


def test_pdf_returns_bytes():
    """PDF generation returns non-empty bytes."""
    data = ExportData(
        date="2026-02-17",
        sex="male",
        age_group="19-30",
        daily_cal=2000,
        total_calories=2000,
        total_protein=150,
        total_fat=67,
        total_carbs=200,
        total_fiber=35,
        ingredients=[
            ExportIngredient(
                name="Chicken Breast",
                subtitle="raw",
                category="Poultry Products",
                grams=200,
                calories=330,
                protein=62,
                fat=7,
                carbs=0,
                fiber=0,
            ),
        ],
        micros={
            "calcium_mg": ExportMicro(
                name="Calcium", unit="mg", total=50, dri=1000, pct=5.0
            ),
        },
        num_days=7,
    )
    pdf_bytes = generate_pdf(data, include_dashboard=True)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 100
    assert pdf_bytes[:5] == b"%PDF-"


def test_pdf_without_dashboard():
    """PDF without dashboard should still work (shopping list only)."""
    data = ExportData(
        date="2026-02-17",
        sex="male",
        age_group="19-30",
        daily_cal=2000,
        total_calories=2000,
        total_protein=150,
        total_fat=67,
        total_carbs=200,
        total_fiber=35,
        ingredients=[
            ExportIngredient(
                name="Rice",
                subtitle="cooked",
                category="Cereal Grains and Pasta",
                grams=300,
                calories=390,
                protein=8,
                fat=1,
                carbs=86,
                fiber=1,
            ),
        ],
        micros={},
        num_days=3,
    )
    pdf_bytes = generate_pdf(data, include_dashboard=False)
    assert pdf_bytes[:5] == b"%PDF-"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_export.py::test_pdf_returns_bytes -v`
Expected: FAIL — `ImportError`

**Step 3: Write implementation**

Add to `src/daily_chow/export.py`:

```python
from pathlib import Path

import jinja2
import weasyprint

_TEMPLATE_DIR = Path(__file__).parent / "templates"

# Colors matching the frontend INGREDIENT_COLORS
INGREDIENT_COLORS = [
    "#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#a855f7",
    "#06b6d4", "#f97316", "#ec4899", "#14b8a6", "#8b5cf6",
    "#84cc16", "#e11d48", "#0ea5e9", "#d946ef", "#eab308",
]


def _build_macro_bars(
    ingredients: list[ExportIngredient],
) -> dict[str, list[dict]]:
    """Build macro bar segment data for the PDF template."""
    macros = ["Calories", "Protein", "Fat", "Carbs", "Fiber"]
    attrs = ["calories", "protein", "fat", "carbs", "fiber"]
    bars: dict[str, list[dict]] = {}
    for macro_name, attr in zip(macros, attrs):
        total = sum(getattr(ing, attr) for ing in ingredients)
        segments = []
        for i, ing in enumerate(ingredients):
            val = getattr(ing, attr)
            pct = (val / total * 100) if total > 0 else 0
            if pct > 0.5:  # skip tiny segments
                segments.append({
                    "pct": round(pct, 1),
                    "color": INGREDIENT_COLORS[i % len(INGREDIENT_COLORS)],
                })
        bars[macro_name] = segments
    return bars


def generate_pdf(data: ExportData, *, include_dashboard: bool = True) -> bytes:
    """Generate a PDF meal plan with optional nutrition dashboard."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("export.html")

    # Build shopping list grouped by category
    categories: dict[str, list[dict]] = {}
    for ing in data.ingredients:
        total_g = ing.grams * data.num_days
        item = {"name": ing.name, "weight_str": format_weight(total_g)}
        categories.setdefault(ing.category, []).append(item)
    shopping_categories = [
        (cat, sorted(items, key=lambda i: i["name"]))
        for cat, items in sorted(categories.items())
    ]

    # Build micro list for template
    micro_list = [
        {"name": m.name, "pct": m.pct}
        for m in data.micros.values()
    ]

    html = template.render(
        include_dashboard=include_dashboard,
        date=data.date,
        sex=data.sex.title(),
        age_group=data.age_group,
        daily_cal=data.daily_cal,
        total_calories=data.total_calories,
        total_protein=data.total_protein,
        total_fat=data.total_fat,
        total_carbs=data.total_carbs,
        total_fiber=data.total_fiber,
        ingredients=data.ingredients,
        macro_bars=_build_macro_bars(data.ingredients),
        micros=micro_list,
        num_days=data.num_days,
        shopping_categories=shopping_categories,
    )

    return weasyprint.HTML(string=html).write_pdf()
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_export.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add src/daily_chow/export.py tests/test_export.py
git commit -m "feat: add PDF export generation with weasyprint"
```

---

### Task 6: API endpoint + tests

**Files:**
- Modify: `src/daily_chow/api.py`
- Create: `tests/test_api_export.py`

**Step 1: Write the failing test**

Create `tests/test_api_export.py`:

```python
from fastapi.testclient import TestClient

from daily_chow.api import app

client = TestClient(app)


def _make_export_body(**overrides):
    """Build a minimal valid export request body."""
    body = {
        "format": "md",
        "include_dashboard": False,
        "num_days": 1,
        "solution": {
            "status": "optimal",
            "ingredients": [
                {
                    "key": 171705,
                    "grams": 200,
                    "calories_kcal": 260,
                    "protein_g": 5,
                    "fat_g": 1,
                    "carbs_g": 57,
                    "fiber_g": 2,
                },
            ],
            "meal_calories_kcal": 260,
            "meal_protein_g": 5,
            "meal_fat_g": 1,
            "meal_carbs_g": 57,
            "meal_fiber_g": 2,
            "micros": {},
        },
        "foods": {
            "171705": {
                "fdc_id": 171705,
                "name": "Rice",
                "subtitle": "white, cooked",
                "usda_description": "Rice, white, long-grain, regular, cooked",
                "category": "Cereal Grains and Pasta",
                "calories_kcal_per_100g": 130,
                "protein_g_per_100g": 2.7,
                "fat_g_per_100g": 0.3,
                "carbs_g_per_100g": 28.2,
                "fiber_g_per_100g": 0.4,
                "commonness": 3,
                "micros": {},
            }
        },
        "sex": "male",
        "age_group": "19-30",
        "daily_cal": 2000,
    }
    body.update(overrides)
    return body


def test_export_markdown():
    body = _make_export_body(format="md")
    resp = client.post("/api/export", json=body)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/markdown; charset=utf-8"
    text = resp.text
    assert "Daily Chow" in text
    assert "Rice" in text


def test_export_pdf():
    body = _make_export_body(format="pdf", include_dashboard=True)
    resp = client.post("/api/export", json=body)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


def test_export_shopping_list_scales():
    body = _make_export_body(format="md", num_days=7)
    resp = client.post("/api/export", json=body)
    text = resp.text
    # 200g * 7 = 1400g
    assert "1400g" in text
    assert "7 days" in text
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api_export.py -v`
Expected: FAIL — 404 (endpoint doesn't exist yet)

**Step 3: Write the endpoint**

Add imports at the top of `src/daily_chow/api.py`:

```python
from datetime import date
from fastapi.responses import Response
from daily_chow.export import ExportData, ExportIngredient, ExportMicro, generate_markdown, generate_pdf
```

Add request model and endpoint:

```python
class ExportFoodRequest(BaseModel):
    fdc_id: int
    name: str
    subtitle: str
    usda_description: str
    category: str
    calories_kcal_per_100g: float
    protein_g_per_100g: float
    fat_g_per_100g: float
    carbs_g_per_100g: float
    fiber_g_per_100g: float
    commonness: int = 3
    micros: dict[str, float] = {}


class ExportRequest(BaseModel):
    format: Literal["md", "pdf"]
    include_dashboard: bool = True
    num_days: int = 1
    solution: SolveResponse
    foods: dict[str, ExportFoodRequest]
    sex: str = "male"
    age_group: str = "19-30"
    daily_cal: int = 2000


@app.post("/api/export")
def post_export(req: ExportRequest) -> Response:
    # Build ExportIngredient list from solution + food metadata
    export_ingredients: list[ExportIngredient] = []
    for si in req.solution.ingredients:
        food = req.foods.get(str(si.key))
        if food is None:
            continue
        export_ingredients.append(
            ExportIngredient(
                name=food.name,
                subtitle=food.subtitle,
                category=food.category,
                grams=si.grams,
                calories=si.calories_kcal,
                protein=si.protein_g,
                fat=si.fat_g,
                carbs=si.carbs_g,
                fiber=si.fiber_g,
            )
        )

    # Build ExportMicro from solution micros + DRI info
    export_micros: dict[str, ExportMicro] = {}
    for key, mr in req.solution.micros.items():
        info = MICRO_INFO.get(key)
        if info is None:
            continue
        export_micros[key] = ExportMicro(
            name=info.name,
            unit=info.unit,
            total=mr.total + mr.pinned,
            dri=mr.dri,
            pct=mr.pct,
        )

    data = ExportData(
        date=date.today().isoformat(),
        sex=req.sex,
        age_group=req.age_group,
        daily_cal=req.daily_cal,
        total_calories=req.solution.meal_calories_kcal,
        total_protein=req.solution.meal_protein_g,
        total_fat=req.solution.meal_fat_g,
        total_carbs=req.solution.meal_carbs_g,
        total_fiber=req.solution.meal_fiber_g,
        ingredients=export_ingredients,
        micros=export_micros,
        num_days=req.num_days,
    )

    if req.format == "pdf":
        pdf_bytes = generate_pdf(data, include_dashboard=req.include_dashboard)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=daily-chow-plan.pdf"},
        )

    md_text = generate_markdown(data)
    return Response(
        content=md_text,
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=daily-chow-plan.md"},
    )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api_export.py -v`
Expected: all PASS

**Step 5: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: all PASS

**Step 6: Commit**

```bash
git add src/daily_chow/api.py tests/test_api_export.py
git commit -m "feat: add /api/export endpoint for markdown and PDF export"
```

---

### Task 7: Frontend export UI

**Files:**
- Modify: `frontend/src/lib/api.ts` — add `exportPlan` function
- Modify: `frontend/src/routes/+page.svelte` — add Export button + popover

**Step 1: Add export API function to `frontend/src/lib/api.ts`**

Add at the end of the file:

```typescript
export async function exportPlan(params: {
	format: 'md' | 'pdf';
	include_dashboard: boolean;
	num_days: number;
	solution: SolveResponse;
	foods: Record<string, Food>;
	sex: string;
	age_group: string;
	daily_cal: number;
}): Promise<Blob> {
	const res = await fetch('/api/export', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(params),
	});
	return res.blob();
}
```

**Step 2: Add export state and handler to `+page.svelte`**

Add these state variables near the other state declarations (around line 54):

```typescript
let showExportPopover = $state(false);
let exportFormat = $state<'md' | 'pdf'>('pdf');
let exportDays = $state(7);
let exportDashboard = $state(true);
let exporting = $state(false);
```

Add the `exportPlan` import to the existing import from `$lib/api` (line 2).

Add the export handler function near the other handler functions:

```typescript
async function handleExport() {
    if (!solution) return;
    exporting = true;
    try {
        const blob = await exportPlan({
            format: exportFormat,
            include_dashboard: exportDashboard,
            num_days: exportDays,
            solution,
            foods,
            sex,
            age_group: ageGroup,
            daily_cal: dailyCal,
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `daily-chow-plan.${exportFormat === 'pdf' ? 'pdf' : 'md'}`;
        a.click();
        URL.revokeObjectURL(url);
        showExportPopover = false;
    } finally {
        exporting = false;
    }
}
```

**Step 3: Add Export button in the header**

In the `<header>` section (around line 559), add an Export button inside `.header-controls`, before the help button:

```svelte
<button class="help-btn" onclick={() => (showExportPopover = !showExportPopover)} title="Export plan" disabled={!solution}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
</button>
```

**Step 4: Add popover markup**

Add right after the closing `</header>` tag (around line 576):

```svelte
{#if showExportPopover}
<div class="export-popover">
    <div class="export-row">
        <label>Format</label>
        <div class="toggle-group">
            <button class:active={exportFormat === 'pdf'} onclick={() => exportFormat = 'pdf'}>PDF</button>
            <button class:active={exportFormat === 'md'} onclick={() => exportFormat = 'md'}>Markdown</button>
        </div>
    </div>
    <div class="export-row">
        <label>Days</label>
        <input type="number" min="1" max="14" bind:value={exportDays} />
    </div>
    {#if exportFormat === 'pdf'}
    <div class="export-row">
        <label>
            <input type="checkbox" bind:checked={exportDashboard} />
            Include nutrition dashboard
        </label>
    </div>
    {/if}
    <button class="export-btn" onclick={handleExport} disabled={!solution || exporting}>
        {exporting ? 'Exporting...' : 'Export'}
    </button>
</div>
{/if}
```

**Step 5: Add CSS for the popover**

Add to the `<style>` section:

```css
.export-popover {
    position: absolute;
    top: 60px;
    right: 16px;
    background: var(--bg-card, #2a2a2a);
    border: 1px solid var(--border, #444);
    border-radius: 8px;
    padding: 12px;
    z-index: 100;
    min-width: 220px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
.export-row {
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
}
.export-row label {
    font-size: 12px;
    color: var(--text-secondary, #aaa);
}
.export-row input[type="number"] {
    width: 60px;
    padding: 4px 6px;
    border-radius: 4px;
    border: 1px solid var(--border, #444);
    background: var(--bg-input, #1a1a1a);
    color: var(--text, #eee);
    font-size: 12px;
}
.toggle-group {
    display: flex;
    border-radius: 4px;
    overflow: hidden;
    border: 1px solid var(--border, #444);
}
.toggle-group button {
    padding: 4px 10px;
    font-size: 11px;
    border: none;
    background: var(--bg-input, #1a1a1a);
    color: var(--text-secondary, #aaa);
    cursor: pointer;
}
.toggle-group button.active {
    background: var(--accent, #3b82f6);
    color: white;
}
.export-btn {
    width: 100%;
    margin-top: 4px;
    padding: 6px;
    border-radius: 6px;
    border: none;
    background: var(--accent, #3b82f6);
    color: white;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
}
.export-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}
```

**Step 6: Test manually**

1. Ensure the dev server is running (both backend and frontend)
2. Open the app, add some ingredients, solve
3. Click the export (download) button in the header
4. Try PDF export with dashboard — should download a styled PDF
5. Try Markdown export — should download a .md file
6. Try different day counts — shopping list quantities should scale

**Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/routes/+page.svelte
git commit -m "feat: add export button and popover to frontend UI"
```

---

### Task 8: End-to-end smoke test

**Files:**
- All existing test files

**Step 1: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: all PASS

**Step 2: Visual check of PDF output**

Run a quick script to generate a sample PDF and open it:

```bash
uv run python -c "
from daily_chow.export import *
data = ExportData(
    date='2026-02-17', sex='male', age_group='19-30', daily_cal=2500,
    total_calories=2500, total_protein=180, total_fat=80, total_carbs=280, total_fiber=40,
    ingredients=[
        ExportIngredient('Chicken Breast', 'raw', 'Poultry Products', 250, 412, 78, 9, 0, 0),
        ExportIngredient('Brown Rice', 'cooked', 'Cereal Grains and Pasta', 400, 444, 10, 3, 92, 4),
        ExportIngredient('Broccoli', 'raw', 'Vegetables', 300, 102, 8, 1, 20, 8),
        ExportIngredient('Salmon', 'raw', 'Finfish', 150, 312, 30, 21, 0, 0),
        ExportIngredient('Sweet Potato', 'raw', 'Vegetables', 250, 215, 4, 0, 51, 8),
    ],
    micros={
        'calcium_mg': ExportMicro('Calcium', 'mg', 800, 1000, 80),
        'iron_mg': ExportMicro('Iron', 'mg', 12, 8, 150),
        'vitamin_c_mg': ExportMicro('Vitamin C', 'mg', 95, 90, 105.6),
        'vitamin_d_mcg': ExportMicro('Vitamin D', 'mcg', 8, 15, 53.3),
    },
    num_days=7,
)
pdf = generate_pdf(data, include_dashboard=True)
with open('/tmp/daily-chow-sample.pdf', 'wb') as f:
    f.write(pdf)
print(f'Wrote {len(pdf)} bytes to /tmp/daily-chow-sample.pdf')
"
open /tmp/daily-chow-sample.pdf
```

Review the PDF visually. Iterate on template CSS if needed.

**Step 3: Final commit (if any template adjustments)**

```bash
git add -A
git commit -m "fix: polish PDF template styling"
```
