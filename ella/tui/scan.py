from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ProgressBar

from .. import history as hist
from ..scanner import PhotoInfo, compute_hashes, group_similar, load_photos
from ..scorer import score_group


class ScanScreen(Screen):
    """Phase 1: hash all photos. Phase 2: group and score."""

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

        self.app.call_from_thread(
            self.query_one("#scan-bar", ProgressBar).update,
            total=max(self._total, 1),
        )
        self.app.call_from_thread(
            self.query_one("#scan-label", Label).update,
            f"Computing hashes for {self._total} photos...",
        )

        def on_hash_progress(i: int) -> None:
            self.app.call_from_thread(
                self.query_one("#scan-bar", ProgressBar).advance, 1
            )
            self.app.call_from_thread(
                self.query_one("#scan-count", Label).update,
                f"{i} / {self._total}",
            )

        compute_hashes(photos, on_hash_progress)

        # Phase 2: group and score
        groups = group_similar(photos, self._threshold)
        n_groups = len(groups)

        self.app.call_from_thread(
            self.query_one("#scan-bar", ProgressBar).update,
            total=max(n_groups, 1),
            progress=0,
        )

        for i, group in enumerate(groups):
            self.app.call_from_thread(
                self.query_one("#scan-label", Label).update,
                f"Scoring group {i + 1} of {n_groups}...",
            )
            self.app.call_from_thread(
                self.query_one("#scan-count", Label).update,
                f"{sum(len(g) for g in groups[:i])} photos processed",
            )
            score_group(group)
            self.app.call_from_thread(
                self.query_one("#scan-bar", ProgressBar).advance, 1
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
    """Scores all photos and routes flagged ones to the cull review screen."""

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
