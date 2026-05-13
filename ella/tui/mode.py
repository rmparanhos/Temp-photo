from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, ListItem, ListView, Static


class ModeScreen(Screen):
    BINDINGS = [
        Binding("d", "duplicates", "Find duplicates"),
        Binding("c", "cull", "Cull low-quality"),
        Binding("escape,q", "go_back", "Back"),
    ]

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path

    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="mode-body"):
                yield Static(
                    f"[bold]{self._path}[/]\n"
                    "[dim]Select what you'd like to do:[/]\n",
                    id="mode-path",
                )
                yield ListView(
                    ListItem(
                        Static(
                            "[bold]D[/]  Find & remove duplicates\n"
                            "[dim]   Groups similar photos by perceptual hash "
                            "and keeps the highest-quality one.[/]"
                        ),
                        id="mode-dupes",
                    ),
                    ListItem(
                        Static(
                            "[bold]C[/]  Cull low-quality photos\n"
                            f"[dim]   Flags photos with score below "
                            f"{self.app._cull_threshold:.0f} "
                            f"(blurry, dark, noisy, etc.) for removal.[/]"
                        ),
                        id="mode-cull",
                    ),
                    id="mode-list",
                )
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.id == "mode-dupes":
            self.action_duplicates()
        elif event.item.id == "mode-cull":
            self.action_cull()

    def action_duplicates(self) -> None:
        from .scan import ScanScreen
        self.app.switch_screen(
            ScanScreen(self._path, self.app._threshold, self.app._recursive)
        )

    def action_cull(self) -> None:
        from .scan import CullScanScreen
        self.app.switch_screen(
            CullScanScreen(self._path, self.app._cull_threshold, self.app._recursive)
        )

    def action_go_back(self) -> None:
        self.app.pop_screen()
