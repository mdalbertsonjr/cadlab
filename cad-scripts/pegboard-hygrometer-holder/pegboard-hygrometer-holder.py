import FreeCAD
import Part
import math

doc = FreeCAD.newDocument("PegboardHygrometerHolder")

# --- Parameters (Spreadsheet) ---
# Coordinate system: X = width (left-right), Y = height (bottom-top), Z = depth (Z=0 is open front, Z=outer_depth is back)
sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")

# Primary parameters
sheet.set("A1",  "hygrometer_width");   sheet.set("B1",  "47.0"); sheet.setAlias("B1",  "hygrometer_width")
sheet.set("A2",  "hygrometer_height");  sheet.set("B2",  "25.0"); sheet.setAlias("B2",  "hygrometer_height")
sheet.set("A3",  "hygrometer_depth");   sheet.set("B3",  "14.5"); sheet.setAlias("B3",  "hygrometer_depth")
sheet.set("A4",  "peg_spacing");        sheet.set("B4",  "25.0"); sheet.setAlias("B4",  "peg_spacing")
sheet.set("A5",  "peg_hole_diameter");  sheet.set("B5",  "4.5");  sheet.setAlias("B5",  "peg_hole_diameter")
sheet.set("A6",  "peg_hook_depth");     sheet.set("B6",  "8.0");  sheet.setAlias("B6",  "peg_hook_depth")
sheet.set("A7",  "wall_thickness");     sheet.set("B7",  "2.0");  sheet.setAlias("B7",  "wall_thickness")
sheet.set("A8",  "tolerance");          sheet.set("B8",  "0.2");  sheet.setAlias("B8",  "tolerance")
sheet.set("A9",  "vent_width");         sheet.set("B9",  "8.0");  sheet.setAlias("B9",  "vent_width")
sheet.set("A10", "rib_width");          sheet.set("B10", "3.0");  sheet.setAlias("B10", "rib_width")
sheet.set("A11", "rib_thickness");      sheet.set("B11", "1.5");  sheet.setAlias("B11", "rib_thickness")

# Derived dimensions
sheet.set("A12", "outer_width");   sheet.set("B12", "=B1 + 2 * B8 + 2 * B7");       sheet.setAlias("B12", "outer_width")
sheet.set("A13", "outer_height");  sheet.set("B13", "=B2 + 2 * B8 + 2 * B7");       sheet.setAlias("B13", "outer_height")
sheet.set("A14", "outer_depth");   sheet.set("B14", "=B3 + B7");                    sheet.setAlias("B14", "outer_depth")
sheet.set("A15", "pocket_width");  sheet.set("B15", "=B1 + 2 * B8");               sheet.setAlias("B15", "pocket_width")
sheet.set("A16", "pocket_height"); sheet.set("B16", "=B2 + 2 * B8");               sheet.setAlias("B16", "pocket_height")
sheet.set("A17", "peg_radius");    sheet.set("B17", "=(B5 - 0.5) / 2");            sheet.setAlias("B17", "peg_radius")
sheet.set("A18", "peg_center_y");  sheet.set("B18", "=B13 / 2");                   sheet.setAlias("B18", "peg_center_y")
sheet.set("A19", "peg_center_x1"); sheet.set("B19", "=(B12 - B4) / 2");            sheet.setAlias("B19", "peg_center_x1")
sheet.set("A20", "peg_center_x2"); sheet.set("B20", "=(B12 + B4) / 2");            sheet.setAlias("B20", "peg_center_x2")
sheet.set("A21", "vent_right_x");  sheet.set("B21", "=B12 - B7 - B9");             sheet.setAlias("B21", "vent_right_x")
# rib_length is the full diagonal of the pocket — used for the X rib Length expression
sheet.set("A22", "rib_length");    sheet.set("B22", "=sqrt(B15 ^ 2 + B16 ^ 2)");  sheet.setAlias("B22", "rib_length")

doc.recompute()

# --- Geometry ---

# Full outer bounding box
outer_box = doc.addObject("Part::Box", "OuterBox")
outer_box.setExpression("Length", "Parameters.outer_width")
outer_box.setExpression("Width",  "Parameters.outer_height")
outer_box.setExpression("Height", "Parameters.outer_depth")

# Interior pocket — four-walled, open only at the front (Z=0)
pocket = doc.addObject("Part::Box", "InnerPocket")
pocket.setExpression("Length", "Parameters.pocket_width")
pocket.setExpression("Width",  "Parameters.pocket_height")
pocket.setExpression("Height", "Parameters.hygrometer_depth")
pocket.setExpression("Placement.Base.x", "Parameters.wall_thickness")
pocket.setExpression("Placement.Base.y", "Parameters.wall_thickness")
pocket.setExpression("Placement.Base.z", "0")

# Cut pocket from outer box — four-walled cradle shell
cradle_shell = doc.addObject("Part::Cut", "CradleShell")
cradle_shell.Base = outer_box
cradle_shell.Tool = pocket

# Left pegboard peg — cylinder protruding in +Z from back face
peg1 = doc.addObject("Part::Cylinder", "Peg1")
peg1.setExpression("Radius", "Parameters.peg_radius")
peg1.setExpression("Height", "Parameters.peg_hook_depth")
peg1.setExpression("Placement.Base.x", "Parameters.peg_center_x1")
peg1.setExpression("Placement.Base.y", "Parameters.peg_center_y")
peg1.setExpression("Placement.Base.z", "Parameters.outer_depth")

