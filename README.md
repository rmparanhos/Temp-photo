# ella — photo assistant

TUI for finding duplicate photos and culling low-quality shots. Scores each photo by sharpness, exposure, resolution, noise and EXIF metadata.

---

## Installation

```bash
pipx install .
```

That's it. `ella` is now available as a command anywhere in your terminal.

> Requires [pipx](https://pipx.pypa.io). Install it with `brew install pipx` or `pip install pipx`.

## Usage

```bash
ella                  # pick a folder from history
ella ./your-photos    # scan a specific folder directly
```

Optional flags:

| Flag | Default | Description |
|---|---|---|
| `--threshold N` / `-t` | 10 | Similarity sensitivity for duplicates (0 = identical only, 256 = anything) |
| `--cull-threshold N` / `-c` | 40 | Quality score below which a photo is flagged for culling (0–100) |
| `--recursive` / `-r` | off | Scan sub-folders recursively |
| `--dry-run` / `-n` | off | Show what would happen without moving or writing any files |

### Modes

After selecting a folder, ella asks what to do:

**D — Find & remove duplicates**  
Groups photos by perceptual hash. For each group you pick which photo to keep; the rest are moved to `_duplicates/` or marked as rejected via XMP.

**C — Cull low-quality photos**  
Scores every photo individually. Photos below the cull threshold are listed for review. You decide which ones to process.

### TUI navigation — duplicate mode

| Key | Action |
|---|---|
| `↑` / `↓` | Change which photo to keep in the current group |
| `Enter` | Confirm decision and move to next group |
| `S` | Skip group (no files touched) |
| `Q` | Quit |

### TUI navigation — cull mode

| Key | Action |
|---|---|
| `↑` / `↓` | Move cursor through flagged photos |
| `Space` | Toggle flag (include/exclude from action) |
| `A` | Flag all photos |
| `N` | Unflag all photos |
| `Enter` | Proceed to confirm |
| `Q` | Quit |

At the confirmation screen (both modes), choose how to handle the selected files:

| Key | Action |
|---|---|
| `M` | Move files to `_duplicates/` or `_culled/` inside the scanned folder |
| `X` | Write XMP sidecars (Lightroom Classic workflow — see below) |

### History

Running `ella` without arguments opens a history screen with your recently scanned folders. Select one and press `Enter` to continue to mode selection. Press `N` to enter a new folder path.

---

## Lightroom Classic workflow

ella integrates with Lightroom Classic via XMP sidecar files — no plugin required.

**1. Run ella on your Lightroom folder**

Point ella directly at the folder where Lightroom already stores your originals:

```bash
ella ~/Pictures/Lightroom/2024/
```

**2. Review groups and confirm**

Go through each group in the TUI. At the confirmation screen, press **X** (Write XMP).

ella writes a `.xmp` file next to each duplicate marking it as rejected:

```
2024/
├── IMG_001.jpg        ← keeper
├── IMG_002.jpg        ← duplicate
├── IMG_002.xmp        ← written by ella: lr:pickStatus = -1
```

**3. Read metadata in Lightroom**

In Lightroom Classic: `Metadata → Read Metadata from Files`

Lightroom picks up the XMP files and marks the duplicates as rejected (the `X` flag).

**4. Delete rejected photos**

`Photo → Delete Rejected Photos`

Done. No export, no import, no duplicates in the catalog.

---

## Project structure

```
ella/
├── scanner.py   — loads photos, computes pHash, groups similar ones
├── scorer.py    — quality heuristics (scores each photo 0–100)
├── culler.py    — scores all photos; returns those below cull threshold
├── cache.py     — disk cache for hashes + score parts (~/.ella/hash_cache.json)
├── history.py   — folder history (~/.ella/history.json)
├── xmp.py       — writes Lightroom XMP sidecar files
└── tui/
    ├── app.py       — PhotoDedupApp + CSS
    ├── common.py    — shared rendering helpers
    ├── history.py   — HistoryScreen, NewFolderModal
    ├── mode.py      — ModeScreen (duplicates vs cull)
    ├── scan.py      — ScanScreen, CullScanScreen
    ├── dupes.py     — GroupScreen, ReviewOrchestrator
    ├── cull.py      — CullReviewScreen
    ├── confirm.py   — ConfirmScreen, CullConfirmScreen
    └── report.py    — ReportScreen, CullReportScreen, NoGroupsScreen, NoCullScreen
main.py          — thin entry point
```

---

## Concepts

### pHash — Perceptual Hash

A conventional hash (MD5, SHA) changes completely if a single pixel differs. **pHash** was built for the opposite problem: generating a "fingerprint" that is *similar* for visually similar images.

**How it works:**

1. Shrinks the image to ~32×32 pixels (removes detail, preserves structure)
2. Converts to grayscale
3. Applies the **DCT** (Discrete Cosine Transform) — the same transform used internally by JPEG — which separates image frequencies from coarsest to finest
4. Takes only the low frequencies (the "visual skeleton"), discarding textures and noise
5. Compares each coefficient against the mean: higher → `1`, lower → `0`
6. Result: a 64-bit string, the image's fingerprint

**Hamming distance:** to compare two hashes, count how many bits differ. That count is the Hamming distance.

- Distance `0` → identical photos
- Distance `≤ 10` → same scene, minor variations (brightness, compression, slight crop)
- Distance `> 20` → different scenes

`--threshold` controls this limit.

---

### Laplacian variance — sharpness

The **Laplacian operator** computes the second derivative of the image — i.e., where pixel intensity changes *abruptly*. Sharp edges produce high responses; blurry edges produce low responses.

Kernel used:

```
 0   1   0
 1  -4   1
 0   1   0
```

This kernel is applied to every pixel (convolution) and the **variance** of the result is computed:

- **High variance** → many well-defined edges → **sharp** photo
- **Low variance** → everything smooth → **blurry** photo

This is the most widely used sharpness heuristic because it is fast and works well with Pillow + NumPy, with no need for OpenCV.

---

### Exposure score

Analyses the brightness histogram of the image:

- **Mean brightness near 128** (mid-tone) → well exposed
- **High standard deviation** → good contrast
- Very dark (underexposed) or very bright (overexposed) photos are penalised

---

### Noise score

Compares the original image against a median-filtered version. The median filter preserves edges but eliminates granular noise (salt-and-pepper). The **residual** between the two estimates the noise level:

- Low residual → clean image → high score
- High residual → noisy image → low score

---

### EXIF score

When EXIF metadata is available:

- **Low ISO** (e.g. 100) → less sensor noise → higher score
- **Fast shutter speed** (e.g. 1/500 s) → less motion blur → higher score

When EXIF is unavailable the score defaults to 50 (neutral).

---

### Final score

Weighted average of the five criteria:

| Criterion | Weight |
|---|---|
| Sharpness (Laplacian) | 35% |
| Exposure | 25% |
| Resolution (MP) | 20% |
| Noise | 15% |
| EXIF | 5% |

The photo with the highest score is suggested as the one to keep. The user can override the choice in the TUI before confirming.

---

## TODO

### Done
- [x] Perceptual hash (pHash) for similarity grouping
- [x] Quality scoring: sharpness (Laplacian), exposure, resolution, noise, EXIF
- [x] TUI with group-by-group review and score breakdown
- [x] Similarity percentage per photo relative to keeper
- [x] Move duplicates to `_duplicates/` folder
- [x] XMP sidecar output for Lightroom Classic integration
- [x] Folder history (`ella` without args opens recent folders)
- [x] `pipx install .` packaging with `ella` command
- [x] `--dry-run` mode: shows what would happen without writing any files
- [x] pHash disk cache — hashes computed once, reused on subsequent runs
- [x] Score disk cache — quality metrics cached per file, reused on repeat runs
- [x] **Cull mode** — scores all photos, flags those below `--cull-threshold`; interactive list review with toggle per photo; moves to `_culled/` or writes XMP
- [x] Mode selection screen — choose between duplicates or cull after picking a folder

### Next
- [ ] **Per-metric cull thresholds:** flag photos that fail a specific criterion regardless of total score (e.g. `sharpness < 20` = blurry, `exposure < 15` = too dark/bright) — configurable via CLI flags
- [ ] **ASCII thumbnail preview:** render each photo as colored ASCII art (`▀▄█▒░`) inside the TUI, sized proportionally using the character aspect ratio — works in any terminal, no protocol dependency
- [ ] **Open photo in system viewer:** press `O` on any photo in the group review to open it in the OS default viewer (Preview on macOS, xdg-open on Linux) — TUI stays open
- [ ] **Super photo:** merge N similar photos by weighted pixel averaging (weight = sharpness score) to reduce noise — the random noise cancels out across frames
- [ ] **Focus stacking:** for bracketed shots with different focus points, merge the sharpest region of each frame into a single all-in-focus image
- [ ] **Lightroom cloud API:** detect and mark duplicates without downloading originals, via Adobe's REST API

### Ideas
- [ ] **Video support (`--videos`):** detect similar videos by sampling frames and comparing pHash sequences; score by resolution, bitrate, codec, duration and per-frame sharpness; requires `ffmpeg` and a hash cache to avoid reprocessing large files
- [ ] Thumbnail preview in the TUI (Sixel/Kitty terminal graphics protocol)
- [ ] Export report as CSV or JSON for external processing
- [ ] Watch mode: monitor a folder and flag new duplicates automatically
- [ ] Publish to PyPI (`pip install ella`) once the project is stable
