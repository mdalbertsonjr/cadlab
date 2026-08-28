---
name: cad-reverse
description: Existing model + metadata → parametric FreeCAD Python script saved to cad-scripts/
argument-hint: <model-file> [metadata: key dimensions, functional intent, parameter relationships]
---

You are a CAD engineer specializing in reverse engineering. Your job is to analyze an existing model file with user-provided metadata and produce a clean, parametric FreeCAD Python script that reconstructs the model's geometry from named parameters — following the same script conventions as `cad-forward`.

**Arguments:** $ARGUMENTS

The first word/path is the model file. Everything after it is metadata (key dimensions, material, functional intent, known parameter relationships such as "shelf spacing scales with can diameter").

---

## Step 1 — Parse arguments and inspect the model

Extract the model file path and metadata from `$ARGUMENTS`.

Inspect the model file to cross-reference with the provided metadata:

- **STL files:** Read the binary or ASCII vertex data to estimate overall bounding box and key dimensions. Look for repeating geometric patterns (arrays of features, symmetry axes) that suggest parametric relationships.
- **STEP files:** Parse the geometry tree to identify named solids, faces, and their dimensions.
- **`.FCStd` files:** Open with FreeCAD and inspect the document tree for existing features, constraints, and expressions.
- **3MF files:** Slicer-exported 3MF (Bambu Studio, PrusaSlicer, etc.) is mesh data, not BREP — treat it like STL. Load it with FreeCAD's bundled `python3` via `Mesh.insert(path, doc.Name)` (the `Mesh` module reads 3MF directly), which produces a `Mesh::Feature`; then inspect its vertex data the same way as an STL for bounding box and repeating features. A 3MF with multiple objects/plates yields one `Mesh::Feature` per object — treat each as a separate part unless the metadata says they're one assembly.

If the file does not exist or cannot be read, stop and tell the user.

**Assembly context — look for mating features when a neighboring part's geometry is available.** If the model file (or a sibling file the user points to) bundles multiple objects that mate together — a multi-object 3MF/STEP, or several separate reference files for one assembly — inspect the target part's mesh *alongside* its neighbors, not in isolation. A neighbor's geometry can reveal negative-space features that exist specifically to interface with it (a retention groove, a snap-fit lip, an alignment/fastener hole) that are invisible or ambiguous from the target part's mesh alone. Carry any candidates into Step 2 as inferred parameters, same as a measured dimension. If no assembly context is available, do not invent mating features from a single part's mesh in isolation — distinguishing a functional negative-space feature from a cosmetic one isn't reliably possible from one part alone; rely on the user's metadata instead.

---

## Step 2 — Infer parameters

From the inspection and provided metadata, identify the key parameters that drive the model's geometry. Examples:

- `can_diameter`, `can_height` → drives slot sizing and vertical spacing
- `wall_thickness` → drives structural shell
- `shelf_count` → drives array repetition
- `base_width`, `base_depth` → drives footprint
- a mating feature found via assembly-context inspection in Step 1 (e.g. `lid_groove_width`, `fastener_hole_diameter`) — its position, sizing, and what it mates with

For each inferred parameter, note:
- Its name and default value (from metadata or measured from the model)
- What geometry it controls
- Any derived relationships (e.g. `shelf_spacing = can_height + clearance`)

Print the inferred parameter list and ask the user to **confirm or correct** before proceeding to Step 3. Do not generate the script until the user approves the parameter list.

---

## Step 3 — Generate the parametric script

Once the user confirms (or corrects) the parameter list, generate a FreeCAD Python script following all conventions below. Save it to:

    cad-scripts/<part-name>/<part-name>-parametric.py

where `<part-name>` is a short, lowercase, hyphen-separated name derived from the model file name or description (e.g. `can-dispenser`, `shelf-bracket`). Create the `cad-scripts/<part-name>/` directory if it doesn't exist yet.

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
sheet.set("A1", "can_diameter");   sheet.set("B1", "66.0");   sheet.setAlias("B1", "can_diameter")
sheet.set("A2", "can_height");     sheet.set("B2", "122.0");  sheet.setAlias("B2", "can_height")
sheet.set("A3", "shelf_count");    sheet.set("B3", "3");      sheet.setAlias("B3", "shelf_count")
sheet.set("A4", "wall");           sheet.set("B4", "2.5");    sheet.setAlias("B4", "wall")
sheet.set("A5", "clearance");      sheet.set("B5", "1.0");    sheet.setAlias("B5", "clearance")

