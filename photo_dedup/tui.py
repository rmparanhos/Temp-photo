from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, ScrollableContainer, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    ProgressBar,
    Rule,
    Static,
)

from . import history as hist
from .scanner import HASH_MAX_BITS, PhotoInfo, compute_hashes, group_similar, load_photos
from .scorer import LABELS, WEIGHTS, score_group
from .xmp import write_rejected

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

BAR_WIDTH = 22


def _bar(value: float) -> str:
    filled = round(value / 100 * BAR_WIDTH)
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def _render_card(info: PhotoInfo, label: str, color: str, similarity: float) -> str:
    size_kb = info.path.stat().st_size // 1024
    lines = [
        f"[bold {color}]{label}[/]  [bold]{info.path.name}[/]"
        f"  [dim]{size_kb} KB[/]"
        f"  score [bold cyan]{info.score:.1f}[/]"
        f"  similarity [bold magenta]{similarity:.0f}%[/]",
        "",
    ]
    for key, display in LABELS.items():
        val = info.score_breakdown.get(key, 0.0)
        lines.append(f"  {display:10s}  {_bar(val)}  {val:5.1f}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# History screen
# ─────────────────────────────────────────────────────────────────────────────

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
        self.app.switch_screen(
            ScanScreen(path, self.app._threshold, self.app._recursive)
        )

    def action_quit_app(self) -> None:
        self.app.exit()


# ─────────────────────────────────────────────────────────────────────────────
# Scan screen
# ─────────────────────────────────────────────────────────────────────────────

class ScanScreen(Screen):
    def __init__(self, directory: Path, threshold: int, recursive: bool) -> None:
        super().__init__()
        self._directory = directory
        self._threshold = threshold
        self._recursive = recursive
        self._total = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="scan-body"):
                yield Label("Scanning photos...", id="scan-label")
                yield ProgressBar(total=100, show_eta=False, id="scan-bar")
                yield Label("", id="scan-count")
        yield Footer()

    def on_mount(self) -> None:
        hist.record(self._directory)
        self._run_scan()

    @work(thread=True)
    def _run_scan(self) -> None:
        photos = load_photos(self._directory, self._recursive)
        self._total = len(photos)

        self.call_from_thread(
            self.query_one("#scan-bar", ProgressBar).update, total=max(self._total, 1)
        )
        self.call_from_thread(
            self.query_one("#scan-label", Label).update,
            f"Computing hashes for {self._total} photos...",
        )

        def on_progress(i: int) -> None:
            self.call_from_thread(self.query_one("#scan-bar", ProgressBar).advance, 1)
            self.call_from_thread(
                self.query_one("#scan-count", Label).update,
                f"{i} / {self._total}",
            )

        compute_hashes(photos, on_progress)

        self.call_from_thread(
            self.query_one("#scan-label", Label).update,
            "Grouping and scoring similar photos...",
        )
        groups = group_similar(photos, self._threshold)
        for group in groups:
            score_group(group)

        errors = [p for p in photos if p.error]
        self.call_from_thread(self._scan_done, groups, errors)

    def _scan_done(
        self, groups: list[list[PhotoInfo]], errors: list[PhotoInfo]
    ) -> None:
        if not groups:
            self.app.push_screen(NoGroupsScreen(errors))
        else:
            self.app.switch_screen(ReviewOrchestrator(groups, errors))


# ─────────────────────────────────────────────────────────────────────────────
# Group review screen (one group at a time)
# ─────────────────────────────────────────────────────────────────────────────

