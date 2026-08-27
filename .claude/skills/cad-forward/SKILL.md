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

**Geometry — use Part document objects, not raw `Part.make*` shapes.**

Geometry must be created as named document objects so they appear in the FreeCAD model tree. Every dimension property must use `setExpression()` referencing the spreadsheet via `Parameters.<alias>`.

```python
# Base plate
plate = doc.addObject("Part::Box", "Plate")
plate.setExpression("Length", "Parameters.length")
plate.setExpression("Width",  "Parameters.width")
plate.setExpression("Height", "Parameters.height")

# Mounting hole (cylinder)
hole = doc.addObject("Part::Cylinder", "Hole1")
hole.setExpression("Radius", "Parameters.hole_r")
hole.setExpression("Height", "Parameters.height")
hole.setExpression("Placement.Base.x", "(Parameters.length - Parameters.hole_spacing) / 2")
hole.setExpression("Placement.Base.y", "Parameters.width / 2")
```

Available Part document object types and their key properties:
- `Part::Box` — `Length`, `Width`, `Height`
- `Part::Cylinder` — `Radius`, `Height`, `Angle` (default 360°)
- `Part::Cone` — `Radius1`, `Radius2`, `Height`
- `Part::Sphere` — `Radius`
- `Part::Torus` — `Radius1` (major), `Radius2` (tube)

For translations and positioning always use `setExpression()` on `Placement.Base.x/y/z`.

**Boolean operations — use Part document objects, not `.cut()` / `.fuse()` on shapes.**

```python
# Subtract hole from plate
result = doc.addObject("Part::Cut", "Result")
result.Base = plate
result.Tool = hole
```

Available boolean types:
- `Part::Cut`  — `Base`, `Tool`
- `Part::Fuse` — `Base`, `Tool`
- `Part::Common` — `Base`, `Tool`
- `Part::MultiCommon`, `Part::MultiFuse` — `Shapes` (list)

For multiple sequential boolean ops, chain them:

```python
cut1 = doc.addObject("Part::Cut", "Cut1")
cut1.Base = plate
cut1.Tool = hole1

cut2 = doc.addObject("Part::Cut", "Result")
cut2.Base = cut1
cut2.Tool = hole2
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
