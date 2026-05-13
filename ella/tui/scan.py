from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ProgressBar

from .. import history as hist
from ..scanner import PhotoInfo, load_photos


class ScanScreen(Screen):
    """Dedup pipeline: hash → group → score."""

    def __init__(self, directory: Path, threshold: int, recursive: bool) -> None:
        super().__init__()
        self._directory = directory
        self._threshold = threshold
        self._recursive = recursive

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
        from ..deduper import find_duplicates

        photos = load_photos(self._directory, self._recursive)
        total = len(photos)

        self.app.call_from_thread(
            self.query_one("#scan-bar", ProgressBar).update,
            total=max(total, 1),
        )
        self.app.call_from_thread(
            self.query_one("#scan-label", Label).update,
            f"Computing hashes for {total} photos...",
        )

        def on_hash_progress(i: int) -> None:
            self.app.call_from_thread(
                self.query_one("#scan-bar", ProgressBar).advance, 1
            )
            self.app.call_from_thread(
                self.query_one("#scan-count", Label).update,
                f"{i} / {total}",
            )

        def on_groups_found(n_groups: int) -> None:
            self.app.call_from_thread(
                self.query_one("#scan-bar", ProgressBar).update,
                total=max(n_groups, 1),
                progress=0,
            )

        def on_group_scored(i: int) -> None:
            self.app.call_from_thread(
                self.query_one("#scan-label", Label).update,
                f"Scoring group {i + 1}...",
            )
            self.app.call_from_thread(
                self.query_one("#scan-bar", ProgressBar).advance, 1
            )

        groups = find_duplicates(
            photos, self._threshold,
            on_hash_progress, on_groups_found, on_group_scored,
        )
        errors = [p for p in photos if p.error]
        self.app.call_from_thread(self._scan_done, groups, errors)

    def _scan_done(
        self, groups: list[list[PhotoInfo]], errors: list[PhotoInfo]
    ) -> None:
        from .dupes import ReviewOrchestrator
        from .report import NoGroupsScreen
        if not groups:
            self.app.push_screen(NoGroupsScreen(errors))
        else:
            self.app.switch_screen(ReviewOrchestrator(groups, errors))


class CullScanScreen(Screen):
    """Cull pipeline: score all → filter by threshold."""

    def __init__(self, directory: Path, cull_threshold: float, recursive: bool) -> None:
        super().__init__()
        self._directory = directory
        self._cull_threshold = cull_threshold
        self._recursive = recursive

    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="scan-body"):
                yield Label("Loading photos...", id="scan-label")
                yield ProgressBar(total=100, show_eta=False, id="scan-bar")
                yield Label("", id="scan-count")
        yield Footer()

    def on_mount(self) -> None:
        hist.record(self._directory)
        self._run_scan()

    @work(thread=True)
    def _run_scan(self) -> None:
        from ..culler import score_all_photos

        photos = load_photos(self._directory, self._recursive)
        total = len(photos)

        self.app.call_from_thread(
            self.query_one("#scan-bar", ProgressBar).update,
            total=max(total, 1),
            progress=0,
        )
        self.app.call_from_thread(
            self.query_one("#scan-label", Label).update,
            f"Scoring {total} photos...",
        )

        def on_progress(i: int) -> None:
            self.app.call_from_thread(
                self.query_one("#scan-bar", ProgressBar).advance, 1
            )
            self.app.call_from_thread(
                self.query_one("#scan-count", Label).update,
                f"{i} / {total}",
            )

        flagged = score_all_photos(photos, self._cull_threshold, on_progress)
        errors = [p for p in photos if p.error]
        self.app.call_from_thread(self._scan_done, flagged, errors)

    def _scan_done(
        self, flagged: list[PhotoInfo], errors: list[PhotoInfo]
    ) -> None:
        from .cull import CullReviewScreen
        from .report import NoCullScreen
        if not flagged:
            self.app.push_screen(NoCullScreen())
        else:
            self.app.switch_screen(CullReviewScreen(flagged, self._cull_threshold))
