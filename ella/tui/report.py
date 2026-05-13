from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Footer, Header, Rule, Static

from ..scanner import PhotoInfo


class ReportScreen(Screen):
    """Final report for the duplicates workflow."""

    BINDINGS = [Binding("q,enter,escape", "quit_app", "Quit")]

    def __init__(
        self,
        groups: list[list[PhotoInfo]],
        decisions: dict[int, int],
        action: str,          # "moved", "xmp", "dry_run"
        dest: Optional[Path],
    ) -> None:
        super().__init__()
        self._groups = groups
        self._decisions = decisions
        self._action = action
        self._dest = dest

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer():
            yield Static(self._build_summary(), id="report-summary")
            yield Rule()
            for i, group in enumerate(self._groups):
                yield Static(self._build_group_line(i, group), classes="report-group")
            yield Rule()
            if self._action == "xmp":
                yield Static(
                    "[dim]In Lightroom: Metadata → Read Metadata from Files,"
                    " then Photo → Delete Rejected Photos.[/]\n"
                )
            yield Static("[dim]Press Q to quit[/]")
        yield Footer()

    def _build_summary(self) -> str:
        confirmed = len(self._decisions)
        skipped = len(self._groups) - confirmed
        total_moved = sum(
            len(self._groups[idx]) - 1
            for idx in self._decisions
        )

        if self._action == "dry_run":
            verb = "would be processed (dry run)"
        elif self._action == "xmp":
            verb = "marked as rejected (XMP written)"
        else:
            verb = f"moved to {self._dest}"

        parts = [f"[bold]{total_moved} duplicate(s)[/] {verb}"]
        if skipped:
            parts.append(f"[dim]{skipped} group(s) skipped[/]")

        return "  " + "  ·  ".join(parts) + "\n"

    def _build_group_line(self, idx: int, group: list[PhotoInfo]) -> str:
        if idx not in self._decisions:
            return f"  Group {idx + 1:>2}  [dim]— skipped[/]"

        keeper_idx = self._decisions[idx]
        keeper = group[keeper_idx]

        if self._action == "dry_run":
            move_label = "would move"
        elif self._action == "xmp":
            move_label = "→ rejected"
        else:
            move_label = "→ moved   "

        lines = [
            f"  Group {idx + 1:>2}  [bold green]✓ kept    {keeper.path.name}[/]"
        ]
        for i, info in enumerate(group):
            if i != keeper_idx:
                lines.append(
                    f"           [dim]{move_label}  {info.path.name}[/]"
                )
        return "\n".join(lines)

    def action_quit_app(self) -> None:
        self.app.exit()


class CullReportScreen(Screen):
    """Final report for the cull workflow."""

    BINDINGS = [Binding("q,enter,escape", "quit_app", "Quit")]

    def __init__(
        self,
        processed: list[PhotoInfo],
        action: str,          # "moved", "xmp", "dry_run"
        dest: Optional[Path],
    ) -> None:
        super().__init__()
        self._processed = processed
        self._action = action
        self._dest = dest

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer():
            if self._action == "dry_run":
                verb = "would be culled (dry run)"
            elif self._action == "xmp":
                verb = "marked as rejected (XMP written)"
            else:
                verb = f"moved to {self._dest}"

            yield Static(
                f"  [bold]{len(self._processed)} photo(s)[/] {verb}\n",
                id="cull-report-summary",
            )
            yield Rule()
            for info in self._processed:
                yield Static(
                    f"  [dim]• {info.path.name}[/]"
                    f"  score [bold]{info.score:.1f}[/]"
                )
            yield Rule()
            if self._action == "xmp":
                yield Static(
                    "[dim]In Lightroom: Metadata → Read Metadata from Files,"
                    " then Photo → Delete Rejected Photos.[/]\n"
                )
            yield Static("[dim]Press Q to quit[/]")
        yield Footer()

    def action_quit_app(self) -> None:
        self.app.exit()


class NoGroupsScreen(Screen):
    """Shown when no duplicate groups were found."""

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


class NoCullScreen(Screen):
    """Shown when no photos fall below the cull threshold."""

    BINDINGS = [Binding("q,enter,escape", "quit_app", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            yield Static(
                "[bold green]No low-quality photos found.[/]\n"
                "All photos are above the quality threshold!"
            )
        yield Footer()

    def action_quit_app(self) -> None:
        self.app.exit(message="No low-quality photos found.")
