import math

import FreeCAD
import Part
import Sketcher
import PartDesign

doc = FreeCAD.newDocument("CanDispenserRamp")

# --- Parameters (Spreadsheet) ---
sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")

def setp(row, name, value):
    sheet.set(f"A{row}", name)
    sheet.set(f"B{row}", value)
    sheet.setAlias(f"B{row}", name)

# Primary parameters (given / measured, independent)
setp(1, "can_diameter", "66.0")
setp(2, "can_height", "122.7")
setp(3, "wall", "3.5")
setp(4, "clearance", "13.0")
setp(5, "side_wall_height", "85.5")
setp(6, "main_length", "182.0")
setp(7, "ramp_rise_length", "51.0")
setp(8, "fastener_hole_diameter", "4.8")
setp(9, "boss_proud", "5.0")
setp(10, "rib_width", "4.8")
setp(11, "rib_thickness", "5.0")
setp(12, "rib_y", "65.4")
# Calibration offset: the original channel_width formula (can_height + 2*wall +
# clearance) predicts an outer half-width of ~71.35mm at default dimensions, but
# direct mesh measurement of the real part found 66.2mm -- a ~5.15mm/side gap.
# Rather than abandon can-size scaling, this offset is subtracted so the formula
# reproduces the measured geometry at default values while still scaling
# proportionally with can_height. Not a physically-derived relationship -- an
# acknowledged calibration constant. See README Caveat.
setp(13, "width_calibration_offset", "5.15")

# Derived (formulas)
sheet.set("A14", "trough_width")
sheet.set("B14", "=B2 + B4 - 2*B13")
sheet.setAlias("B14", "trough_width")
sheet.set("A15", "outer_half_width")
sheet.set("B15", "=B14/2 + B3")
sheet.setAlias("B15", "outer_half_width")
sheet.set("A16", "ramp_length")
sheet.set("B16", "=B6 + B7")
sheet.setAlias("B16", "ramp_length")

doc.recompute()

# --- Geometry: PartDesign Body ---
body = doc.addObject("PartDesign::Body", "Body")


def poly_sketch(name, plane, offset, pts):
    """Fully-constrained N-gon: Coincident closure + absolute DistanceX/DistanceY
    pins on each edge's start point. Works for axis-aligned rectangles and
    arbitrary (e.g. diagonal parallelogram) polygons alike -- avoids the
    Horizontal/Vertical-vs-actual-orientation mismatch footgun entirely."""
    sk = body.newObject("Sketcher::SketchObject", name)
    sk.AttachmentSupport = [(doc.getObject(plane), "")]
    sk.MapMode = "FlatFace"
    sk.AttachmentOffset = FreeCAD.Placement(offset, FreeCAD.Rotation())
    n = len(pts)
    for i in range(n):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % n]), False)
    for i in range(n):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % n, 1))
    for i in range(n):
        sk.addConstraint(Sketcher.Constraint("DistanceX", i, 1, pts[i].x))
        sk.addConstraint(Sketcher.Constraint("DistanceY", i, 1, pts[i].y))
    doc.recompute()
    if not sk.FullyConstrained:
        raise RuntimeError(f"{name} is not fully constrained")
    return sk


def assert_valid_tip(label):
    if not body.Tip.Shape.isValid() or len(body.Tip.Shape.Solids) != 1:
        raise RuntimeError(
            f"Invalid or non-solid geometry after {label} ({body.Tip.Name}): "
            f"isValid={body.Tip.Shape.isValid()}, solids={len(body.Tip.Shape.Solids)}"
        )


# Read current parameter values to compute sketch geometry (Python-computed wire
# topology from spreadsheet-driven dimensions, per the skill's one relaxation of
# "never a plain Python variable" -- the *scaling* relationships still live in the
# spreadsheet and are bound via setExpression below).
outer_half_width = sheet.get("outer_half_width")
side_wall_height = sheet.get("side_wall_height")
trough_width = sheet.get("trough_width")
ramp_length = sheet.get("ramp_length")
wall = sheet.get("wall")

# --- Outer block: full ramp_length prism ---
outer_pts = [
    FreeCAD.Vector(-outer_half_width, 0.0, 0),
    FreeCAD.Vector(outer_half_width, 0.0, 0),
    FreeCAD.Vector(outer_half_width, side_wall_height, 0),
    FreeCAD.Vector(-outer_half_width, side_wall_height, 0),
]
outer_sketch = poly_sketch("OuterProfile", "YZ_Plane", FreeCAD.Vector(0, 0, 0), outer_pts)
# pts[2]=(half_w, side_wall_height) -> DistanceY idx = n + 2*2 + 1 = 9
# pts[3]=(-half_w, side_wall_height) -> DistanceY idx = n + 2*3 + 1 = 11
outer_sketch.setExpression("Constraints[9]", "Parameters.side_wall_height")
outer_sketch.setExpression("Constraints[11]", "Parameters.side_wall_height")