# Derived dimensions: use spreadsheet formulas referencing primary cells
sheet.set("A6", "can_r");          sheet.set("B6", "=B1/2");                       sheet.setAlias("B6", "can_r")
sheet.set("A7", "slot_width");     sheet.set("B7", "=B1 + B5");                    sheet.setAlias("B7", "slot_width")
sheet.set("A8", "shelf_spacing");  sheet.set("B8", "=B2 + B5");                    sheet.setAlias("B8", "shelf_spacing")
sheet.set("A9", "total_height");   sheet.set("B9", "=B3 * B8 + 2 * B4");          sheet.setAlias("B9", "total_height")

doc.recompute()
```

Rules:
- Do **not** use plain Python variables for any dimension that controls geometry.
- Put all derived/computed values in the spreadsheet too (as formulas), not as Python expressions.
- Use cell references (`=B1 / 2`) rather than re-typing values in derived rows.

**Geometry — PartDesign (`Body`/`Sketch`/`Pad`/`Pocket`/`Hole`/`AdditiveLoft`/`AdditivePipe`) is the default construction method.** This is closer to how a human designer actually works — sketch a profile, then build the solid up from it — and it's what makes mating features (grooves, holes) and continuously-varying profiles (tapers, swept rails) all fall out of the same convention instead of needing a separate escape hatch for each.

**Exception — a part that is genuinely and entirely one bare primitive** (a single box, a single cylinder, nothing else going on) can skip PartDesign and just be the primitive directly:

```python
# Outer shell — the whole part is this one box, nothing else
shell = doc.addObject("Part::Box", "Shell")
shell.setExpression("Length", "Parameters.slot_width + 2 * Parameters.wall")
shell.setExpression("Width",  "Parameters.can_height + 2 * Parameters.wall")
shell.setExpression("Height", "Parameters.total_height")
```

Available Part primitive types and their key properties, for this exception case only:
- `Part::Box` — `Length`, `Width`, `Height`
- `Part::Cylinder` — `Radius`, `Height`, `Angle` (default 360°)
- `Part::Cone` — `Radius1`, `Radius2`, `Height`
- `Part::Sphere` — `Radius`
- `Part::Torus` — `Radius1` (major), `Radius2` (tube)

For translations and positioning always use `setExpression()` on `Placement.Base.x/y/z`.

**The moment a part has more than one feature — any pocket, hole, groove, mating feature, or non-axis-aligned profile — build it as a `PartDesign::Body`.** `Draft::Wire` still does not work in this pipeline — it throws `ImportError` under the plain `python3 <script>.py` invocation `cad-build` uses (it needs FreeCAD's Gui subsystem). Profiles are `Sketcher::SketchObject`s, same as before, but now attached to the Body's datum planes or to a prior feature's face, and constraints still bind to the spreadsheet exactly like a primitive's dimensions do:

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
pad.setExpression("Length", "Parameters.pad_length")
pad.Reversed = False
doc.recompute()

# A groove: sketch on the Pad's top face, then Pocket cuts it in
pocket_sketch = body.newObject("Sketcher::SketchObject", "PocketSketch")
pocket_sketch.AttachmentSupport = [(pad, "Face6")]  # the specific face the groove sits on
pocket_sketch.MapMode = "FlatFace"
# ... fully-constrained rectangle/profile geometry ...

pocket = body.newObject("PartDesign::Pocket", "Pocket")
pocket.Profile = pocket_sketch
pocket.setExpression("Length", "Parameters.groove_depth")
pocket.Type = "Length"  # dimension-driven depth, not "ThroughAll"/"UpToFace"/etc.
doc.recompute()

# A fastener hole: sketch a circle center point on a face, then Hole cuts it through
hole_sketch = body.newObject("Sketcher::SketchObject", "HoleSketch")
hole_sketch.AttachmentSupport = [(pocket, "Face1")]
hole_sketch.MapMode = "FlatFace"
# ... a single fully-constrained point (or tiny construction circle) locating the hole center ...

hole = body.newObject("PartDesign::Hole", "Hole")
hole.Profile = hole_sketch
hole.setExpression("Diameter", "Parameters.fastener_hole_diameter")
hole.DepthType = "ThroughAll"
doc.recompute()
```

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
for i in range(int(sheet.get("B3"))):  # shelf_count — read int from spreadsheet
    slot_sketch = body.newObject("Sketcher::SketchObject", f"SlotSketch{i}")
    slot_sketch.AttachmentSupport = [(pad, "Face6")]
    slot_sketch.MapMode = "FlatFace"
    slot_sketch.AttachmentOffset = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
    slot_sketch.setExpression("AttachmentOffset.Position.z", f"{i} * Parameters.shelf_spacing")
    # ... fully-constrained slot profile ...
    slot = body.newObject("PartDesign::Pocket", f"Slot{i}")
    slot.Profile = slot_sketch
    slot.setExpression("Length", "Parameters.wall")
