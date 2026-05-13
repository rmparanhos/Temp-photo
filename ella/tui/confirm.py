from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import Footer, Header, Rule, Static

from ..scanner import PhotoInfo
from ..xmp import write_rejected


class ConfirmScreen(Screen):
    """Summary of duplicate decisions; choose move or XMP."""

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
            dry = self.app._dry_run
            yield Static(
                f"[bold]{len(self._to_move)} duplicate(s)[/] ready to process"
                + (f"  [dim]({skipped} group(s) skipped)[/]" if skipped else "")
                + (f"  [bold yellow](dry run — no files will be changed)[/]" if dry else "")
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
        from .report import ReportScreen
        if not self._to_move or self.app._dry_run:
            self.app.switch_screen(
                ReportScreen(self._groups, self._decisions, "dry_run", None)
            )
            return

        base_dir = self._to_move[0].parent
        dest = base_dir / "_duplicates"
        dest.mkdir(exist_ok=True)

        for path in self._to_move:
            target = dest / path.name
            if target.exists():
                stem, suffix = path.stem, path.suffix
                counter = 1
                while target.exists():
                    target = dest / f"{stem}_{counter}{suffix}"
                    counter += 1
            shutil.move(str(path), str(target))

        self.app.switch_screen(
            ReportScreen(self._groups, self._decisions, "moved", dest)
        )

    def action_write_xmp(self) -> None:
        from .report import ReportScreen
        if self.app._dry_run:
            self.app.switch_screen(
                ReportScreen(self._groups, self._decisions, "dry_run", None)
            )
            return

        for path in self._to_move:
            write_rejected(path)

        self.app.switch_screen(
            ReportScreen(self._groups, self._decisions, "xmp", None)
        )

    def action_cancel(self) -> None:
        self.app.exit(message="Cancelled. No files were changed.")


class CullConfirmScreen(Screen):
    """Summary of photos to cull; choose move or XMP."""

    BINDINGS = [
        Binding("m", "move_files", "Move to _culled/"),
        Binding("x", "write_xmp", "Write XMP (Lightroom)"),
        Binding("escape,q", "cancel", "Cancel"),
    ]

    def __init__(self, to_process: list[PhotoInfo]) -> None:
        super().__init__()
        self._to_process = to_process

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer():
            dry = self.app._dry_run
            yield Static(
                f"[bold]{len(self._to_process)} photo(s)[/] selected for culling"
                + (f"  [bold yellow](dry run — no files will be changed)[/]" if dry else "")
                + "\n",
                id="cull-confirm-summary",
            )
            for info in self._to_process:
                yield Static(
                    f"  [dim]• {info.path.name}[/]"
                    f"  score [bold red]{info.score:.1f}[/]"
                )
            yield Rule()
            yield Static(
                "[dim]M  move to _culled/   "
                "X  write XMP sidecars (Lightroom Classic)   "
                "Esc  cancel[/]"
            )
        yield Footer()

    def action_move_files(self) -> None:
        from .report import CullReportScreen
        if not self._to_process or self.app._dry_run:
            self.app.switch_screen(CullReportScreen(self._to_process, "dry_run", None))
            return

        base_dir = self._to_process[0].path.parent
        dest = base_dir / "_culled"
        dest.mkdir(exist_ok=True)

        for info in self._to_process:
            path = info.path
            target = dest / path.name
            if target.exists():
                stem, suffix = path.stem, path.suffix
                counter = 1
                while target.exists():
                    target = dest / f"{stem}_{counter}{suffix}"
                    counter += 1
            shutil.move(str(path), str(target))

        self.app.switch_screen(CullReportScreen(self._to_process, "moved", dest))

    def action_write_xmp(self) -> None:
        from .report import CullReportScreen
        if self.app._dry_run:
            self.app.switch_screen(CullReportScreen(self._to_process, "dry_run", None))
            return

        for info in self._to_process:
            write_rejected(info.path)

        self.app.switch_screen(CullReportScreen(self._to_process, "xmp", None))

    def action_cancel(self) -> None:
        self.app.exit(message="Cancelled. No files were changed.")
