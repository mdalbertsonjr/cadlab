# can-dispenser-ramp

The sloped channel piece of a 5-part gravity-fed can dispenser (the other
parts — `Lid`, `Open End`, `Tongue`, `Turnover End` — aren't reconstructed
yet). Cans lie on their side and roll/slide down this trough to dispense.
Reverse-engineered from a slicer-exported `.3mf` reference model at
`~/Documents/3D-Printing/Models/Can Dispenser 12oz - Ramp.3mf` via
`/cad-reverse`, sized for a standard 12oz (355 mL) can.

**This is the third rebuild (wayfinder ticket #34), and it does not yet pass
its own verification bar.** The first two rebuilds (#28, #31) both modeled
the part as a solid block (with a cut trough, then as a hollow prism) and
both failed — first human QA, then the `/cad-slice` slicer-comparison check
introduced by #33. That check's first real run (posted on issue #32)
revealed the actual structure: **the real part is an open-truss chute, not
a walled channel** — a sloped-interior floor plate, side walls built from
separate bands/braces/a cap-rail hook with real open voids between them
(not solid panels), and no end walls at either end. This rebuild models that
structure directly.

A first pass at this rebuild got total material/envelope very close (0.2%
off) but failed `/cad-slice`'s per-layer check badly (394/427 layers, 92%).
Direct visual GUI review by the user (not `/cad-slice`, which had no way to
flag this on its own) found the real defect: the cap rail was modeled with a
**wrong diagnosis** (assumed it needed height tapering) when the real problem
was **connectivity** — in the real part the cap rail barely touches the rest
of the structure at all. A follow-up mesh re-inspection confirmed this and
found two more concrete defects (an A-lobe boss's Z-range, and the entry
wedge's exact shape). That revision fixed connectivity, the A-lobe, and a
wedge start-point bug — real progress (394→207 failing layers) but still
failing.

**Session continued** (same day, further user GUI review) fixed three more
things the user found by eye: (1) the rib-to-cap-rail connectors were an
orthogonal jog instead of continuing the rib's own diagonal angle; (2) the
cap rail was missing entirely past `s`≈185 — a fresh mesh re-inspection
found it actually runs continuously the full part length, though not at a
uniform length-vs-height relationship; (3) the entry wedge's shape was
expanded from a 2-section to a 6-section loft. Result: 394→207→151 failing
layers.

**Session continued again** (overnight, unsupervised): mirrored the cap-rail
tip taper to the entry end, precisely measured this time (plateau at
Z=83.03 from `s`=0-6, linear ramp to CAP_TOP by `s`=9 — not a naive mirror).
Building it exposed **two pre-existing, silent bugs**, both fixed: (a) a
loft between mismatched vertex-count profiles (a "short hook" with fewer
points than the full hook) produced a **non-manifold candidate** —
`FreeCAD.Shape.isValid()` reported `True` throughout, only PrusaSlicer's
`--info` manifold check caught it; the *exact same* pre-existing bug turned
out to be in `CapRailTip`'s original 7-point-vs-4-point loft too, silently
broken since it was first written. Both fixed by preserving point-count
correspondence between every loft's sections rather than collapsing to a
simpler shape. (b) Once manifold, a per-layer diff found the entry fix
mostly worked but exposed the REAL dominant remaining defect: the cap
rail's top is not a smooth diagonal narrowing at all — a direct mesh
re-inspection (3 independent `s` locations, identical result) found a
**sharp step** at Z=83.0 down to a narrow 2.2mm ridge that runs flat to
CAP_TOP, not the ~3.2mm wall-width band the hook profile assumed. Fixing
this eliminated the top-band failure entirely. **A follow-up attempt to fix
the entry wedge (the next-largest remaining gap, ~90 layers) by rebuilding
it as horizontal Z-bands instead of `s`-sections was a regression** (150→320
failing layers, large new extrusion-length deviations exactly where bands
met) and was reverted — see Caveats. **Result this session: 151→150 failing
layers**, with the entry/ridge fixes independently verified via a full
`/cad-slice` re-run (not just diffed against the previous run's numbers),
plus two genuine correctness bugs (silent non-manifold geometry) fixed that
weren't visible in the failing-layer count at all. Still fails. Do not treat
this as ready for Human QA (#32) until `/cad-slice` passes.

**Session continued yet again**: fixed three more things the user found by
eye — the rib-to-cap-rail connectors were rebuilt to continue each rib's
diagonal spine (not an orthogonal jog); the cap-rail entry-end taper was
re-measured precisely (plateau at Z=83.03 for `s`=0-6, ramp to full height by
`s`=9) and rebuilt without the earlier accidental non-manifold bug; the
entry wedge got a capped, disciplined third attempt (a genuinely different
boundary-tracing technique) that also regressed and was correctly reverted —
see Caveats #1. **Then, in the session directly documented here**: a direct
mesh re-inspection isolating the floor+wall-band's own wire from the
separately-floating rib/cap-rail wires at each cross-section found **the
wall band's top edge smoothly declines from ~33mm near `s`=34 to ~19mm at
`s`=182** (not flat at Z=25, and not a sharp zigzag either — the earlier
"zigzagging" read was from coarser, less-attributed sampling), and — a
second, independent finding from the same investigation — **the wall band's
outer face sits at Y≈67.8, not `outer_half_width`(66.2)**, a consistent
1.6mm/side gap confirmed at 5 separate `s` locations, exactly matching the
rib's own outer reach. Both fixed (the flat `Pad` became a multi-section
`AdditiveLoft`; the outer Y offset by +1.6mm). **Result: 150→138 failing
layers**, with a much larger improvement in severity than the count alone
shows — the previously dominant 62-layer band (Z 9.2-21.4mm) broke up into
small scattered remnants. The single largest remaining band moved to the
cap-rail-tip region (Z 74.6-85.0mm, 52 layers) — diagnosed as the same class
of "2D-varying boundary" problem as the entry wedge (Caveats #1), not
something this session's fixes touched. Given two prior sessions already
spent three reverted attempts on that exact problem class for the wedge, a
fourth blind attempt (this time on the cap-rail tip) was deliberately not
made this session — see Caveats #1 for the updated diagnosis both members
share. Also investigated (secondary priority): a red-highlighted constraint
the user spotted in the GUI — checked object visibility (clean: only `Body`
and the tip feature are visible) and every sketch's
`getConflictingConstraints`/`getRedundantConstraints`/`getMalformedConstraints`
(all empty) via the FreeCAD API; could not reproduce or identify the issue
headlessly. Still fails `/cad-slice`. Do not treat this as ready for Human QA
(#32).

## Geometry

Built as a single `PartDesign::Body`. Members, each a separate Pad/Loft
fused into one solid:

- **Floor plate** (`PartDesign::AdditiveLoft`, `s`=0→188): flat underside at
  Z=0; the interior top surface is the actual can-rolling ramp, sloping from
  16.67mm down to 8.29mm over `s`=25→180, then tapering to a thin
  (~2.86mm) terminating lip by `s`=188. The floor does **not** continue into
  the rise span — past `s`≈188 there is no floor at all.
- **Wall lower band** (`Pad`, `s`=0→`main_length`, both sides): a simple
  3.2mm-thick band from the floor up to Z=25 (the real band's top edge
  zigzags with `s`; approximated flat here — see Caveats).
- **Cap rail** (`Pad` + `CapRailEntryTaper` + `CapRailTip`, both sides): a
  10-point hook profile, Z 70.15→85.53, with a **sharp step at Z=83.0** down
  to a narrow 2.2mm ridge (Y=65.1-67.3) that runs flat to CAP_TOP — not a
  smooth diagonal narrowing to the full wall width, which was the previous
  shape and the session's dominant remaining defect (a uniform ~4.6mm
  Y-width excess across nearly the entire main span, found via direct
  per-layer G-code diffing, confirmed via mesh re-inspection at 3 independent
  `s` locations). Length runs the *entire* part length (a fresh mesh
  re-inspection found it does not stop at `s`≈185 as every prior pass
  assumed), tapering at both ends: `CapRailEntryTaper` (plateau at Z=83.03
  from `s`=0-6, ramping to full height by `s`=9) and `CapRailTip` (the
  far/rise-end taper, now built by proportionally compressing the full
  10-point hook's own height range rather than lofting against an unrelated
  simpler shape — the previous approach was a silently non-manifold
  self-intersection, see Caveats).
- **Cap-rail connectors** (12 total, one per rib tooth per side): the cap
  rail is a genuinely disconnected floating member in the real part for
  almost its entire length — it only touches the diagonal ribs beneath it in
  narrow ~2-3mm windows, once per rib tooth. **Angle corrected this
  revision**: previously an orthogonal jog straight up from the rib's peak;
  the user visually spotted this and it's now built as a parallelogram
  continuing the rib's own diagonal spine (same construction pattern as the
  ribs themselves) up into the cap rail, reading as one continuous diagonal
  member.
- **Climbing rise-span rails** (`AdditiveLoft`, `s`=182→232.9, both sides):
  replace the lower-band pair past the floor's end, climbing at the measured
  ~1.678mm-Z-per-mm-`s` slope, converging toward the tip.
- **Bottom outer skirt** (`Pad`, `s`=0→`main_length`, both sides): a low
  rail, simplified to overlap the wall band directly rather than the real
  ~1.3mm gap between them (connectivity simplification).
- **Entry wedge / gusset panels** (`AdditiveLoft`, `s`=0→40, both sides,
  **expanded from 2 to 6 sections this revision**): the user reported the
  entry wedge's shape ("the V ... isn't shaped properly"); a fresh
  measurement found its dominant variation is the top edge descending
  steeply with `s` (Z≈83 at `s`≤3, 53@10, 34@20, 22@30, fading into the
  floor by `s`≈40) — now captured directly with 6 sections following that
  curve instead of linearly interpolating 2 endpoints. The inward Y-reach is
  still a single value per section, not the full measured per-Z variation —
  see Caveats.
- **4 rail-boss lobes** (`ALobe1/2`, `BLobe1/2`, both sides): the
  lid-engaging rail, per #31. **A-lobes' Z-range corrected this revision**
  to Z 4.4–9.4 (a second mesh re-inspection found the real feature is a
  small foot near the floor, not the Z 0–24 range previously assumed).
  B-lobes kept at their originally-measured Z (74.8-83) with a small local
  connector bridging to the climbing rail rather than widening the lobe
  itself.
- **12 stiffening ribs** (`Rib0..5 Pos/Neg`), unchanged from #31.
- **4 fastener holes**: Z positions corrected to the actual measured Open
  End peg heights (Z≈6.9 in the lower band, Z≈78.7 in the cap rail) — #31
  had placed them at mid-wall height (Z=42.75), which the material-map
  inspection showed falls in open truss void on the real part.

## Parameters

| Alias | Default | Meaning |
|---|---|---|
| `can_diameter` | 66.0 mm | Standard 12oz can diameter (given). |
| `can_height` | 122.7 mm | Standard 12oz can height (given). |
| `wall` | 3.2 mm | Wall/band thickness (revised from 3.5mm — material-map remeasurement). |
| `clearance` | 13.0 mm | Extra room around the can so it can roll freely (measured). |
| `side_wall_height` | 85.5 mm | Overall part height (independent, measured). |
| `main_length` | 182.0 mm | Length of the wall-band/cap-rail/floor span before the rise (independent, measured). |
| `rise_length` | 51.0 mm | Length of the climbing rise span (independent, measured). |
| `fastener_hole_diameter` | 4.8 mm | Measured Open End peg (4.60mm) + 0.2mm clearance — still a first guess, see Caveats. |
| `rib_width` | 4.8 mm | Rib thickness in the Y direction (measured). |
| `rib_thickness` | 5.0 mm | Rib thickness perpendicular to its own diagonal spine (measured). |
| `rib_y` | 65.4 mm | Y-offset of the rib spine from the centerline (measured). |
| `width_calibration_offset` | 4.85 mm | Retuned for `wall`=3.2mm so the can-size formula still reproduces the measured 66.2mm outer half-width — see Caveats. |
| `trough_width` *(derived)* | `= can_height + clearance - 2*width_calibration_offset` ≈ 126.0 mm | Scales with `can_height`. |
| `inner_half_width` *(derived)* | `= trough_width/2` ≈ 63.0 mm | Inner wall face. |
| `outer_half_width` *(derived)* | `= inner_half_width + wall` ≈ 66.2 mm | Outer wall face. |
| `ramp_length` *(derived)* | `= main_length + rise_length` ≈ 233.0 mm | Overall part length. |

All member `s`/`Z` positions and profile shapes are independent measured
constants (Python-computed at script-run time from the spreadsheet's current
width values) — re-run the script after changing `can_diameter`/`can_height`
to regenerate at the new scale; only the floor plate's width is live
`setExpression`-bound for an in-GUI Ctrl+R rescale (verified: rescaling to a
53.0×131.0mm slim can holds `outer_half_width`→70.35mm, single valid solid).

## Caveats

- **This build does not pass `/cad-slice` yet** — see Validation. Known
  remaining gaps, roughly in order of likely impact:
  1. **Two members share the same unsolved problem class: a boundary that
     varies in both length (`s`) and height (Z) simultaneously, which no
     single-axis section shape (a loft of rectangles varying only in one
     direction) can represent.** Four attempts across two members, four
     reverts:
     - **Entry wedge** (Z≈2.4-7.6mm band this session, was the dominant
       Z≈2.4-21.4mm band before the wall-band fixes below shrank it): a
       6-section `s`-loft (current), horizontal Z-bands (regressed
       150→320 — banding creates a toolpath-heavy staircase at each band
       boundary), and a from-scratch fixed-Y(Z)-profile decomposition
       (regressed 150→300 in two variants) have all been tried and
       reverted. The from-scratch attempt's G-code analysis found the real
       trigger was `Top solid infill`/`Bridge infill` toolpath at Z≈25 —
       which pointed at (and this session confirmed and fixed) the wall
       band's flat-top approximation below. Measured boundary data from all
       three attempts is in ticket #34's history; don't re-measure blindly.
     - **Cap-rail tip** (Z≈74.6-85.0mm, 52 layers — now the single largest
       remaining band, surfaced by *this* session's wall-band fixes clearing
       away what used to dominate): the candidate's far-length reach at a
       given Z plateaus early and stays constant, while the baseline's grows
       more gradually with Z — the same "single fixed cross-section can't
       capture a 2D-varying boundary" problem as the wedge, just on the
       `CapRailTip`/`CapRailEntryTaper` members instead. Diagnosed via
       per-layer bbox comparison this session (layers 380-420 spot-checked);
       not yet attempted, given the wedge's 0-for-3 track record on this
       exact problem class — a naive "add more sections" retry without a
       new construction technique would likely repeat the same regression.
     - **Next real attempt at either should try a technique not yet used
       for a 2D boundary**: e.g. a swept profile whose own cross-section is
       parametrized by both `s` and Z directly (not a rectangle interpolated
       between two axes independently), or accept the current shape and
       instead reduce material *elsewhere* to compensate for the excess
       `Top solid infill` trigger, rather than chasing the boundary shape
       itself.
  2. **The wall band's top edge and outer-face width were both wrong — fixed
     this session.** Top edge was flat at Z=25; a direct mesh re-inspection
     (isolating the floor+wall-band's own wire from the separately-floating
     rib/cap-rail wires at each cross-section) found it actually **smoothly
     declines from ~33mm near `s`=34 to ~19mm at `s`=182**. Separately, the
     outer face was assumed to sit at `outer_half_width`(66.2mm) but actually
     sits at **Y≈67.8mm** (confirmed at 5 `s` locations, all agreeing to
     within 0.05mm) — exactly matching the rib's own outer reach. Both are
     now modeled (`WALL_BAND_PROFILE` loft, `+1.6mm` outer offset). This
     directly caused the improvement in Validation below, and confirms the
     G-code `Top solid infill` trigger diagnosed in item 1's wedge attempts
     was real, not a red herring.
  3. **The cap-rail connectors, B-lobe connector, and rail-boss lobes** add
     small local material bumps with no exact real-part correspondent —
     documented simplifications to guarantee a single fused solid, not
     measured features in their own right (except the lobes themselves,
     which are measured).
  4. **Two silent non-manifold bugs, fixed this session, worth understanding
     if debugging a future loft in this script**: `PartDesign::AdditiveLoft`
     between two profile sketches with a *different point count* (e.g. a
     7-point hook lofted against an unrelated 4-point rectangle) can produce
     a self-intersecting surface that `FreeCAD.Shape.isValid()` reports as
     perfectly valid — only a mesh-level manifold check (PrusaSlicer's
     `--info`, now wired into `/cad-slice`) catches it. Both occurrences in
     this script (the original `CapRailTip`, and a first draft of the entry
     taper) are fixed by giving every loft's sections the *same point count
     and topology*, collapsing extra points onto degenerate-but-distinct
     positions rather than using a simpler unrelated shape.
  5. **`Mesh.crossSections()` takes `(point, normal)`, not `(normal, point)`**
     — the opposite of what its signature suggests, and silently returns
     zero wires (no error) if you get it backwards. Also: the mesh's own
     coordinate frame is offset from the script's `s`=0 origin (`Xmin` is
     large and negative) — translate by `Xmin` before querying, or every
     cross-section comes back empty with no indication why.
  6. **A prior per-layer mismatch was wrongly diagnosed as a cap-rail height
     problem** (assumed the main-span top face needed tapering along `s`) —
     disproved by direct re-measurement (the cap rail's *height* was already
     correct; the real defects were connectivity, then the ridge-vs-diagonal
     shape). Recorded here so a future session doesn't re-try the same wrong
     fix a third time.
- **Skirt-to-wall connectivity simplified**: the skirt overlaps the wall
  band directly; the real ~1.3mm gap between them is not modeled.
- **Width-formula calibration** (`width_calibration_offset`): not a
  physically-derived relationship, an acknowledged calibration constant —
  worth re-deriving from first principles if this part is revisited.
- **0.2mm peg-hole clearance is a first guess**, explicitly flagged by the
  user to revisit once two peg-connected parts (this Ramp and `Open End`)
  are actually printed and test-fitted.
- **Fastener hole Y-position** is centered in the wall thickness
  (`outer_half_width - wall/2`) rather than the raw Open End-measured
  67.6mm, which fell just outside the Ramp's own wall band once reconciled
  against `outer_half_width` — re-check once `Open End` is reverse-engineered
  and the two can be compared directly.
- **A red-highlighted constraint the user spotted in the GUI, cutting through
  the part, could not be reproduced headlessly.** Checked and ruled out: (a)
  a leftover visible sketch — `Visibility` is clean, only `Body` and the tip
  feature are visible; (b) a genuine Sketcher constraint conflict —
  `getConflictingConstraints()`/`getRedundantConstraints()`/
  `getMalformedConstraints()` return empty on every sketch in the document.
  Neither hypothesis panned out. If this is still visible after the next
  rebuild, it needs actual GUI eyes (screenshot or direct description of
  which sketch/feature is highlighted) rather than more headless guessing.

## Validation

Headless build + `/cad-slice` (manifold pre-check + print-stability-warning
capture) in a container matching this repo's `containers/Dockerfile` (host
`python3` currently can't import FreeCAD at all — a separate,
already-flagged environment gap):

- **Single valid solid**, volume ≈492,371mm³ (real mesh: 455,738mm³ — 8.0%
  off, up from 5.5% before this session's fixes; volume is a rough proxy,
  `/cad-slice`'s per-layer signal is the real one and it *improved* this
  session despite volume moving further away — the wall band's corrected
  outer-face width adds real, previously-missing material), bounding box
  232.9 × 142.4 × 85.5mm.
- **Ctrl+R rescale** to an 8.4oz slim can (53.0/131.0mm): `outer_half_width`
  grows to 70.35mm as expected, stays a single valid solid.
- **Manifold pre-check**: both sides `manifold=yes`, `number_of_parts=1` —
  genuinely fixed this session (see Caveats #4), not just previously
  unchecked.
- **Print-stability warning**: detected on **both** baseline and candidate —
  informational, not a fail signal, since the real part has genuine
  unsupported bridging by design (matching the cap-rail-connectivity
  finding from the prior revision).
- **`/cad-slice` against `Can Dispenser 12oz - Ramp.3mf`: FAIL, with real,
  independently-verified progress across the whole day
  (394→207→151→150→138).**
  - Aggregate gate: layer count matches exactly (427=427). Filament 4.2%
    apart, estimated time 0.1% apart — comfortably within the 10%
    tolerance. **The aggregate gate passes.**
  - Manifold pre-check: both sides `manifold=yes`, `number_of_parts=1`,
    re-verified after this session's changes.
  - Per-layer signal: **138 of 427 layers (32%) out of tolerance** against
    the 5% threshold, down from 150. Max per-layer bbox deviation is now
    4.75mm — this session's fixes did *not* touch the band that produces
    this specific worst-layer number (the cap-rail tip, Caveats #1), but
    they eliminated the previously-dominant 62-layer band (Z 9.2-21.4mm)
    entirely, breaking it into small scattered remnants (6, 5, 5 layers) —
    the wall-band width/top-edge fixes (Caveats #2) are confirmed working,
    not just theoretically correct.
  - **Remaining failure bands, by Z-height** (this session's fresh
    breakdown, not carried over from before): Z 2.4-7.6mm (27 layers, entry
    wedge), scattered remnants at Z 9-17mm (16 layers total), Z 29.4-32.6mm
    (17 layers, likely the wedge's upper transition), Z 46.6-50.6mm (19
    layers, rib-region, not investigated this session), Z 70.2-71.4mm (7
    layers, a cap-rail-base seam), **Z 74.6-85.0mm (52 layers, the new
    single largest band — the cap-rail tip, see Caveats #1)**.
  - **Interpretation**: the wall-band fixes were unambiguously worth doing —
    they roughly halved what used to be the dominant failure source and
    didn't regress anything else. What's left is concentrated in the two
    "2D-varying boundary" members (Caveats #1) plus a smaller, not-yet-
    investigated rib-region band (Z 46.6-50.6mm) that a future session
    should look at fresh rather than assume is wedge/cap-rail related.

**Sketch-profile pitfall**: an under-constrained (or mis-indexed) profile
sketch can produce a shape that looks completely normal on casual inspection
but is silently null under `.isValid()`'s deep check. This build constrains
every polygon sketch with absolute `DistanceX`/`DistanceY` pins on each
point instead of relying on `Horizontal`/`Vertical` constraints, which
sidesteps the specific orientation-mismatch variant of that footgun.

## Build

```
/cad-build can-dispenser-ramp-parametric
```

Output: `cad-scripts/can-dispenser-ramp/can-dispenser-ramp-parametric.FCStd`

**Do not run `/cad-slice` expecting a pass** until the Validation section
above is updated — the current script is a documented FAIL, kept in the repo
as the best-effort state to build the next iteration from, not a finished
part.
