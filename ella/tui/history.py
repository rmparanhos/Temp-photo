from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, ScrollableContainer, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from .. import history as hist


class NewFolderModal(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss_modal", "Cancel")]

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="modal-body"):
                yield Label("Enter folder path:")
                yield Input(placeholder="~/Pictures/Lightroom/", id="path-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(Path(event.value).expanduser().resolve())

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


class HistoryScreen(Screen):
    BINDINGS = [
        Binding("n", "new_folder", "New folder"),
        Binding("q", "quit_app", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        entries = hist.load()
        with ScrollableContainer():
            if entries:
                yield Static("[bold]Recent folders[/]\n", id="history-title")
            yield ListView(
                ListItem(Label("[bold green][+] New folder[/]"), id="new"),
                *[
                    ListItem(
                        Static(
                            f"[bold]{e.path}[/]"
                            + (
                                "  [dim](not found)[/]"
                                if not e.path.exists()
                                else f"  [dim]{hist.time_ago(e.last_run)}[/]"
                            )
                        ),
                        id=f"entry-{i}",
                    )
                    for i, e in enumerate(entries)
                ],
                id="history-list",
            )
            if not entries:
                yield Static(
                    "[dim]No recent folders. Press N to scan a new folder.[/]",
                    id="no-history",
                )
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.id == "new":
            self.action_new_folder()
        else:
            idx = int(event.item.id.split("-")[1])
            path = hist.load()[idx].path
            self._launch(path)

    def action_new_folder(self) -> None:
        def on_dismiss(path: Optional[Path]) -> None:
            if path:
                self._launch(path)

        self.app.push_screen(NewFolderModal(), on_dismiss)

    def _launch(self, path: Path) -> None:
        if not path.is_dir():
            self.notify(f"'{path}' is not a valid folder.", severity="error")
            return
        from .mode import ModeScreen
        self.app.switch_screen(ModeScreen(path))

    def action_quit_app(self) -> None:
        self.app.exit()
