"""Custom Textual widgets for Daily Chow.

RangeBar: visual range slider with min/max handles and solved-value marker.
IngredientRow: compound widget for one ingredient (checkbox + name + range + macros).
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Checkbox, Input, Label, Static


# ── RangeBar ──────────────────────────────────────────────────────────


class RangeBar(Static):
    """A visual bar showing a range [min, max] within [abs_min, abs_max],
    with a marker for the solved value.

    Width of the bar is determined by the container; the bar renders
    proportionally within the available columns.
    """

    BAR_WIDTH = 30  # character width of the bar portion

    range_min: reactive[int] = reactive(0)
    range_max: reactive[int] = reactive(500)
    abs_min: int = 0
    abs_max: int = 1000
    solved: reactive[int | None] = reactive(None)

    DEFAULT_CSS = """
    RangeBar {
        width: auto;
        min-width: 34;
        height: 1;
    }
    """

    def __init__(
        self,
        abs_min: int = 0,
        abs_max: int = 1000,
        range_min: int = 0,
        range_max: int = 500,
        solved: int | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.abs_min = abs_min
        self.abs_max = abs_max
        self.range_min = range_min
        self.range_max = range_max
        self.solved = solved

    def _pos(self, value: int) -> int:
        """Map a value to a character position in the bar."""
        span = self.abs_max - self.abs_min
        if span <= 0:
            return 0
        return round((value - self.abs_min) / span * (self.BAR_WIDTH - 1))

    def render(self) -> str:
        w = self.BAR_WIDTH
        lo = self._pos(self.range_min)
        hi = self._pos(self.range_max)
        sv = self._pos(self.solved) if self.solved is not None else None

        chars = list("." * w)

        # Draw the active range
        for i in range(lo, min(hi + 1, w)):
            chars[i] = "━"

        # Endpoints
        if 0 <= lo < w:
            chars[lo] = "├"
        if 0 <= hi < w:
            chars[hi] = "┤"

        # Solved value marker (overrides range chars)
        if sv is not None and 0 <= sv < w:
            chars[sv] = "●"

        return "".join(chars)

    def watch_range_min(self) -> None:
        self.update(self.render())

    def watch_range_max(self) -> None:
        self.update(self.render())

    def watch_solved(self) -> None:
        self.update(self.render())


# ── IngredientRow ─────────────────────────────────────────────────────


class IngredientRow(Widget):
    """A single ingredient row: checkbox, name, min/max inputs, range bar,
    solved grams, and macro contribution display.
    """

    DEFAULT_CSS = """
    IngredientRow {
        layout: horizontal;
        height: 3;
        padding: 0 1;
    }
    IngredientRow .ing-check {
        width: 6;
        min-width: 6;
    }
    IngredientRow .ing-name {
        width: 22;
        min-width: 22;
        padding: 1 1 0 0;
    }
    IngredientRow .ing-min-input {
        width: 8;
        min-width: 8;
    }
    IngredientRow .ing-bar {
        width: 34;
        min-width: 34;
        padding: 1 0 0 0;
    }
    IngredientRow .ing-max-input {
        width: 8;
        min-width: 8;
    }
    IngredientRow .ing-solved {
        width: 8;
        min-width: 8;
        padding: 1 1 0 1;
        text-style: bold;
    }
    IngredientRow .ing-macros {
        width: 18;
        min-width: 18;
        padding: 1 0 0 0;
        color: $text-muted;
    }
    IngredientRow.disabled .ing-name {
        color: $text-disabled;
    }
    IngredientRow.disabled .ing-bar {
        opacity: 0.3;
    }
    """

    class Changed(Message):
        """Posted when any value in the row changes."""

        def __init__(self, ingredient_key: str) -> None:
            super().__init__()
            self.ingredient_key = ingredient_key

    class Removed(Message):
        """Posted when the user requests removal of this ingredient."""

        def __init__(self, ingredient_key: str) -> None:
            super().__init__()
            self.ingredient_key = ingredient_key

    def __init__(
        self,
        ingredient_key: str,
        name: str,
        enabled: bool = True,
        min_g: int = 0,
        max_g: int = 500,
        abs_max: int = 1000,
        solved: int | None = None,
        cal: float = 0,
        protein: float = 0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.ingredient_key = ingredient_key
        self._name = name
        self._enabled = enabled
        self._min_g = min_g
        self._max_g = max_g
        self._abs_max = abs_max
        self._solved = solved
        self._cal = cal
        self._protein = protein

    def compose(self) -> ComposeResult:
        yield Checkbox(
            "",
            value=self._enabled,
            classes="ing-check",
            id=f"check_{self.ingredient_key}",
        )
        yield Label(self._name, classes="ing-name")
        yield Input(
            str(self._min_g),
            type="integer",
            classes="ing-min-input",
            id=f"min_{self.ingredient_key}",
        )
        yield RangeBar(
            abs_min=0,
            abs_max=self._abs_max,
            range_min=self._min_g,
            range_max=self._max_g,
            solved=self._solved,
            classes="ing-bar",
        )
        yield Input(
            str(self._max_g),
            type="integer",
            classes="ing-max-input",
            id=f"max_{self.ingredient_key}",
        )
        yield Label(
            self._format_solved(self._solved),
            classes="ing-solved",
            id=f"solved_{self.ingredient_key}",
        )
        yield Label(
            self._format_macros(self._cal, self._protein),
            classes="ing-macros",
            id=f"macros_{self.ingredient_key}",
        )

    @staticmethod
    def _format_solved(solved: int | None) -> str:
        return f"{solved}g" if solved is not None else "—"

    @staticmethod
    def _format_macros(cal: float, protein: float) -> str:
        return f"{cal:.0f}/{protein:.0f}"

    @property
    def enabled(self) -> bool:
        cb = self.query_one(f"#check_{self.ingredient_key}", Checkbox)
        return cb.value

    @property
    def min_g(self) -> int:
        inp = self.query_one(f"#min_{self.ingredient_key}", Input)
        try:
            return max(0, int(inp.value))
        except ValueError:
            return 0

    @property
    def max_g(self) -> int:
        inp = self.query_one(f"#max_{self.ingredient_key}", Input)
        try:
            return max(0, int(inp.value))
        except ValueError:
            return self._abs_max

    def update_solution(self, solved: int | None, cal: float, protein: float) -> None:
        """Update the solved value and macros display."""
        bar = self.query_one(RangeBar)
        bar.solved = solved
        self.query_one(f"#solved_{self.ingredient_key}", Label).update(
            self._format_solved(solved)
        )
        self.query_one(f"#macros_{self.ingredient_key}", Label).update(
            self._format_macros(cal, protein)
        )

    @on(Checkbox.Changed)
    def _on_checkbox(self, event: Checkbox.Changed) -> None:
        event.stop()
        if event.checkbox.value:
            self.remove_class("disabled")
        else:
            self.add_class("disabled")
        self.post_message(self.Changed(self.ingredient_key))

    @on(Input.Changed)
    def _on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        bar = self.query_one(RangeBar)
        bar.range_min = self.min_g
        bar.range_max = self.max_g
        self.post_message(self.Changed(self.ingredient_key))

    BINDINGS = [("delete", "remove", "Remove ingredient")]

    def action_remove(self) -> None:
        self.post_message(self.Removed(self.ingredient_key))
