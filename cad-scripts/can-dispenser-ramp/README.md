# can-dispenser-ramp

The sloped channel piece of a 5-part gravity-fed can dispenser (the other
parts — `Lid`, `Open End`, `Tongue`, `Turnover End` — aren't reconstructed
yet). Cans lie on their side and roll/slide down this trough to dispense.
Reverse-engineered from a slicer-exported `.3mf` reference model at
`~/Documents/3D-Printing/Models/Can Dispenser 12oz - Ramp.3mf` via
`/cad-reverse`, sized for a standard 12oz (355 mL) can. This is the second
rebuild (wayfinder ticket #31), replacing an earlier version that failed
human QA on two fronts: no lid-retention feature or fastener holes at all,
and a taper shape that didn't actually match the reference model.

## Geometry

Built as a single `PartDesign::Body`, per the PartDesign-as-default
convention in `.claude/skills/cad-reverse/SKILL.md`:

- **Outer block**: a `Part::Box`-equivalent Pad, `ramp_length` ×
  (`2*outer_half_width`) × `side_wall_height`.
- **Trough**: a `PartDesign::SubtractiveLoft` (not the previous build's
  primitive-box-plus-`Part::Loft` split) cutting the open channel through 7
  section profiles that follow the *actual* measured floor-height curve.
  **Correction from the previous rebuild**: the "taper" is not the channel
  *width* narrowing to a point — it's the *floor rising* while the width
  stays constant, closing to a ~1.5mm slit that never fully seals. The
  previous build's channel-narrowing model, and even its 2-section
  `Ruled=True` loft for that wrong model, were both replaced.
- **4 rail bosses** (`ALobe1/2`, `BLobe1/2`, each ±Y): additive ears
  projecting ~5mm proud of the outer wall, confirmed against the reference
  model to be the feature that engages a groove cut into the separate `Lid`
  part (i.e. "the missing lid groove" from the QA failure is this rail, not
  a cut into the Ramp itself).
- **4 fastener holes** (`Hole1/2 Pos/Neg`): through-holes sized to the
  measured `Open End` peg diameter plus clearance, at the floor-rise end of
  the part (confirmed by the user against the reference model in the
  FreeCAD GUI — Open End caps the rising-floor end, not the flat entry end).
- **12 stiffening ribs** (`Rib0..5 Pos/Neg`): a repeating diagonal rib
  pattern found on both side walls while re-verifying the base channel's
  cross-section (see Caveat below) — the user identified this as a
  structural stiffening rib and asked for it to be modeled precisely, not
  simplified away.

## Parameters

| Alias | Default | Meaning |
|---|---|---|
| `can_diameter` | 66.0 mm | Standard 12oz can diameter (given). |
| `can_height` | 122.7 mm | Standard 12oz can height (given). |
| `wall` | 3.5 mm | Channel wall thickness (measured). |
| `clearance` | 13.0 mm | Extra room around the can so it can roll freely (measured). |
| `side_wall_height` | 85.5 mm | Height of the channel's side walls (independent, measured). |
| `main_length` | 182.0 mm | Length of the flat-floor constant-cross-section span (independent, measured; revised from 171.6mm). |
| `ramp_rise_length` | 51.0 mm | Length over which the floor rises to close the gap (independent, measured; renamed from `taper_length`=61.3mm — it's a floor rise, not a width taper). |
| `fastener_hole_diameter` | 4.8 mm | Measured Open End peg (4.60mm) + 0.2mm clearance. |
| `boss_proud` | 5.0 mm | How far the rail bosses project beyond the outer wall (measured). |
| `rib_width` | 4.8 mm | Rib thickness in the Y direction (measured). |
| `rib_thickness` | 5.0 mm | Rib thickness perpendicular to its own diagonal spine (derived from the measured apparent cross-section via trigonometry — see Caveat). |
| `rib_y` | 65.4 mm | Y-offset of the rib spine from the centerline (measured). |
| `width_calibration_offset` | 5.15 mm | Reconciles the can-size-driven width formula with the directly measured outer geometry — see Caveat. |
| `trough_width` *(derived)* | `= can_height + clearance - 2*width_calibration_offset` ≈ 125.4 mm | Width of the open trough — scales with `can_height`. |
| `outer_half_width` *(derived)* | `= trough_width/2 + wall` ≈ 66.2 mm | Half-width of the outer block — scales with `trough_width`. |
| `ramp_length` *(derived)* | `= main_length + ramp_rise_length` ≈ 233.0 mm | Overall part length. |

Rail-boss, rib, and fastener-hole *positions* (the specific `s`/`Z`
coordinates in the script) are independent measured constants, not derived
from can dimensions — they're fixed structural/mating features of this
specific molded part, not things that should move when `can_diameter`/
`can_height` change.

## Caveats

- **Width-formula calibration.** The original `channel_width = can_height +
  2*wall + clearance` formula (from the very first build) predicts an outer
  half-width of ~71.35mm at default dimensions, but direct mesh measurement
  of the real part found 66.2mm — a ~5.15mm/side gap. Rather than abandon
  can-size scaling, `width_calibration_offset` (5.15mm) is subtracted so the
  formula reproduces the measured geometry at default values while still
  scaling proportionally with `can_height`. This is an acknowledged
  calibration constant, not a physically-derived relationship — worth
  re-deriving from first principles if this part is revisited.
- **Fastener hole Y-position reconciled, not directly measured on the
  Ramp.** The 67.6mm peg position found by inspecting `Open End`'s mesh
  falls just outside the Ramp's own wall band once reconciled against the
  corrected `outer_half_width` — likely the same measurement-frame mismatch
  as the width calibration above (Open End's geometry was measured
  independently of the Ramp's). The holes are centered in the Ramp's actual
  wall thickness instead (`outer_half_width - wall/2`) so they land in real
  material; this should be re-checked once `Open End` itself is
  reverse-engineered and the two can be compared directly.
- **Ribs modeled as a padded diagonal parallelogram, not a literal
  `AdditivePipe` sweep.** A straight-spine sweep and a Pad of a parallelogram
  profile (aligned to the spine's own direction, then extruded perpendicular
  to it) produce an identical solid for a straight rib — the Pad approach
  was more robust to build correctly for 12 repeated instances than
  chaining `Sweep`/`Pipe` spine-and-profile attachments. The rib path itself
  (period ≈22.83mm, run 21mm, rise 35.5mm per tooth, 6 teeth from
  `s`≈34 to ≈171) is a straight-line diagonal per tooth, confirmed via dense
  (1mm-interval) mesh cross-sectioning — not assumed from coarse sampling.
- **Base channel cross-section is still a simplification.** Real mesh
  cross-sections in the constant-span region show additional disconnected
  wire fragments beyond the ribs (evidence of thin-shell/rounded-corner
  construction in the source mesh) that aren't chased here — consistent
  with this pipeline's stated policy of matching functional envelope, not
  exact surface topology.
- **0.2mm peg-hole clearance is a first guess**, explicitly flagged by the
  user to revisit once two peg-connected parts (this Ramp and `Open End`)
  are actually printed and test-fitted.

## Validation

Headless build in a container matching this repo's `containers/Dockerfile`
(host `python3` currently can't import FreeCAD at all — a separate,
already-flagged environment gap, not specific to this part):

- **Default (66.0mm / 122.7mm can)**: single valid solid, volume ≈427,220mm³,
  bounding box 233 × 142.4 × 85.5mm (matches `ramp_length` ×
  `2*(outer_half_width+boss_proud)` × `side_wall_height`).
- **Rescaled to an 8.4oz slim can (53.0mm / 131.0mm)**: `trough_width` grew
  to 133.7mm and `outer_half_width` to 70.35mm exactly as the formulas
  predict, `main_length`/`ramp_rise_length`/`side_wall_height` stayed fixed,
  and the result stayed a single valid solid — confirms the parametric
  relationships hold under Ctrl+R, not just at default values.
- Each fastener hole's volume removal (~63mm³) matches the expected
  cylindrical-bore-through-3.5mm-wall volume, confirming they cut through
  real wall material rather than missing or drilling the wrong direction (an
  actual bug hit and fixed while building this: a hole sketch on the wrong
  reference plane drills along that plane's normal, not into the page — the
  Hole feature drills lengthwise down the ramp if you put its sketch on
  `YZ_Plane` instead of `XZ_Plane`).

**Sketch-profile pitfall carried over from the previous build**: an
under-constrained (or mis-indexed) profile sketch can produce a shape that
looks completely normal on casual inspection but is silently null under
`.isValid()`'s deep check. This build sidesteps the specific
`Horizontal`/`Vertical`-vs-orientation mismatch variant of that footgun by
constraining every polygon sketch with absolute `DistanceX`/`DistanceY` pins
on each point instead — works uniformly for axis-aligned rectangles and the
diagonal rib parallelograms alike.

**Two more bugs a headless check couldn't catch — only found once the user
actually opened this in the FreeCAD GUI (see AGENTS.md "Physical
validation": a headless recompute is necessary but never sufficient):**

- **`Pad.Midplane` silently did nothing.** The rib pads originally set
  `Midplane = True` to center each rib's Y-extrusion on `rib_y`. FreeCAD
  logged `Midplane` as deprecated in favor of `SideType`, and — critically —
  reported the *stored* value as `False` despite the script setting `True`,
  meaning every rib actually built one-sided (offset ~2.4mm from its
  intended centered position) rather than symmetric. Fixed by setting
  `SideType = "Symmetric"` directly instead; verified with a direct
  cross-section slice that the rib now protrudes to exactly
  `rib_y + rib_width/2` = 67.8mm, matching the intended math.
- **Every profile sketch stayed visible after being consumed.**
  `PartDesign::Pad`/`Pocket`/`Hole` features correctly hide the *feature*
  they supersede, but not the *sketch* that feature was built from — with
  dozens of sketches (base, trough sections, boss, rib, hole profiles) left
  visible, the GUI showed an unreadable tangle of overlapping wireframes
  instead of the finished solid, making visual QA impossible. Fixed with an
  explicit visibility pass at the end of the script: hide every object,
  then show only `body.Tip` (and the `Body` itself). This is an
  App-level `Visibility` property, readable/settable headlessly — no
  `FreeCADGui` import needed.

## Build

```
/cad-build can-dispenser-ramp-parametric
```

Output: `cad-scripts/can-dispenser-ramp/can-dispenser-ramp-parametric.FCStd`
