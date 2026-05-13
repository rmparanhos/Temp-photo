from __future__ import annotations

from ..scanner import PhotoInfo
from ..scorer import LABELS

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


def _render_cull_card(info: PhotoInfo, threshold: float) -> str:
    size_kb = info.path.stat().st_size // 1024
    score_color = "red" if info.score < threshold * 0.5 else "yellow"
    lines = [
        f"[bold {score_color}]⚑ FLAGGED[/]  [bold]{info.path.name}[/]"
        f"  [dim]{size_kb} KB[/]"
        f"  score [bold {score_color}]{info.score:.1f}[/]  [dim](threshold: {threshold:.0f})[/]",
        "",
    ]
    for key, display in LABELS.items():
        val = info.score_breakdown.get(key, 0.0)
        lines.append(f"  {display:10s}  {_bar(val)}  {val:5.1f}")
    return "\n".join(lines)
