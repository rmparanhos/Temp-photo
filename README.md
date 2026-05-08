# ella — photo assistant

TUI for finding similar photos, scoring their quality, and moving duplicates to a separate folder.

---

## Usage

```bash
pip install -r requirements.txt
python main.py ./your-photos
```

Optional flags:

| Flag | Default | Description |
|---|---|---|
| `--threshold N` | 10 | Similarity sensitivity (0 = identical only, 64 = anything) |
| `--recursive` / `-r` | off | Scan sub-folders recursively |

### TUI navigation

| Key | Action |
|---|---|
| `↑` / `↓` | Change which photo to keep in the current group |
| `Enter` | Confirm decision and move to next group |
| `S` | Skip group (no files touched) |
| `Q` | Quit |

At the end, a confirmation screen lists everything that will be moved. Duplicates go into `_duplicates/` inside the scanned folder.

---

## Project structure

```
photo_dedup/
├── scanner.py   — loads photos, computes pHash, groups similar ones
├── scorer.py    — quality heuristics (scores each photo 0–100)
└── tui.py       — Textual TUI
main.py          — entry point (CLI arguments)
requirements.txt
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

## Roadmap (v2)

- **Super photo via weighted averaging:** average the pixels of N similar photos, weighted by each photo's sharpness score. Noise, being random, cancels out — the result is cleaner than any individual frame.