pad = body.newObject("PartDesign::Pad", "OuterPad")
pad.Profile = outer_sketch
pad.Length = ramp_length
pad.setExpression("Length", "Parameters.ramp_length")
pad.Reversed = False
doc.recompute()
assert_valid_tip("OuterPad")

# --- Trough: SubtractiveLoft through the floor-rise profile, open above the ceiling
# so it cuts through the top face. Floor-rise samples are measured, independent
# constants (see README); trough_width is the one dimension here that scales with
# can_height, bound via setExpression on each section.
FLOOR_PROFILE = [
    (0.0, 0.0),
    (182.0, 0.0),
    (190.0, 13.6),
    (202.0, 33.7),
    (214.0, 53.8),
    (226.0, 73.9),
    (232.9, 84.0),
]
CUT_TOP = side_wall_height  # exactly the ceiling -- open at the top face, no further

trough_sketches = []
for i, (s, z) in enumerate(FLOOR_PROFILE):
    half_tw = trough_width / 2.0
    pts = [
        FreeCAD.Vector(-half_tw, z, 0),
        FreeCAD.Vector(half_tw, z, 0),
        FreeCAD.Vector(half_tw, CUT_TOP, 0),
        FreeCAD.Vector(-half_tw, CUT_TOP, 0),
    ]
    sk = poly_sketch(f"TroughSection{i}", "YZ_Plane", FreeCAD.Vector(0, 0, s), pts)
    # p1 (idx0) DistanceX = -trough_width/2, p2 (idx1) DistanceX = trough_width/2
    sk.setExpression("Constraints[4]", "-Parameters.trough_width / 2")
    sk.setExpression("Constraints[6]", "Parameters.trough_width / 2")
    trough_sketches.append(sk)

trough = body.newObject("PartDesign::SubtractiveLoft", "Trough")
trough.Profile = trough_sketches[0]
trough.Sections = trough_sketches[1:]
# Ruled (piecewise-linear between adjacent sections), not smooth: the measured
# floor-rise is itself linear between sample points (~1.677mm Z per mm of length,
# confirmed by dense sampling), so a smooth B-spline loft through 7 sections risks
# overshoot/ringing between control points -- Ruled tracks the real, linear curve
# more faithfully here and avoids that.
trough.Ruled = True
doc.recompute()
assert_valid_tip("Trough")

# --- Rail bosses: 4 lobes (measured, independent), each on both +Y and -Y walls --
# additive ears engaging the Lid's groove (confirmed by user against the reference model).
LOBES = [
    ("ALobe1", 172.6, 177.5, 3.5, 76.9),
    ("ALobe2", 181.0, 188.4, 0.0, 76.9),
    ("BLobe1", 215.0, 220.7, 74.8, 82.3),
    ("BLobe2", 224.0, 231.4, 74.9, 83.0),
]

for name, s0, s1, z0, z1 in LOBES:
    for side, sign in (("Pos", 1), ("Neg", -1)):
        # Inset the inner edge 2mm into the existing wall so the Pad has genuine
        # volume overlap to fuse against, rather than a touching-but-not-overlapping
        # coincident face (which OCC can leave as two separate solids).
        y_in = sign * (outer_half_width - 2.0)
        y_out = sign * (outer_half_width + 5.0)
        pts = [
            FreeCAD.Vector(y_in, z0, 0),
            FreeCAD.Vector(y_out, z0, 0),
            FreeCAD.Vector(y_out, z1, 0),
            FreeCAD.Vector(y_in, z1, 0),
        ]
        sk = poly_sketch(f"{name}{side}Sketch", "YZ_Plane", FreeCAD.Vector(0, 0, s0), pts)
        boss = body.newObject("PartDesign::Pad", f"{name}{side}Pad")
        boss.Profile = sk
        boss.Length = s1 - s0
        boss.Reversed = False
        doc.recompute()
        assert_valid_tip(f"{name}{side}Pad")

# --- Stiffening ribs: repeating diagonal bosses on both side walls. Measured as a
# straight-line spine per tooth (period ~22.83mm along the ramp axis, rise ~35.5mm
# in Z), modeled as a padded parallelogram profile -- equivalent to sweeping a
# rectangular cross-section along that spine, and more robust to build than a
# Sweep/Pipe attachment chain for 12 repeated instances. See README Caveat.
RIB_RUN = 21.0
RIB_RISE = 35.5
RIB_PERIOD = 22.83
RIB_FIRST_START = 34.0
RIB_Z_START = 23.0
RIB_COUNT = 6
rib_thickness = sheet.get("rib_thickness")
rib_y = sheet.get("rib_y")
rib_width = sheet.get("rib_width")

theta = math.atan2(RIB_RISE, RIB_RUN)
nx, nz = -math.sin(theta), math.cos(theta)  # unit normal to the spine

