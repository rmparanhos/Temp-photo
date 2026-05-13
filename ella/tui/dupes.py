from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import Footer, Header, Rule, Static

from ..scanner import HASH_MAX_BITS, PhotoInfo
from .common import _render_card


class GroupScreen(Screen):
    BINDINGS = [
        # priority=True ensures these fire even when ScrollableContainer is focused
        Binding("up,k", "prev_keeper", "Previous photo", priority=True),
        Binding("down,j", "next_keeper", "Next photo", priority=True),
        Binding("enter", "confirm", "Confirm"),
        Binding("s", "skip", "Skip group"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(
        self,
        group: list[PhotoInfo],
        group_num: int,
        total_groups: int,
    ) -> None:
        super().__init__()
        self._group = group
        self._group_num = group_num
        self._total = total_groups
        self._keeper_idx = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="keeper-indicator")
        with ScrollableContainer():
            yield Static(
                f"[bold]{len(self._group)} similar photos[/]"
                f"  [dim]Group {self._group_num} of {self._total}[/]\n",
                id="group-header",
            )
            for i in range(len(self._group)):
                yield Static(id=f"card-{i}", classes="photo-card")
            yield Rule()
            yield Static(
                "[dim]↑↓  change keeper   "
                "Enter  confirm   "
                "S  skip group   "
                "Q  quit[/]"
            )
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_cards()

    def _refresh_cards(self) -> None:
        keeper = self._group[self._keeper_idx]

        self.query_one("#keeper-indicator", Static).update(
            f" [bold green]★ Keeping:[/]  [bold]{keeper.path.name}[/]"
            f"  [dim](photo {self._keeper_idx + 1} of {len(self._group)})[/]"
        )

        for i, info in enumerate(self._group):
            card = self.query_one(f"#card-{i}", Static)
            if i == self._keeper_idx:
                label, color, similarity = "★ KEEP", "green", 100.0
                card.remove_class("card-delete")
                card.add_class("card-keep")
            else:
                label, color = "✗ MOVE", "red"
                similarity = (1 - (keeper.phash - info.phash) / HASH_MAX_BITS) * 100
                card.remove_class("card-keep")
                card.add_class("card-delete")
            card.update(_render_card(info, label, color, similarity))

    def action_prev_keeper(self) -> None:
        self._keeper_idx = max(0, self._keeper_idx - 1)
        self._refresh_cards()

    def action_next_keeper(self) -> None:
        self._keeper_idx = min(len(self._group) - 1, self._keeper_idx + 1)
        self._refresh_cards()

    def action_confirm(self) -> None:
        self.dismiss(("confirm", self._keeper_idx))

    def action_skip(self) -> None:
        self.dismiss(("skip", None))

    def action_quit_app(self) -> None:
        self.app.exit()


class ReviewOrchestrator(Screen):
    """Invisible coordinator: shows GroupScreen instances sequentially."""

    def __init__(
        self,
        groups: list[list[PhotoInfo]],
        errors: list[PhotoInfo],
    ) -> None:
        super().__init__()
        self._groups = groups
        self._errors = errors
        self._decisions: dict[int, int] = {}
        self._current = 0

    def on_mount(self) -> None:
        self._show_next()

    def _show_next(self) -> None:
        if self._current >= len(self._groups):
            from .confirm import ConfirmScreen
            self.app.switch_screen(
                ConfirmScreen(self._groups, self._decisions, self._errors)
            )
            return

        idx = self._current
        screen = GroupScreen(self._groups[idx], idx + 1, len(self._groups))

        def on_dismiss(result: tuple) -> None:
            action, keeper_idx = result
            if action == "confirm":
                self._decisions[idx] = keeper_idx
            self._current += 1
            self._show_next()

        self.app.push_screen(screen, on_dismiss)

    def compose(self) -> ComposeResult:
        yield Static("")
