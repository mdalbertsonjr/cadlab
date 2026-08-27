# text-stencil

Generates a multi-line spray-paint stencil plate with the text cut through
it, sized automatically to fit the rendered text.

This script intentionally departs from the usual `cad-forward` script
conventions (see `.claude/skills/cad-forward/SKILL.md`):

- **CLI-driven, not hardcoded.** All parameters are `argparse` flags rather
  than fixed spreadsheet defaults, since text content/layout is expected to
  change per run.
- **Not a live-parametric FreeCAD document.** The plate and letter cuts are
  built as raw OCCT shapes in Python and stored as a single static
  `Part::Feature`, not as `Part::Box`/`Part::Cut` document objects driven by
  `setExpression`. The Parameters spreadsheet is populated for
  record-keeping only — editing it and pressing Ctrl+R will **not**
  regenerate the text; re-run the script with different arguments instead.
  This tradeoff is deliberate: nested letter-outline compounds (especially
  letters with enclosed islands like O/A/B/P/Q/R/D) made FreeCAD's
  recompute-on-open boolean engine produce silent zero-volume results when
  left as live document objects.

## Usage

Run with FreeCAD's headless interpreter, `freecadcmd`, passing script
arguments after `--`:

```bash
freecadcmd text-stencil.py -- --lines "HELLO"

freecadcmd text-stencil.py -- \
    --lines "BIG TITLE" "small subtitle" \
    --font-heights 30 15 --justify right

freecadcmd text-stencil.py -- \
    --lines "A" "B" "C" \
    --font-heights 25 20 15 --thickness 2 --margin 10 --line-gap 4
```

## Arguments

| Flag | Default | Meaning |
|---|---|---|
| `--lines` / `-l` | *required* | One or more lines of text (quote multi-word lines). |
| `--thickness` / `-t` | 1.0 mm | Stencil plate thickness. |
| `--font-heights` / `-fh` | 20.0 mm (all lines) | One value applied to all lines, or one per line. |
| `--justify` / `-j` | `center` | `left` / `center` / `right` horizontal justification. |
| `--margin` / `-m` | 5.0 mm | Margin between text and each plate edge. |
| `--line-gap` / `-g` | 3.0 mm | Vertical gap between text lines. |
| `--font` / `-f` | `DejaVuSans-Bold.ttf` | Path to a TrueType font (falls back through a known-good list if missing). |
| `--output` / `-o` | `/home/developer/cad-output/text-stencil` | Output base path (`.FCStd` appended if missing). |

Letters with enclosed areas (O, A, B, P, Q, R, D) will have floating
islands — add stencil bridges manually in FreeCAD if needed.
