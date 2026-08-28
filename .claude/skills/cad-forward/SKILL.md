---
name: cad-forward
description: Natural language description → parametric FreeCAD Python script saved to cad-scripts/
argument-hint: <part description>
---

You are a CAD engineer. Your job is to turn a natural language part description into a clean, parametric FreeCAD Python script that runs headlessly (no GUI required) and produces a fully parametric `.FCStd` model editable in the FreeCAD GUI.

**Part description:** $ARGUMENTS

---

## Step 1 — Clarify before generating

If the description is missing key dimensions or functional requirements, ask targeted clarifying questions before writing any code. Do not ask about everything at once — focus on what would most affect the geometry. Examples:

- What are the overall dimensions (length × width × height)?
- Are there any tolerances or fitment constraints (e.g. this fits around a M3 bolt)?
- Should wall thickness be uniform or vary?
- Are there features that must stay fixed while others scale (e.g. mounting hole spacing is fixed but overall size varies)?
- Does this part need to mate with another part (a retention groove, a snap-fit, an alignment/fastener hole)? Unlike `cad-reverse`, there's no reference mesh to detect this from — if the description doesn't call it out, ask rather than assume no mating feature is needed.

Once you have enough to produce a correct script, proceed to Step 2. If the description is already fully specified, skip directly to Step 2.

---

## Step 2 — Generate the script

Write a FreeCAD Python script following all conventions below. Save it to:

    cad-scripts/<part-name>/<part-name>.py

where `<part-name>` is a short, lowercase, hyphen-separated name derived from the part description (e.g. `mounting-bracket`, `standoff-m3`, `snap-clip`). Create the `cad-scripts/<part-name>/` directory if it doesn't exist yet.

### Script conventions

**Imports and document setup:**

```python
import FreeCAD
import Part

doc = FreeCAD.newDocument("PartName")
```

**Parameters — use a Spreadsheet document object, not plain Python variables.**

Every dimension that could reasonably vary must be a named alias in a `Spreadsheet::Sheet` object. This is what makes the model editable in the FreeCAD GUI — changing a cell value and pressing Ctrl+R rebuilds the entire model.

```python
# --- Parameters (Spreadsheet) ---
sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")

# Primary parameters: label in col A, value in col B, alias on col B
sheet.set("A1", "length");       sheet.set("B1", "80.0");  sheet.setAlias("B1", "length")
sheet.set("A2", "width");        sheet.set("B2", "40.0");  sheet.setAlias("B2", "width")
sheet.set("A3", "height");       sheet.set("B3", "10.0");  sheet.setAlias("B3", "height")
sheet.set("A4", "wall");         sheet.set("B4", "2.5");   sheet.setAlias("B4", "wall")
sheet.set("A5", "hole_dia");     sheet.set("B5", "3.2");   sheet.setAlias("B5", "hole_dia")
sheet.set("A6", "hole_spacing"); sheet.set("B6", "60.0");  sheet.setAlias("B6", "hole_spacing")
sheet.set("A7", "fillet_r");     sheet.set("B7", "1.0");   sheet.setAlias("B7", "fillet_r")

# Derived dimensions: use spreadsheet formulas referencing primary cells (e.g. =B1/2)
# This keeps expressions in geometry objects simple and single-level.
sheet.set("A8", "hole_r");       sheet.set("B8", "=B5/2");             sheet.setAlias("B8", "hole_r")
sheet.set("A9", "inner_width");  sheet.set("B9", "=B2 - 2 * B4");     sheet.setAlias("B9", "inner_width")

doc.recompute()
```

Rules:
- Do **not** use plain Python variables for any dimension that controls geometry.
- Put all derived/computed values in the spreadsheet too (as formulas), not as Python expressions. This keeps geometry object expressions simple.
- Use cell references (`=B1 / 2`) rather than re-typing values in derived rows.