class GroupScreen(Screen):
    BINDINGS = [
        Binding("up,k", "prev_keeper", "Previous photo"),
        Binding("down,j", "next_keeper", "Next photo"),
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


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator screen
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Confirm screen
# ─────────────────────────────────────────────────────────────────────────────

class ConfirmScreen(Screen):
    BINDINGS = [
        Binding("m", "move_files", "Move to _duplicates/"),
        Binding("x", "write_xmp", "Write XMP (Lightroom)"),
        Binding("escape,q", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        groups: list[list[PhotoInfo]],
        decisions: dict[int, int],
        errors: list[PhotoInfo],
    ) -> None:
        super().__init__()
        self._groups = groups
        self._decisions = decisions
        self._errors = errors
        self._to_move = self._collect_files()

    def _collect_files(self) -> list[Path]:
        files = []
        for group_idx, keeper_idx in self._decisions.items():
            for i, info in enumerate(self._groups[group_idx]):
                if i != keeper_idx:
                    files.append(info.path)
        return files

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer():
            skipped = len(self._groups) - len(self._decisions)
            yield Static(
                f"[bold]{len(self._to_move)} duplicate(s)[/] ready to process"
                + (f"  [dim]({skipped} group(s) skipped)[/]" if skipped else "")
                + "\n",
                id="confirm-summary",
            )
            if self._errors:
                yield Static(
                    f"[yellow]{len(self._errors)} file(s) with errors (skipped)[/]\n"
                )
            for path in self._to_move:
                yield Static(f"  [dim]• {path.name}[/]")
            yield Rule()
            yield Static(
                "[dim]M  move to _duplicates/   "
                "X  write XMP sidecars (Lightroom Classic)   "
                "Esc  cancel[/]"
            )
        yield Footer()

    def action_move_files(self) -> None:
        if not self._to_move:
            self.app.exit(message="Nothing to move.")
            return

        base_dir = self._to_move[0].parent
        dest = base_dir / "_duplicates"
        dest.mkdir(exist_ok=True)

        moved = 0
        for path in self._to_move:
            target = dest / path.name
            if target.exists():
                stem, suffix = path.stem, path.suffix
                counter = 1
                while target.exists():
                    target = dest / f"{stem}_{counter}{suffix}"
                    counter += 1
            shutil.move(str(path), str(target))
            moved += 1

        self.app.exit(message=f"{moved} photo(s) moved to {dest}")

    def action_write_xmp(self) -> None:
        if not self._to_move:
            self.app.exit(message="Nothing to process.")
            return

        written = 0
        for path in self._to_move:
            write_rejected(path)
            written += 1

        self.app.exit(
            message=(
                f"{written} XMP sidecar(s) written.\n"
                "In Lightroom: Metadata → Read Metadata from Files, "
                "then Photo → Delete Rejected Photos."
            )
        )

    def action_cancel(self) -> None:
        self.app.exit(message="Cancelled. No files were changed.")


# ─────────────────────────────────────────────────────────────────────────────
# No-groups screen
# ─────────────────────────────────────────────────────────────────────────────

class NoGroupsScreen(Screen):
    BINDINGS = [Binding("q,enter,escape", "quit_app", "Quit")]

    def __init__(self, errors: list[PhotoInfo]) -> None:
        super().__init__()
        self._errors = errors

    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            yield Static(
                "[bold green]No similar photos found.[/]\n"
                "Everything looks clean!"
            )
        yield Footer()

    def action_quit_app(self) -> None:
        self.app.exit(message="No similar photos found.")


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
Screen {
    background: $surface;
}

#scan-body {
    width: 60;
    height: auto;
    align: center middle;
    margin-top: 8;
}

#scan-label {
    text-align: center;
    margin-bottom: 1;
}

#scan-count {
    text-align: center;
    color: $text-muted;
    margin-top: 1;
}

.photo-card {
    border: solid $panel-lighten-2;
    margin: 0 1 1 1;
    padding: 1 2;
}

.card-keep {
    border: solid $success;
    background: $success 8%;
}

.card-delete {
    border: solid $error;
    background: $error 5%;
}

#group-header {
    margin: 1 2;
}

#confirm-summary {
    margin: 1 2;
}

#history-title {
    margin: 1 2;
}

#history-list {
    margin: 0 1;
}

#no-history {
    margin: 2;
    color: $text-muted;
}

NewFolderModal {
    align: center middle;
}

#modal-body {
    background: $surface;
    border: solid $primary;
    padding: 2 4;
    width: 60;
    height: auto;
}

#modal-body Label {
    margin-bottom: 1;
}
"""


class PhotoDedupApp(App):
    TITLE = "ella — photo assistant"
    CSS = CSS

    def __init__(
        self,
        directory: Optional[Path],
        threshold: int,
        recursive: bool,
    ) -> None:
        super().__init__()
        self._directory = directory
        self._threshold = threshold
        self._recursive = recursive

    def on_mount(self) -> None:
        if self._directory:
            self.push_screen(
                ScanScreen(self._directory, self._threshold, self._recursive)
            )
        else:
            self.push_screen(HistoryScreen())