for k in range(RIB_COUNT):
    s_start = RIB_FIRST_START + k * RIB_PERIOD
    half_t = rib_thickness / 2.0
    pts = [
        FreeCAD.Vector(s_start - nx * half_t, RIB_Z_START - nz * half_t, 0),
        FreeCAD.Vector(s_start + nx * half_t, RIB_Z_START + nz * half_t, 0),
        FreeCAD.Vector(s_start + RIB_RUN + nx * half_t, RIB_Z_START + RIB_RISE + nz * half_t, 0),
        FreeCAD.Vector(s_start + RIB_RUN - nx * half_t, RIB_Z_START + RIB_RISE - nz * half_t, 0),
    ]
    for side, sign in (("Pos", 1), ("Neg", -1)):
        sk = poly_sketch(
            f"Rib{k}{side}Sketch", "XZ_Plane", FreeCAD.Vector(0, 0, sign * -rib_y), pts
        )
        rib_pad = body.newObject("PartDesign::Pad", f"Rib{k}{side}Pad")
        rib_pad.Profile = sk
        rib_pad.Length = rib_width
        rib_pad.setExpression("Length", "Parameters.rib_width")
        # SideType="Symmetric", not the deprecated Midplane=True (which silently
        # failed to take effect here -- FreeCAD logged it as "assuming SideType=
        # 'One side'" despite the script setting Midplane=True, leaving every rib
        # offset by half its own thickness instead of centered on rib_y).
        rib_pad.SideType = "Symmetric"
        doc.recompute()
        assert_valid_tip(f"Rib{k}{side}Pad")

# --- Fastener holes: 4 holes matching Open End's pegs, at the floor-rise end
# (measured, independent -- see README).
HOLES = [
    ("Hole1Pos", 161.0, 1),
    ("Hole1Neg", 161.0, -1),
    ("Hole2Pos", 204.0, 1),
    ("Hole2Neg", 204.0, -1),
]
# Measured hole Y (67.6mm, from Open End's peg positions) falls just outside the
# Ramp's own wall band (62.7-66.2mm here) once reconciled against the corrected
# outer_half_width -- likely the same measurement-frame mismatch as the width
# calibration above (Open End's geometry measured independently of the Ramp's).
# Center the hole in the actual wall thickness instead so it lands in real material.
HOLE_Y = outer_half_width - wall / 2.0
HOLE_Z = 42.75  # mid-height of the side wall

for name, s, sign in HOLES:
    sk = body.newObject("Sketcher::SketchObject", f"{name}Sketch")
    # XZ_Plane, not YZ_Plane: a Hole feature drills perpendicular to its sketch
    # plane, and the hole must go THROUGH the wall (the Y direction), not lengthwise
    # down the ramp -- XZ_Plane's normal is Y, matching the rib sketches above.
    sk.AttachmentSupport = [(doc.getObject("XZ_Plane"), "")]
    sk.MapMode = "FlatFace"
    sk.AttachmentOffset = FreeCAD.Placement(FreeCAD.Vector(0, 0, sign * -HOLE_Y), FreeCAD.Rotation())
    center = FreeCAD.Vector(s, HOLE_Z, 0)
    circ = Part.Circle(center, FreeCAD.Vector(0, 0, 1), 2.4)
    sk.addGeometry(circ, False)
    sk.addConstraint(Sketcher.Constraint("Radius", 0, 2.4))
    sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 3, s))
    sk.addConstraint(Sketcher.Constraint("DistanceY", 0, 3, HOLE_Z))
    sk.setExpression("Constraints[0]", "Parameters.fastener_hole_diameter / 2")
    doc.recompute()
    if not sk.FullyConstrained:
        raise RuntimeError(f"{name}Sketch is not fully constrained")

    hole = body.newObject("PartDesign::Hole", name)
    hole.Profile = sk
    hole.Diameter = 4.8
    hole.setExpression("Diameter", "Parameters.fastener_hole_diameter")
    hole.DepthType = "ThroughAll"
    doc.recompute()
    assert_valid_tip(name)

doc.recompute()

# Show only the finished solid. PartDesign::Pad/Pocket/Hole features correctly
# hide the feature they supersede, but each feature's *sketch* stays visible
# forever by default -- with dozens of sketches (base, trough sections, boss,
# rib, and hole profiles) that leaves the GUI showing a tangle of overlapping
# wireframes instead of the finished part. Visibility is an App-level property,
# readable/settable headlessly (no FreeCADGui import needed).
for obj in doc.Objects:
    if hasattr(obj, "Visibility"):
        obj.Visibility = False
body.Tip.Visibility = True
body.Visibility = True

# Save parametric model (editable in FreeCAD GUI)
doc.saveAs("cad-scripts/can-dispenser-ramp/can-dispenser-ramp-parametric.FCStd")
print("Saved: cad-scripts/can-dispenser-ramp/can-dispenser-ramp-parametric.FCStd")