**Geometry — PartDesign (`Body`/`Sketch`/`Pad`/`Pocket`/`Hole`/`AdditiveLoft`/`AdditivePipe`) is the default construction method.** This is closer to how a human designer actually works — sketch a profile, then build the solid up from it — and it's what makes mating features (grooves, holes) and continuously-varying profiles (tapers, swept rails) all fall out of the same convention instead of needing a separate escape hatch for each.

**Exception — a part that is genuinely and entirely one bare primitive** (a single box, a single cylinder, nothing else going on) can skip PartDesign and just be the primitive directly:

```python
# Base plate — the whole part is this one box, nothing else
plate = doc.addObject("Part::Box", "Plate")
plate.setExpression("Length", "Parameters.length")
plate.setExpression("Width",  "Parameters.width")
plate.setExpression("Height", "Parameters.height")
```

Available Part primitive types and their key properties, for this exception case only:
- `Part::Box` — `Length`, `Width`, `Height`
- `Part::Cylinder` — `Radius`, `Height`, `Angle` (default 360°)
- `Part::Cone` — `Radius1`, `Radius2`, `Height`
- `Part::Sphere` — `Radius`
- `Part::Torus` — `Radius1` (major), `Radius2` (tube)

For translations and positioning always use `setExpression()` on `Placement.Base.x/y/z`.