# Right pegboard peg
peg2 = doc.addObject("Part::Cylinder", "Peg2")
peg2.setExpression("Radius", "Parameters.peg_radius")
peg2.setExpression("Height", "Parameters.peg_hook_depth")
peg2.setExpression("Placement.Base.x", "Parameters.peg_center_x2")
peg2.setExpression("Placement.Base.y", "Parameters.peg_center_y")
peg2.setExpression("Placement.Base.z", "Parameters.outer_depth")

# Fuse left peg
with_peg1 = doc.addObject("Part::Fuse", "WithPeg1")
with_peg1.Base = cradle_shell
with_peg1.Tool = peg1

# Fuse right peg
with_peg2 = doc.addObject("Part::Fuse", "WithPeg2")
with_peg2.Base = with_peg1
with_peg2.Tool = peg2

# Left ventilation slot — through back wall on the left side
vent_left = doc.addObject("Part::Box", "VentLeft")
vent_left.setExpression("Length", "Parameters.vent_width")
vent_left.setExpression("Width",  "Parameters.pocket_height")
vent_left.setExpression("Height", "Parameters.wall_thickness")
vent_left.setExpression("Placement.Base.x", "Parameters.wall_thickness")
vent_left.setExpression("Placement.Base.y", "Parameters.wall_thickness")
vent_left.setExpression("Placement.Base.z", "Parameters.hygrometer_depth")

# Right ventilation slot — through back wall on the right side
vent_right = doc.addObject("Part::Box", "VentRight")
vent_right.setExpression("Length", "Parameters.vent_width")
vent_right.setExpression("Width",  "Parameters.pocket_height")
vent_right.setExpression("Height", "Parameters.wall_thickness")
vent_right.setExpression("Placement.Base.x", "Parameters.vent_right_x")
vent_right.setExpression("Placement.Base.y", "Parameters.wall_thickness")
vent_right.setExpression("Placement.Base.z", "Parameters.hygrometer_depth")

# Cut left vent
with_vent_left = doc.addObject("Part::Cut", "WithVentLeft")
with_vent_left.Base = with_peg2
with_vent_left.Tool = vent_left

# Cut right vent
with_vent_right = doc.addObject("Part::Cut", "WithVentRight")
with_vent_right.Base = with_vent_left
with_vent_right.Tool = vent_right

# --- X ribs on exterior back face ---
# Two diagonal ribs crossing the back face corner-to-corner.
# rib_width and rib_thickness are parametric via the spreadsheet.
# Rib placement angle is computed from pocket dimensions using Python math;
# editing B1/B2 in the FreeCAD GUI won't move the ribs — re-run the script instead.

# Values that drive rib placement — mirror B1-B11 in the spreadsheet
_hw, _hh, _wt, _tol = 47.0, 25.0, 2.0, 0.2
_pw = _hw + 2 * _tol                      # pocket_width
_ph = _hh + 2 * _tol                      # pocket_height
_ow = _hw + 2 * _tol + 2 * _wt           # outer_width
_oh = _hh + 2 * _tol + 2 * _wt           # outer_height
_od = 14.5 + _wt                          # outer_depth
_rib_w = 3.0                              # rib_width (must match B10)
_rib_len = math.sqrt(_pw**2 + _ph**2)    # diagonal of pocket interior
_angle = math.degrees(math.atan2(_ph, _pw))  # degrees from +X toward top-right corner
_cx, _cy = _ow / 2, _oh / 2              # center of back face

def _rib_placement(cx, cy, z, length, width, angle_deg):
    """Placement for a box of (length x width) centred at (cx, cy, z), rotated angle_deg around Z."""
    a = math.radians(angle_deg)
    ox = -math.cos(a) * length / 2 + math.sin(a) * width / 2
    oy = -math.sin(a) * length / 2 - math.cos(a) * width / 2
    return FreeCAD.Placement(
        FreeCAD.Vector(cx + ox, cy + oy, z),
        FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), angle_deg)
    )

# Rib 1: bottom-left inner corner → top-right inner corner
rib1 = doc.addObject("Part::Box", "Rib1")
rib1.setExpression("Length", "Parameters.rib_length")
rib1.setExpression("Width",  "Parameters.rib_width")
rib1.setExpression("Height", "Parameters.rib_thickness")
rib1.Placement = _rib_placement(_cx, _cy, _od, _rib_len, _rib_w, _angle)

# Rib 2: top-left inner corner → bottom-right inner corner
rib2 = doc.addObject("Part::Box", "Rib2")
rib2.setExpression("Length", "Parameters.rib_length")
rib2.setExpression("Width",  "Parameters.rib_width")
rib2.setExpression("Height", "Parameters.rib_thickness")
rib2.Placement = _rib_placement(_cx, _cy, _od, _rib_len, _rib_w, -_angle)

# Fuse Rib1
with_rib1 = doc.addObject("Part::Fuse", "WithRib1")
with_rib1.Base = with_vent_right
with_rib1.Tool = rib1

# Fuse Rib2 — final printable solid
result = doc.addObject("Part::Fuse", "Result")
result.Base = with_rib1
result.Tool = rib2

doc.recompute()

doc.saveAs("/home/developer/cad-output/pegboard-hygrometer-holder.FCStd")
print("Saved: /home/developer/cad-output/pegboard-hygrometer-holder.FCStd")