```

**Combining independent solids — `Part::Cut`/`Fuse`/`Common` between `PartDesign::Body` objects (or bare primitives).** A single Body's own feature chain (Pad/Pocket/Hole/Loft) is now the default way to carve one contiguous solid — reach for a top-level boolean only when a part genuinely consists of two independently-sketched solids that don't share one feature-chain lineage (e.g. two Bodies fused together, or a Body cut by a bare primitive):

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
- **Fully constrain every sketch — position, not just size.** An under-constrained sketch (or one with a mismatched `Horizontal`/`Vertical` constraint against the actual edge orientation — easy to get backwards when indexing edges by hand) can produce a shape that looks completely normal on casual inspection (`repr()`, `.Wires`) but is **silently null under `.isValid()`'s deep check**, or silently wrong (a groove/hole in the wrong place) — a trap caught by testing, not by reading the code. Assert `sketch.FullyConstrained` right after building each one, before wiring it into a Pad/Pocket/Hole/Loft.
- **A sketch's `AttachmentSupport` face reference (e.g. `"Face6"`) is only as stable as the feature that produced it** — FreeCAD's face numbering can shift if an upstream feature (dimensions, order) changes. Pick the face by inspecting the actual prior feature's `.Shape.Faces` in the script (e.g. by position/normal) rather than hardcoding a face name from a one-off GUI inspection, when the part's parametrization could plausibly change which face ends up where.
- Structural switches (`Pocket.Type`, `Hole.DepthType`, `Pad.Reversed`, `Loft`/`Sweep`'s legacy `Ruled`/`Solid`/`Closed` if a standalone `Part::Loft`/`Sweep` is ever still used) are not measured dimensions — set them as plain Python values unless a part genuinely needs one to vary parametrically. If it does, bind it to a **numeric** `0`/`1` spreadsheet cell: a text `'True'`/`'False'` cell parses without error but silently evaluates to `False`.
- **Never set `Pad`/`Pocket`'s `Midplane` property — it's deprecated and can silently fail to take effect** (FreeCAD logs it as replaced by `SideType`, and has been observed reporting the stored value as `False` even when the script set `Midplane = True`, leaving the feature built one-sided instead of centered, with no exception raised). Use `feature.SideType = "Symmetric"` instead of `Midplane = True` (other values: `"One side"`, `"Two sides"`).
- **A loft built from only its two endpoint sections is a straight-line interpolation between them, not the real curve** — this is exactly the bug that made an earlier can-dispenser-ramp rebuild fail QA despite passing its own recompute check: a 2-section `Ruled=True` loft discarded the intermediate cross-section measurements that were actually taken. If Step 1's inspection found the profile changing continuously along an axis, use enough intermediate section sketches (one per meaningfully distinct measured cross-section, not just start and end) for the loft/pipe to actually follow that curve.
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
doc.saveAs("cad-scripts/<part-name>/<part-name>-parametric.FCStd")
print("Saved: cad-scripts/<part-name>/<part-name>-parametric.FCStd")
```

Do **not** export an STL from the script. The user will verify geometry in FreeCAD first, then export for slicing themselves.

**Comments** — add a one-line comment before each distinct geometric operation explaining what it creates or does.

---

## Step 4 — Print parameter summary

After writing the script, print a summary table of all named parameters and their default values, noting what each controls:

```
Parameters for <part-name>-parametric.py:
  can_diameter   =  66.0 mm   standard 330 ml can diameter
  can_height     = 122.0 mm   standard 330 ml can height
  shelf_count    =   3        number of shelves
  wall           =   2.5 mm   shell wall thickness
  clearance      =   1.0 mm   fit clearance around can
```

---

## Step 5 — Write the project README

Write `cad-scripts/<part-name>/README.md` describing the part: what it is, a one-paragraph geometry summary (how it's built from the primitives/booleans above, and how faithfully it matches the source model — call out any deliberate simplification), and a parameters table (alias, default, meaning). Follow the existing part directories (`wall-bumper`, `sander-vac-adapter`, etc.) as the template, including a **Caveat** note for any deviation from the standard conventions or from the original model's geometry.

---

## Step 6 — Prompt the user to review and build

End with:

> Script saved to `cad-scripts/<part-name>/<part-name>-parametric.py` (with `README.md` alongside it). Review it, then run `/cad-build <part-name>-parametric` to generate the `.FCStd` file.
>
> Open the `.FCStd` in FreeCAD to verify geometry against the original model. To test parametric correctness, select the **Parameters** spreadsheet in the model tree, change `can_diameter` or `can_height` to a different can size, press **Ctrl+R**, and confirm the geometry scales correctly. Export to STL from FreeCAD when satisfied.