**The moment a part has more than one feature — any pocket, hole, groove, mating feature, or non-axis-aligned profile — build it as a `PartDesign::Body`.** `Draft::Wire` still does not work in this pipeline — it throws `ImportError` under the plain `python3 <script>.py` invocation `cad-build` uses (it needs FreeCAD's Gui subsystem). Profiles are `Sketcher::SketchObject`s attached to the Body's datum planes or to a prior feature's face, and constraints still bind to the spreadsheet exactly like a primitive's dimensions do:

```python
import Sketcher
import PartDesign

body = doc.addObject("PartDesign::Body", "Body")

# Base sketch on the XY plane
base_sketch = body.newObject("Sketcher::SketchObject", "BaseSketch")
base_sketch.AttachmentSupport = [(doc.XY_Plane, "")]
base_sketch.MapMode = "FlatFace"
# ... addGeometry + addConstraint calls, fully constrained (see Rules below) ...

# Pad the base sketch into a solid
pad = body.newObject("PartDesign::Pad", "Pad")
pad.Profile = base_sketch
pad.setExpression("Length", "Parameters.height")
pad.Reversed = False
doc.recompute()

# A mounting hole: sketch a circle center point on a face, then Hole cuts it through
hole_sketch = body.newObject("Sketcher::SketchObject", "HoleSketch")
hole_sketch.AttachmentSupport = [(pad, "Face6")]  # the specific face the hole sits on
hole_sketch.MapMode = "FlatFace"
# ... a single fully-constrained point (or tiny construction circle) locating the hole center ...

hole = body.newObject("PartDesign::Hole", "Hole1")
hole.Profile = hole_sketch
hole.setExpression("Diameter", "Parameters.hole_dia")
hole.DepthType = "ThroughAll"
doc.recompute()
```

A groove or other pocket-shaped mating feature follows the same pattern as the hole above, but with `PartDesign::Pocket` (`Profile`, and either `pocket.setExpression("Length", ...)` with `pocket.Type = "Length"` for a dimension-driven depth, or `pocket.Type = "ThroughAll"` to cut all the way through) instead of `PartDesign::Hole`.

**A continuously-varying profile** (a taper, a swept rail — the case that used to reach for standalone `Part::Loft`/`Part::Sweep`) is now `PartDesign::AdditiveLoft` (or `AdditivePipe` for a swept rail), built from sketches within the same Body rather than a separate document object:

```python
# Section sketches along the taper — use enough of them to represent the real curve,
# not just the two endpoints (see Rules below for why that matters)
section1 = body.newObject("Sketcher::SketchObject", "Section1")
# ... attached/placed at the taper's start, fully constrained ...
section2 = body.newObject("Sketcher::SketchObject", "Section2")
# ... attached/placed partway along the taper, fully constrained ...
section3 = body.newObject("Sketcher::SketchObject", "Section3")
# ... attached/placed at the taper's end, fully constrained ...

loft = body.newObject("PartDesign::AdditiveLoft", "Loft")
loft.Profile = section1
loft.Sections = [section2, section3]
doc.recompute()
```

**Repeating features** — loop to instantiate multiple `Pocket`/`Hole`/`Pad` features within the same Body (or multiple bare primitives, in the trivial-primitive exception case), naming each one with an index:

```python
for i in range(int(sheet.get("B_hole_count"))):
    hole_sketch = body.newObject("Sketcher::SketchObject", f"HoleSketch{i}")
    hole_sketch.AttachmentSupport = [(pad, "Face6")]
    hole_sketch.MapMode = "FlatFace"
    hole_sketch.AttachmentOffset = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
    hole_sketch.setExpression("AttachmentOffset.Position.x", f"{i} * Parameters.hole_spacing")
    # ... fully-constrained hole-center point ...
    hole = body.newObject("PartDesign::Hole", f"Hole{i}")
    hole.Profile = hole_sketch
    hole.setExpression("Diameter", "Parameters.hole_dia")
    hole.DepthType = "ThroughAll"
```

**Combining independent solids — `Part::Cut`/`Fuse`/`Common` between `PartDesign::Body` objects (or bare primitives).** A single Body's own feature chain (Pad/Pocket/Hole/Loft) is now the default way to carve one contiguous solid — reach for a top-level boolean only when a part genuinely consists of two independently-sketched solids that don't share one feature-chain lineage:

```python
cut1 = doc.addObject("Part::Cut", "Result")
cut1.Base = body           # a PartDesign::Body works here too — use body.Tip or the Body itself
cut1.Tool = other_body
```

Available boolean types:
- `Part::Cut`  — `Base`, `Tool`
- `Part::Fuse` — `Base`, `Tool`
- `Part::Common` — `Base`, `Tool`
- `Part::MultiCommon`, `Part::MultiFuse` — `Shapes` (list)

**Rules:**
- Only the meaningful tunable dimensions (a constraint, an offset) need a spreadsheet alias via `setExpression` — this is the one place the "never a plain Python variable" rule relaxes: a sketch's own wire topology can be Python-computed from those dimensions rather than every vertex needing its own cell.
- **Fully constrain every sketch — position, not just size.** An under-constrained sketch (or one with a mismatched `Horizontal`/`Vertical` constraint against the actual edge orientation — easy to get backwards when indexing edges by hand) can produce a shape that looks completely normal on casual inspection (`repr()`, `.Wires`) but is **silently null under `.isValid()`'s deep check**, or silently wrong (a hole/groove in the wrong place) — a trap caught by testing, not by reading the code. Assert `sketch.FullyConstrained` right after building each one, before wiring it into a Pad/Pocket/Hole/Loft.
- **A sketch's `AttachmentSupport` face reference (e.g. `"Face6"`) is only as stable as the feature that produced it** — FreeCAD's face numbering can shift if an upstream feature (dimensions, order) changes. Pick the face by inspecting the actual prior feature's `.Shape.Faces` in the script (e.g. by position/normal) rather than hardcoding a face name from a one-off guess, when the part's parametrization could plausibly change which face ends up where.
- Structural switches (`Pocket.Type`, `Hole.DepthType`, `Pad.Reversed`, `Loft`/`Sweep`'s legacy `Ruled`/`Solid`/`Closed` if a standalone `Part::Loft`/`Sweep` is ever still used) are not measured dimensions — set them as plain Python values unless a part genuinely needs one to vary parametrically. If it does, bind it to a **numeric** `0`/`1` spreadsheet cell: a text `'True'`/`'False'` cell parses without error but silently evaluates to `False`.
- **Never set `Pad`/`Pocket`'s `Midplane` property — it's deprecated and can silently fail to take effect** (FreeCAD logs it as replaced by `SideType`, and has been observed reporting the stored value as `False` even when the script set `Midplane = True`, leaving the feature built one-sided instead of centered, with no exception raised). Use `feature.SideType = "Symmetric"` instead of `Midplane = True` (other values: `"One side"`, `"Two sides"`).
- **A loft built from only its two endpoint sections is a straight-line interpolation between them, not the real curve you meant to describe.** If a tapering/varying profile has a shape more complex than a straight interpolation between its start and end, use enough intermediate section sketches (one per meaningfully distinct cross-section) for the loft/pipe to actually follow that curve.
- **`Pad`/`Pocket`/`Hole`/`Loft`/`Sweep` can all silently produce invalid or wrong-topology geometry with no error indicator** (open-contour sections, orientation-dependent twists, self-intersecting lofts/sweeps, a Pocket that fails to fully cut are all documented FreeCAD failure modes). Any script using them must assert the final shape before saving, against the Body's resulting tip shape:

```python
if not body.Tip.Shape.isValid() or len(body.Tip.Shape.Solids) != 1:
    raise RuntimeError(
        f"Invalid or non-solid geometry after {body.Tip.Name}: "
        f"isValid={body.Tip.Shape.isValid()}, solids={len(body.Tip.Shape.Solids)}"
    )
```

This is a targeted check against PartDesign's specific known failure class, not a general geometry-quality pass — that's the separate parametric-quality skill's territory.

**For a `PartDesign::Body` part, hide everything but the finished solid before saving.** `Pad`/`Pocket`/`Hole`/`Loft` features correctly hide the *feature* they supersede, but not the *sketch* that feature was built from — with a real part's worth of sketches (base, section, boss, hole profiles) all left visible, the GUI shows an unreadable tangle of overlapping wireframes instead of the finished part, making visual QA impossible. `Visibility` is an App-level property, readable/settable headlessly (no `FreeCADGui` import needed) — add this right before saving:

```python
for obj in doc.Objects:
    if hasattr(obj, "Visibility"):
        obj.Visibility = False
body.Tip.Visibility = True
body.Visibility = True
```

**Recompute and save — always the last steps:**

```python
doc.recompute()

# Save parametric model (editable in FreeCAD GUI)
doc.saveAs("cad-scripts/<part-name>/<part-name>.FCStd")
print("Saved: cad-scripts/<part-name>/<part-name>.FCStd")
```

Do **not** export an STL from the script. The user will verify geometry in FreeCAD first, then export for slicing themselves.

**Comments** — add a one-line comment before each distinct geometric operation explaining what it creates or does.

---

## Step 3 — Print parameter summary

After writing the script, print a summary table of all named parameters and their default values so the user can review before running:

```
Parameters for <part-name>.py:
  length        =  80.0 mm   overall length
  width         =  40.0 mm   overall width
  ...
```

---

## Step 4 — Write the project README

Write `cad-scripts/<part-name>/README.md` describing the part: what it is, a one-paragraph geometry summary (how it's built from the primitives/booleans above), and a parameters table (alias, default, meaning). Follow the existing part directories (`wall-bumper`, `sander-vac-adapter`, etc.) as the template, including a **Caveat**/deviation note if this script departs from the standard conventions above.

---

## Step 5 — Prompt the user to review and build

End with:

> Script saved to `cad-scripts/<part-name>/<part-name>.py` (with `README.md` alongside it). Review it, then run `/cad-build <part-name>` to generate the `.FCStd` file.
>
> Open the `.FCStd` in FreeCAD to verify geometry. To change a dimension, select the **Parameters** spreadsheet in the model tree, edit the value, and press **Ctrl+R** to recompute. Export to STL from FreeCAD when the geometry looks correct.
