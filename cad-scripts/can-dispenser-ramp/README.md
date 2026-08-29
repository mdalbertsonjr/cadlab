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
structure directly. It gets close on total material and overall shape but
**still fails `/cad-slice`'s per-layer check** — see Validation below. Do
not treat this as ready for Human QA (#32) until that's resolved.

## Geometry

Built as a single `PartDesign::Body`. Members, each a separate Pad/Loft
fused into one solid (with small connector posts added purely to guarantee
that fuse where two members don't naturally overlap):

- **Floor plate** (`PartDesign::AdditiveLoft`, `s`=0→188): flat underside at
  Z=0; the interior top surface is the actual can-rolling ramp, sloping from
  16.67mm down to 8.29mm over `s`=25→180, then tapering to a thin
  (~2.86mm) terminating lip by `s`=188. The floor does **not** continue into
  the rise span — past `s`≈188 there is no floor at all.
- **Wall lower band** (`Pad`, `s`=0→`main_length`, both sides): a simple
  3.2mm-thick band from the floor up to Z=25 (the real band's top edge
  zigzags with `s`; approximated flat here — see Caveats).
- **Cap rail** (`Pad`, `s`=0→`main_length`, both sides): a 7-point hook
  profile approximating the measured lid-engagement lip (straight segments
  standing in for a rounded tip), Z 70.15→85.53.
- **Connector posts**: thin (4mm) bridges between the lower band and cap
  rail — the real open-truss void between them (Z 25→70) is not modeled as
  open; see Caveats.
- **Climbing rise-span rails** (`AdditiveLoft`, `s`=182→232.9, both sides):
  replace the lower-band/cap-rail pair past the floor's end, climbing at the
  measured ~1.678mm-Z-per-mm-`s` slope, converging toward the tip.
- **Bottom outer skirt** (`Pad`, `s`=0→`main_length`, both sides): a low
  rail, simplified to overlap the wall band directly rather than the real
  ~1.3mm gap between them (connectivity simplification).
- **Entry wedge / gusset panels** (`AdditiveLoft`, `s`=2→35, both sides):
  tall near the entry, tapering toward the floor by `s`≈35 — a 2-section
  approximation of the real V-diagonal-bounded gusset shape.
- **4 rail-boss lobes** (`ALobe1/2`, `BLobe1/2`, both sides): the
  lid-engaging rail, per #31. A-lobes' Z-range clipped to land in the wall
  band (was previously specified spanning what turned out to be open truss
  void); B-lobes kept at their originally-measured Z (74.8-83) with a small
  local connector bridging to the climbing rail rather than widening the
  lobe itself (an earlier attempt this session that widened the lobes
  instead caused a much bigger per-layer mismatch — see Caveats).
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
  remaining gaps, roughly in order of likely impact: (1) the cap rail's
  main-span top face closes at the full measured max height (85.53mm) for
  its entire 180mm run, while the real part appears to reach that height
  only near the tip — an attempted fix (lowering the main-span cap height)
  regressed further (lost 2 G-code layers, introduced a 224mm-deviation
  layer) and was reverted; this needs real investigation, not another blind
  parameter tweak. (2) The wall band's top edge is approximated flat at
  Z=25 rather than following its real measured zigzag. (3) The connector
  posts and B-lobe connector add local material bumps with no real-part
  correspondent — they exist purely to keep the geometry a single solid.
  (4) The entry wedge is a 2-section loft approximation of a more complex
  V-diagonal-bounded shape.
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

## Validation

Headless build + `/cad-slice` in a container matching this repo's
`containers/Dockerfile` (host `python3` currently can't import FreeCAD at
all — a separate, already-flagged environment gap):

- **Single valid solid**, volume ≈454,867mm³ (real mesh: 455,738mm³ — 0.2%
  off), bounding box 232.9 × 142.4 × 85.5mm.
- **Ctrl+R rescale** to an 8.4oz slim can (53.0/131.0mm): `outer_half_width`
  grows to 70.35mm as expected, stays a single valid solid.
- **`/cad-slice` against `Can Dispenser 12oz - Ramp.3mf`: FAIL.**
  - Aggregate gate: layer count matches exactly (427=427). Filament used
    4.0% apart (within the 10% tolerance). Estimated print time 9.1% apart
    (within tolerance). **The aggregate gate itself passes.**
  - Per-layer signal: **394 of 427 layers (92%) out of tolerance** (>1.0mm
    bbox deviation or >15% extrusion-length deviation), against a 5%
    threshold. Worst layers are all near the top of the part (Z≈83-85.5,
    layers 422-426), with bbox deviations up to 50.85mm — see Caveats point
    (1) above for the diagnosis.
  - **Interpretation**: total material and overall envelope are now very
    close to the real part (a real structural improvement over both prior
    rebuilds), but the *distribution* of that material across height still
    differs enough, in enough places, to fail a strict per-layer check. This
    is the honest state after ~4 iterations against `/cad-slice`'s feedback
    within one session — not a forced pass. The next session should start
    from the per-layer diagnostic technique used here (slicing the mesh by Z
    and comparing cross-sectional area/bbox at each height directly, faster
    to iterate on than a full slice-and-compare cycle) and work through the
    caveats above roughly in order.

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
