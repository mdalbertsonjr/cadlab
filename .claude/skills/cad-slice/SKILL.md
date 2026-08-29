---
name: cad-slice
description: Slice a built part and its original reference model to G-code and compare them — the pre-print geometric fidelity check
argument-hint: <part-name>[-parametric] <path/to/reference-model>
---

You are a slice-and-compare runner. Your job is to take a part that `cad-build`
has already produced, slice it and its original reference model through the
same headless slicer with the same profile, and report whether the two
G-codes match — a machine check on geometric fidelity that runs *before* any
human time is spent on GUI review or printing.

**Arguments:** $ARGUMENTS — a part name (resolved like `cad-build` resolves
scripts, but to the `.FCStd`) and the path to the original reference model
(STL/3MF/STEP — the same file `cad-reverse` reconstructed from).

**Where this fits:** run this as part of a rebuild ticket's own verification,
alongside the `isValid()`/Ctrl+R checks — it is not a separate tracker phase.
A pass here gates *into* Human QA; it never replaces it. The human
print-and-feedback step remains the pipeline's ultimate validation (see
AGENTS.md "Physical validation") — this skill just catches geometry problems
before they cost a human GUI time or filament. `cad-slice` never edits
scripts: a FAIL feeds back into another `cad-forward`/`cad-reverse`
iteration, same discipline as `cad-build`.

**Why self-consistent slicing:** both models go through the *same* PrusaSlicer
install with the *same* checked-in profile. Never compare against G-code from
a different slicer (e.g. the Bambu Studio output that shipped with a
reference `.3mf`) — two engines' toolpath choices would drown out the
geometry signal this check exists to isolate. Byte-identical output is not
expected even for perfect geometry (the candidate reaches the slicer via
FreeCAD tessellation, the baseline is the original mesh); the comparison
script's tolerances exist for exactly that reason.

**Container requirement:** the `prusa-slicer` package (in
`containers/dependencies.packages`) — images built before it was added need a
rebuild. On Linux the package ships a single `prusa-slicer` binary (there is
no separate `-console` binary as on Windows); it slices fine with no DISPLAY.

---

## Step 1 — Resolve inputs

Resolve the part name to `cad-scripts/<part-name>/<part-name>[-parametric].FCStd`
exactly the way `cad-build` resolves scripts (strip a trailing `-parametric`
for the directory name). If the `.FCStd` doesn't exist, stop and tell the user
to run `/cad-build` first. If the reference model path doesn't exist, stop and
say which path you tried.

## Step 2 — Export both sides to STL, asserting orientation

Run (inside the container, repo mounted):

```bash
python3 .claude/skills/cad-slice/export_stls.py \
    <part.FCStd> <reference-model> <workdir>
```

This tessellates the `.FCStd`'s Body tip shape to `candidate.stl`, re-exports
the reference mesh as `baseline.stl`, and **asserts the two bounding boxes
agree** before anything is sliced — reverse-engineered scripts build in the
source mesh's own coordinate frame, so the boxes should match; if they don't,
the comparison would be meaningless and the script exits non-zero with both
boxes printed. Stop and report that error verbatim if it fires.

## Step 3 — Manifold pre-check

Cheaper than a full slice, and catches a class of problem the G-code
comparison can't localize well (a part that's topologically fine — single
manifold solid — but whose *members* don't actually contact each other where
they should is a different, subtler problem the per-layer signal in Step 5
does catch; this step only catches outright disconnection/non-manifold
geometry):

```bash
prusa-slicer --info baseline.stl
prusa-slicer --info candidate.stl
```

Check both outputs for `manifold = yes` and `number_of_parts = 1`. Stop and
report verbatim if either fails — slicing (let alone comparing) a
non-manifold or multi-part mesh isn't meaningful.

## Step 4 — Slice both with the checked-in profile

```bash
prusa-slicer --export-gcode baseline.stl --center 200,200 \
    --load .claude/skills/cad-slice/profile.ini -o baseline.gcode \
    > baseline.slice.log 2>&1
prusa-slicer --export-gcode candidate.stl --center 200,200 \
    --load .claude/skills/cad-slice/profile.ini -o candidate.gcode \
    > candidate.slice.log 2>&1
```

`--center 200,200` places both models at the same bed position — without it
a model whose coordinates sit outside the bed fails with "All objects are
outside of the print volume", and identical placement is what makes the
per-layer bounding boxes comparable at all. `profile.ini` is checked in
beside this skill so every run is reproducible; a generic 0.4mm-nozzle /
0.2mm-layer PLA profile on an oversized 400×400 bed (big parts must fit —
realism doesn't matter, only that both sides use the identical profile).
Supports are off: support towers are placement-heuristic-sensitive and would
add noise. If PrusaSlicer errors on one side only, that itself is a finding —
report it verbatim (a non-manifold or self-intersecting candidate mesh often
errors where the baseline doesn't).

**The captured logs matter, not just the G-code.** PrusaSlicer emits a
`print warning: Detected print stability issues: ... Floating bridge
anchors, Long bridging extrusions ...` line to stdout at default settings
whenever it detects unsupported bridging/overhangs — previously silently
discarded because nothing captured stdout. It doesn't fail the slice (exit
code stays 0), so redirecting to a log file and feeding it to Step 5 is the
only way to see it.

## Step 5 — Compare

```bash
python3 .claude/skills/cad-slice/compare_gcode.py baseline.gcode candidate.gcode \
    baseline.slice.log candidate.slice.log
```

Two tiers, cheap first: an **aggregate gate** (layer count ±1, filament used
and estimated time within 10%) that fails fast on gross mismatches, then the
**per-layer signal** — each layer's extrusion-move bounding box (>1.0mm edge
deviation flags the layer) and extrusion path length (>15% flags it), failing
if more than 5% of layers flag. Tolerances are constants at the top of the
script. Exit 0 = pass, 1 = fail, human-readable summary either way.

**Print-stability warning (informational, not a pass/fail input):** the
comparison also reports whether PrusaSlicer's stability warning (see Step 4)
appeared on each side. A warning on *both* sides usually means the reference
part has genuine unsupported bridging by design (not every real part is
self-supporting everywhere) — not itself a defect to fix. A warning on only
*one* side is the actionable signal: the reconstruction introduced (or
accidentally fixed) a structural connectivity problem the other side doesn't
have. This isn't wired into the pass/fail verdict yet — there's no calibrated
tolerance for it — so read it manually until a future session has enough
data points to set one.

## Step 6 — Report

Print the comparison summary verbatim, then:

**On PASS:**

> Slicer comparison passed — the reconstructed geometry produces
> materially the same toolpaths as the reference. Proceed to Human QA
> (GUI review / test print); this check does not replace it.

**On FAIL:**

- Report which tier failed and the worst offending layers (the summary lists
  them). Translate layer indices to Z-heights (layer × layer height) so the
  finding points at a *place on the part*, not just a number.
- Do **not** attempt to modify the part script.
- End with:

> Slicer comparison failed. The mismatch above feeds the next
> `cad-reverse`/`cad-forward` iteration — fix the script, re-run
> `/cad-build <part-name>`, then re-run this check.
