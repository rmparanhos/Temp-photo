from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import Footer, Header, Rule, Static

from ..scanner import PhotoInfo
from .common import _render_cull_card


class CullReviewScreen(Screen):
    """Shows all flagged photos one at a time; user toggles inclusion."""

    BINDINGS = [
        Binding("up,k", "cursor_up", "Up", priority=True),
        Binding("down,j", "cursor_down", "Down", priority=True),
        Binding("space", "toggle_current", "Toggle flag"),
        Binding("a", "select_all", "Flag all"),
        Binding("n", "deselect_all", "Unflag all"),
        Binding("enter", "proceed", "Proceed"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, flagged: list[PhotoInfo], threshold: float) -> None:
        super().__init__()
        self._flagged = flagged
        self._threshold = threshold
        self._selected: set[int] = set(range(len(flagged)))  # all flagged by default
        self._cursor = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="cull-indicator")
        with ScrollableContainer():
            yield Static(
                f"[bold]{len(self._flagged)} photos[/] scored below {self._threshold:.0f}\n"
                "[dim]Space: toggle flag · A: flag all · N: unflag all · Enter: proceed[/]\n",
                id="cull-header",
            )
            for i in range(len(self._flagged)):
                yield Static(id=f"cull-item-{i}", classes="cull-item")
            yield Rule()
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_all()

    def _item_text(self, i: int) -> str:
        info = self._flagged[i]
        is_selected = i in self._selected
        cursor_prefix = "[bold yellow]▶[/] " if i == self._cursor else "  "
        check = "[bold red]⚑[/]" if is_selected else "[dim]○[/]"
        score_color = "red" if info.score < self._threshold * 0.5 else "yellow"
        size_kb = info.path.stat().st_size // 1024
        return (
            f"{cursor_prefix}{check}  [bold]{info.path.name}[/]"
            f"  [dim]{size_kb} KB[/]"
            f"  score [bold {score_color}]{info.score:.1f}[/]"
        )

    def _refresh_item(self, i: int) -> None:
        self.query_one(f"#cull-item-{i}", Static).update(self._item_text(i))

    def _refresh_all(self) -> None:
        for i in range(len(self._flagged)):
            self._refresh_item(i)
        self._refresh_indicator()

    def _refresh_indicator(self) -> None:
        n_sel = len(self._selected)
        info = self._flagged[self._cursor]
        self.query_one("#cull-indicator", Static).update(
            f" [bold yellow]⚑ Cull review:[/]  [bold]{info.path.name}[/]"
            f"  score [bold]{info.score:.1f}[/]"
            f"  [dim]({n_sel} of {len(self._flagged)} flagged)[/]"
        )

    def action_cursor_up(self) -> None:
        old = self._cursor
        self._cursor = max(0, self._cursor - 1)
        if old != self._cursor:
            self._refresh_item(old)
            self._refresh_item(self._cursor)
            self._refresh_indicator()

    def action_cursor_down(self) -> None:
        old = self._cursor
        self._cursor = min(len(self._flagged) - 1, self._cursor + 1)
        if old != self._cursor:
            self._refresh_item(old)
            self._refresh_item(self._cursor)
            self._refresh_indicator()

    def action_toggle_current(self) -> None:
        if self._cursor in self._selected:
            self._selected.discard(self._cursor)
        else:
            self._selected.add(self._cursor)
        self._refresh_item(self._cursor)
        self._refresh_indicator()

    def action_select_all(self) -> None:
        self._selected = set(range(len(self._flagged)))
        self._refresh_all()

    def action_deselect_all(self) -> None:
        self._selected = set()
        self._refresh_all()

    def action_proceed(self) -> None:
        to_process = [self._flagged[i] for i in sorted(self._selected)]
        from .confirm import CullConfirmScreen
        self.app.switch_screen(CullConfirmScreen(to_process))

    def action_quit_app(self) -> None:
        self.app.exit()
