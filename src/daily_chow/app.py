"""Daily Chow — Interactive meal macro solver TUI."""

from __future__ import annotations

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    Select,
    Static,
)
from textual.widgets.option_list import Option

from daily_chow.food_db import FOODS, search
from daily_chow.solver import IngredientInput, Objective, Solution, Targets, solve
from daily_chow.state import AppState, IngredientState, SmoothieState, load_state, save_state
from daily_chow.widgets import IngredientRow


# ── Add Ingredient Modal ──────────────────────────────────────────────


class AddIngredientModal(ModalScreen[str | None]):
    """Modal for searching and selecting a food from the database."""

    DEFAULT_CSS = """
    AddIngredientModal {
        align: center middle;
    }
    #add-dialog {
        width: 60;
        height: 20;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #add-dialog #search-input {
        margin-bottom: 1;
    }
    #add-dialog #results-list {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="add-dialog"):
            yield Label("Add Ingredient", classes="title")
            yield Input(placeholder="Search foods...", id="search-input")
            yield OptionList(id="results-list")
            yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

    @on(Input.Changed, "#search-input")
    def _on_search(self, event: Input.Changed) -> None:
        results = search(event.value, limit=8)
        option_list = self.query_one("#results-list", OptionList)
        option_list.clear_options()
        for key, food in results:
            label = f"{food.name} ({food.unit_note}) — {food.cal_per_100g} kcal, {food.protein_per_100g}g pro"
            option_list.add_option(Option(label, id=key))

    @on(OptionList.OptionSelected, "#results-list")
    def _on_select(self, event: OptionList.OptionSelected) -> None:
        if event.option.id is not None:
            self.dismiss(str(event.option.id))

    @on(Button.Pressed, "#cancel-btn")
    def _on_cancel(self) -> None:
        self.dismiss(None)


# ── Main App ──────────────────────────────────────────────────────────


OBJECTIVE_OPTIONS = [
    ("Minimize oil", Objective.MINIMIZE_OIL.value),
    ("Minimize rice deviation", Objective.MINIMIZE_RICE_DEVIATION.value),
    ("Minimize total grams", Objective.MINIMIZE_TOTAL_GRAMS.value),
]


class DailyChowApp(App):
    """Interactive meal macro solver."""

    TITLE = "Daily Chow"
    CSS = """
    #targets-bar {
        dock: top;
        height: 3;
        padding: 0 2;
        layout: horizontal;
        background: $boost;
    }
    #targets-bar Label {
        padding: 1 1 0 0;
    }
    #targets-bar Input {
        width: 8;
    }
    #targets-bar Select {
        width: 28;
    }
    #smoothie-bar {
        dock: top;
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    #ingredients-container {
        height: 1fr;
    }
    #totals-bar {
        dock: bottom;
        height: 5;
        padding: 0 2;
        background: $boost;
    }
    #totals-bar .totals-row {
        height: 1;
    }
    #add-btn {
        dock: bottom;
        width: 100%;
        margin: 0 2;
    }
    .header-label {
        padding: 1 0 0 0;
    }
    """

    BINDINGS = [
        ("a", "add_ingredient", "Add ingredient"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.state = load_state()
        self._last_solution: Solution | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="targets-bar"):
            yield Label("Cal:", classes="header-label")
            yield Input(str(self.state.daily_calories), type="integer", id="cal-target")
            yield Label("Pro:", classes="header-label")
            yield Input(str(self.state.daily_protein), type="integer", id="pro-target")
            yield Label("Fiber≥", classes="header-label")
            yield Input(str(self.state.daily_fiber_min), type="integer", id="fiber-target")
            yield Label("Tol cal:", classes="header-label")
            yield Input(str(self.state.cal_tolerance), type="integer", id="cal-tol")
            yield Label("Tol pro:", classes="header-label")
            yield Input(str(self.state.protein_tolerance), type="integer", id="pro-tol")
            yield Select(OBJECTIVE_OPTIONS, value=self.state.objective, id="objective-select")
        yield Static(self._smoothie_text(), id="smoothie-bar")
        with ScrollableContainer(id="ingredients-container"):
            for ing_state in self.state.ingredients:
                food = FOODS.get(ing_state.key)
                if food is None:
                    continue
                yield IngredientRow(
                    ingredient_key=ing_state.key,
                    name=f"{food.name} ({food.unit_note})",
                    enabled=ing_state.enabled,
                    min_g=ing_state.min_g,
                    max_g=ing_state.max_g,
                    abs_max=food.default_max,
                )
        yield Button("+ Add ingredient [a]", id="add-btn", variant="primary")
        with Vertical(id="totals-bar"):
            yield Label("", id="meal-totals", classes="totals-row")
            yield Label("", id="day-totals", classes="totals-row")
            yield Label("", id="status-label", classes="totals-row")
        yield Footer()

    def on_mount(self) -> None:
        self._run_solver()

    def _smoothie_text(self) -> str:
        s = self.state.smoothie
        return f"Smoothie: {s.calories} kcal / {s.protein}g pro / {s.fiber}g fiber (fixed)"

    # ── State sync ────────────────────────────────────────────────────

    def _sync_state_from_ui(self) -> None:
        """Read current UI values back into self.state."""
        try:
            self.state.daily_calories = int(self.query_one("#cal-target", Input).value)
        except ValueError:
            pass
        try:
            self.state.daily_protein = int(self.query_one("#pro-target", Input).value)
        except ValueError:
            pass
        try:
            self.state.daily_fiber_min = int(self.query_one("#fiber-target", Input).value)
        except ValueError:
            pass
        try:
            self.state.cal_tolerance = int(self.query_one("#cal-tol", Input).value)
        except ValueError:
            pass
        try:
            self.state.protein_tolerance = int(self.query_one("#pro-tol", Input).value)
        except ValueError:
            pass

        sel = self.query_one("#objective-select", Select)
        if sel.value is not None and sel.value != Select.BLANK:
            self.state.objective = str(sel.value)

        rows = self.query(IngredientRow)
        self.state.ingredients = [
            IngredientState(
                key=row.ingredient_key,
                enabled=row.enabled,
                min_g=row.min_g,
                max_g=row.max_g,
            )
            for row in rows
        ]

    # ── Solver ────────────────────────────────────────────────────────

    def _run_solver(self) -> None:
        """Sync state, run solver, update UI."""
        self._sync_state_from_ui()

        targets = self.state.targets
        objective = Objective(self.state.objective)

        ingredient_inputs = []
        for ing_state in self.state.ingredients:
            if not ing_state.enabled:
                continue
            food = FOODS.get(ing_state.key)
            if food is None:
                continue
            min_g = min(ing_state.min_g, ing_state.max_g)
            max_g = max(ing_state.min_g, ing_state.max_g)
            ingredient_inputs.append(IngredientInput(ing_state.key, food, min_g, max_g))

        solution = solve(ingredient_inputs, targets, objective)
        self._last_solution = solution

        # Update ingredient rows with solved values
        solved_map: dict[str, tuple[int, float, float]] = {}
        for si in solution.ingredients:
            solved_map[si.key] = (si.grams, si.calories, si.protein)

        for row in self.query(IngredientRow):
            if row.ingredient_key in solved_map:
                g, c, p = solved_map[row.ingredient_key]
                row.update_solution(g, c, p)
            else:
                row.update_solution(None, 0, 0)

        # Update totals
        s = self.state.smoothie
        meal_label = self.query_one("#meal-totals", Label)
        day_label = self.query_one("#day-totals", Label)
        status_label = self.query_one("#status-label", Label)

        if solution.status == "infeasible":
            meal_label.update("Meal:  — infeasible —")
            day_label.update("Day:   — infeasible —")
            status_label.update("✗ INFEASIBLE — try widening ranges or disabling an ingredient")
        else:
            mc, mp, mf = solution.meal_calories, solution.meal_protein, solution.meal_fiber
            dc = mc + s.calories
            dp = mp + s.protein
            df = mf + s.fiber
            meal_label.update(
                f"Meal:  {mc:.0f} kcal │ {mp:.0f}g pro │ {mf:.0f}g fiber"
            )
            day_label.update(
                f"Day:   {dc:.0f} kcal │ {dp:.0f}g pro │ {df:.0f}g fiber"
            )
            status_label.update(f"✓ {solution.status.upper()}")

        save_state(self.state)

    # ── Event handlers ────────────────────────────────────────────────

    @on(IngredientRow.Changed)
    def _on_ingredient_changed(self, event: IngredientRow.Changed) -> None:
        self._run_solver()

    @on(IngredientRow.Removed)
    def _on_ingredient_removed(self, event: IngredientRow.Removed) -> None:
        for row in self.query(IngredientRow):
            if row.ingredient_key == event.ingredient_key:
                row.remove()
                break
        self._run_solver()

    @on(Input.Changed, "#cal-target, #pro-target, #fiber-target, #cal-tol, #pro-tol")
    def _on_target_changed(self) -> None:
        self._run_solver()

    @on(Select.Changed, "#objective-select")
    def _on_objective_changed(self) -> None:
        self._run_solver()

    @on(Button.Pressed, "#add-btn")
    def _on_add_btn(self) -> None:
        self.action_add_ingredient()

    def action_add_ingredient(self) -> None:
        def on_dismiss(key: str | None) -> None:
            if key is None:
                return
            # Don't add duplicates
            existing_keys = {ing.key for ing in self.state.ingredients}
            if key in existing_keys:
                self.notify(f"Already in list: {FOODS[key].name}", severity="warning")
                return
            food = FOODS[key]
            container = self.query_one("#ingredients-container", ScrollableContainer)
            container.mount(
                IngredientRow(
                    ingredient_key=key,
                    name=f"{food.name} ({food.unit_note})",
                    enabled=True,
                    min_g=food.default_min,
                    max_g=food.default_max,
                    abs_max=food.default_max,
                )
            )
            self._run_solver()

        self.push_screen(AddIngredientModal(), callback=on_dismiss)


def main() -> None:
    app = DailyChowApp()
    app.run()


if __name__ == "__main__":
    main()
