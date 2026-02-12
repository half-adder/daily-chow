"""Custom Textual widgets for Daily Chow.

RangeBar: interactive range slider with draggable min/max handles.
IngredientRow: compound widget for one ingredient (checkbox + name + range + macros).
"""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.events import Click, MouseDown, MouseMove, MouseUp
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Checkbox, Input, Label


# ── RangeBar ──────────────────────────────────────────────────────────


class RangeBar(Widget, can_focus=True):
    """Interactive range slider with two draggable handles (min/max)
    and a marker showing the solved value.

    Click near a handle to grab it; drag to adjust.
    Arrow keys adjust the focused handle.
    Tab switches which handle is focused.
    """

    range_min: reactive[int] = reactive(0)
    range_max: reactive[int] = reactive(500)
    solved: reactive[int | None] = reactive(None)

    DEFAULT_CSS = """
    RangeBar {
        height: 1;
        min-width: 20;
        width: 1fr;
    }
    RangeBar:focus {
        background: $boost;
    }
    """

    class RangeChanged(Message):
        """Posted when either handle moves."""

        def __init__(self, range_min: int, range_max: int) -> None:
            super().__init__()
            self.range_min = range_min
            self.range_max = range_max

    def __init__(
        self,
        abs_min: int = 0,
        abs_max: int = 1000,
        range_min: int = 0,
        range_max: int = 500,
        solved: int | None = None,
        step: int = 5,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.abs_min = abs_min
        self.abs_max = abs_max
        self.range_min = range_min
        self.range_max = range_max
        self.solved = solved
        self.step = step
        self._dragging: str | None = None  # "min" or "max" or None
        self._focused_handle: str = "min"  # which handle arrow keys affect

    # ── Coordinate mapping ────────────────────────────────────────────

    def _bar_width(self) -> int:
        return max(self.size.width, 10)

    def _val_to_col(self, value: int) -> int:
        """Map a value to a column index."""
        span = self.abs_max - self.abs_min
        if span <= 0:
            return 0
        w = self._bar_width()
        return round((value - self.abs_min) / span * (w - 1))

    def _col_to_val(self, col: int) -> int:
        """Map a column index to a value, clamped to [abs_min, abs_max]."""
        w = self._bar_width()
        if w <= 1:
            return self.abs_min
        raw = self.abs_min + (col / (w - 1)) * (self.abs_max - self.abs_min)
        return max(self.abs_min, min(self.abs_max, round(raw)))

    # ── Rendering ─────────────────────────────────────────────────────

    def render(self) -> Text:
        w = self._bar_width()
        lo = self._val_to_col(self.range_min)
        hi = self._val_to_col(self.range_max)
        sv = self._val_to_col(self.solved) if self.solved is not None else None

        text = Text()
        for i in range(w):
            if sv is not None and i == sv and lo <= i <= hi:
                text.append("●", style="bold bright_green")
            elif i == lo:
                style = "bold cyan" if self._focused_handle == "min" and self.has_focus else "cyan"
                text.append("◀", style=style)
            elif i == hi:
                style = "bold cyan" if self._focused_handle == "max" and self.has_focus else "cyan"
                text.append("▶", style=style)
            elif lo < i < hi:
                text.append("━", style="cyan")
            else:
                text.append("─", style="dim")
        return text

    def watch_range_min(self) -> None:
        self.refresh()

    def watch_range_max(self) -> None:
        self.refresh()

    def watch_solved(self) -> None:
        self.refresh()

    # ── Mouse interaction ─────────────────────────────────────────────

    def on_mouse_down(self, event: MouseDown) -> None:
        val = self._col_to_val(event.x)
        dist_min = abs(val - self.range_min)
        dist_max = abs(val - self.range_max)
        self._dragging = "min" if dist_min <= dist_max else "max"
        self._focused_handle = self._dragging
        self._set_handle(self._dragging, val)
        self.capture_mouse()
        self.focus()
        event.stop()

    def on_mouse_move(self, event: MouseMove) -> None:
        if self._dragging:
            val = self._col_to_val(event.x)
            self._set_handle(self._dragging, val)
            event.stop()

    def on_mouse_up(self, event: MouseUp) -> None:
        if self._dragging:
            self._dragging = None
            self.release_mouse()
            event.stop()

    def _set_handle(self, handle: str, value: int) -> None:
        """Set a handle value, keeping min <= max."""
        old_min, old_max = self.range_min, self.range_max
        if handle == "min":
            self.range_min = min(value, self.range_max)
        else:
            self.range_max = max(value, self.range_min)
        if self.range_min != old_min or self.range_max != old_max:
            self.post_message(self.RangeChanged(self.range_min, self.range_max))

    # ── Keyboard interaction ──────────────────────────────────────────

    BINDINGS = [
        ("left", "nudge(-1)", "Decrease"),
        ("right", "nudge(1)", "Increase"),
        ("tab", "switch_handle", "Switch handle"),
    ]

    def action_nudge(self, direction: int) -> None:
        delta = self.step * direction
        self._set_handle(self._focused_handle, getattr(self, f"range_{self._focused_handle}") + delta)
        self.refresh()

    def action_switch_handle(self) -> None:
        self._focused_handle = "max" if self._focused_handle == "min" else "min"
        self.refresh()


# ── IngredientRow ─────────────────────────────────────────────────────


class IngredientRow(Widget):
    """A single ingredient row: checkbox, name, range slider, solved grams,
    and macro contribution display.
    """

    DEFAULT_CSS = """
    IngredientRow {
        layout: horizontal;
        height: 3;
        padding: 0 1;
    }
    IngredientRow .ing-check {
        width: 5;
        min-width: 5;
    }
    IngredientRow .ing-name {
        width: 20;
        min-width: 20;
        padding: 1 1 0 0;
    }
    IngredientRow .ing-min-input {
        width: 7;
        min-width: 7;
    }
    IngredientRow .ing-bar {
        width: 1fr;
        min-width: 16;
        padding: 1 1 0 1;
    }
    IngredientRow .ing-max-input {
        width: 7;
        min-width: 7;
    }
    IngredientRow .ing-solved {
        width: 7;
        min-width: 7;
        padding: 1 1 0 1;
        text-style: bold;
    }
    IngredientRow .ing-macros {
        width: 14;
        min-width: 14;
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
            step=max(1, self._abs_max // 50),
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

    # ── Sync bar ↔ inputs ─────────────────────────────────────────────

    @on(RangeBar.RangeChanged)
    def _on_bar_changed(self, event: RangeBar.RangeChanged) -> None:
        """Bar was dragged — sync the numeric inputs."""
        event.stop()
        min_input = self.query_one(f"#min_{self.ingredient_key}", Input)
        max_input = self.query_one(f"#max_{self.ingredient_key}", Input)
        min_input.value = str(event.range_min)
        max_input.value = str(event.range_max)
        # Changed message will fire from Input.Changed below

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
