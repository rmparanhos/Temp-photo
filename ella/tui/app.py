from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import App

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

#keeper-indicator {
    background: $success 12%;
    border-bottom: solid $success;
    padding: 0 2;
    height: 1;
}

#cull-indicator {
    background: $warning 12%;
    border-bottom: solid $warning;
    padding: 0 2;
    height: 1;
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

.cull-item {
    padding: 0 2;
    margin: 0 1;
}

.cull-item:hover {
    background: $boost;
}

#group-header {
    margin: 1 2;
}

#cull-header {
    margin: 1 2;
}

#confirm-summary {
    margin: 1 2;
}

#cull-confirm-summary {
    margin: 1 2;
}

#report-summary {
    margin: 1 2;
}

#cull-report-summary {
    margin: 1 2;
}

.report-group {
    margin: 0 2 1 2;
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

#mode-body {
    width: 70;
    height: auto;
    align: center middle;
    margin-top: 6;
}

#mode-path {
    margin: 0 1 1 1;
}

#mode-list {
    margin: 0 1;
    height: auto;
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
        dry_run: bool = False,
        cull_threshold: float = 40.0,
    ) -> None:
        super().__init__()
        self._directory = directory
        self._threshold = threshold
        self._recursive = recursive
        self._dry_run = dry_run
        self._cull_threshold = cull_threshold

    def on_mount(self) -> None:
        if self._directory:
            from .mode import ModeScreen
            self.push_screen(ModeScreen(self._directory))
        else:
            from .history import HistoryScreen
            self.push_screen(HistoryScreen())
