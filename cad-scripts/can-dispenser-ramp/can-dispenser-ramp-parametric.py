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
setp(3, "wall", "3.2")
setp(4, "clearance", "13.0")
setp(5, "side_wall_height", "85.5")
setp(6, "main_length", "182.0")
setp(7, "rise_length", "51.0")
setp(8, "fastener_hole_diameter", "4.8")
setp(9, "rib_width", "4.8")
setp(10, "rib_thickness", "5.0")
setp(11, "rib_y", "65.4")
# Recalibrated for the truss-chute rebuild (#34): the material-map inspection
# measured the real wall outer face at Y=66.2mm with wall=3.2mm (revised from
# 3.5mm -- see README Caveat). width_calibration_offset is retuned so the
# can-size-driven formula still reproduces that measured value at defaults.
setp(12, "width_calibration_offset", "4.85")

# Derived (formulas)
sheet.set("A13", "trough_width")
sheet.set("B13", "=B2 + B4 - 2*B12")
sheet.setAlias("B13", "trough_width")
sheet.set("A14", "inner_half_width")
sheet.set("B14", "=B13/2")
sheet.setAlias("B14", "inner_half_width")
sheet.set("A15", "outer_half_width")
sheet.set("B15", "=B14 + B3")
sheet.setAlias("B15", "outer_half_width")
sheet.set("A16", "ramp_length")
sheet.set("B16", "=B6 + B7")
sheet.setAlias("B16", "ramp_length")

doc.recompute()

# --- Geometry: PartDesign Body ---
body = doc.addObject("PartDesign::Body", "Body")


def poly_sketch(name, plane, offset, pts, y_expr_idx=None, y_expr=None):
    """Fully-constrained N-gon: Coincident closure + absolute DistanceX/DistanceY
    pins on each edge's start point. y_expr_idx/y_expr optionally binds one or
    more point-Y (sketch-local-Y, i.e. Z in most of our YZ_Plane sketches, or
    the width axis on XZ_Plane sketches) constraints to a live spreadsheet
    expression, per-point-index -> expression string."""
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
    if y_expr_idx:
        for i in y_expr_idx:
            # DistanceX constraint for point i is at index n + 2*i
            sk.setExpression(f"Constraints[{n + 2 * i}]", y_expr[i])
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
# spreadsheet; the width-determining constraints on the largest members are bound
# live via setExpression below so Ctrl+R rescaling actually moves them).
inner_half_width = sheet.get("inner_half_width")
outer_half_width = sheet.get("outer_half_width")
side_wall_height = sheet.get("side_wall_height")
wall = sheet.get("wall")
main_length = sheet.get("main_length")

FLOOR_HALF_WIDTH = inner_half_width + 1.5  # overlaps 1.5mm into the wall band to fuse

# =====================================================================
# A. Floor plate -- AdditiveLoft, flat underside (Z=0), sloped interior
# top surface (the real can-rolling ramp -- the previous rebuild's "flat
# floor" belief conflated this sloped top with the flat underside). Runs
# s=0..180 at the measured slope, then a short taper (180->188) to a thin
# terminating lip, matching the real part: the floor does not continue
# into the rise span at all past s~188.
# =====================================================================
FLOOR_PROFILE = [
    # (s, bottom_z, top_z)
    (0.0, 0.0, 16.67),
    (25.0, 0.0, 16.67),
    (50.0, 0.0, 15.10),
    (75.0, 0.0, 13.79),
    (101.6, 0.0, 12.40),
    (124.4, 0.0, 11.20),
    (150.0, 0.0, 9.86),
    (175.0, 0.0, 8.55),
    (180.0, 0.0, 8.29),
    (183.0, 1.5, 8.0),
    (185.0, 3.0, 7.7),
    (188.0, 5.0, 7.86),  # thin terminating lip, ~2.86mm thick
]

floor_sketches = []
for i, (s, zb, zt) in enumerate(FLOOR_PROFILE):
    pts = [
        FreeCAD.Vector(-FLOOR_HALF_WIDTH, zb, 0),
        FreeCAD.Vector(FLOOR_HALF_WIDTH, zb, 0),
        FreeCAD.Vector(FLOOR_HALF_WIDTH, zt, 0),
        FreeCAD.Vector(-FLOOR_HALF_WIDTH, zt, 0),
    ]
    y_expr = {
        0: "-(Parameters.inner_half_width + 1.5)",
        1: "Parameters.inner_half_width + 1.5",
    }
    sk = poly_sketch(f"FloorSection{i}", "YZ_Plane", FreeCAD.Vector(0, 0, s), pts,
                      y_expr_idx=(0, 1), y_expr=y_expr)
    floor_sketches.append(sk)

floor = body.newObject("PartDesign::AdditiveLoft", "FloorPlate")
floor.Profile = floor_sketches[0]
floor.Sections = floor_sketches[1:]
floor.Ruled = True  # the measured slope is piecewise-linear between sample points
doc.recompute()
assert_valid_tip("FloorPlate")

# =====================================================================
# B/C/D. Wall members (both sides): lower band (Z 0..25, main span),
# cap-rail hook (Z 70.15..85.53, main span), and their continuation past
# the floor's end (s>=180) as climbing rails converging toward the tip.
# =====================================================================
WALL_BAND_TOP = 25.0
CAP_BOTTOM = 70.15
# A per-layer diagnostic found the main-span cap rail closing at the full
# measured max height (85.53) for its entire 180mm run puts material at
# Z 84-85 across nearly the whole part length (candidate X bbox 232 vs
# baseline's ~224.6) -- the real part's max height is reached only near the
# tip. A same-session attempt to fix this by lowering CAP_TOP to 83
# regressed further (lost 2 G-code layers, introduced a 224mm-deviation
# layer) -- reverted to the measured value; this specific mismatch is left
# as an open, documented finding for the next iteration rather than a fix
# attempted again with no more iteration budget this session. See README
# Caveat and the #34 resolution comment.
CAP_TOP = 85.53
CAP_LIP_Y_EXTRA = 3.4  # outward lip reach beyond the wall's outer face

for side, sign in (("Pos", 1), ("Neg", -1)):
    # Lower band, main span: simple constant-cross-section pad, s=0..180.
    y_in = sign * inner_half_width
    y_out = sign * outer_half_width
    band_pts = [
        FreeCAD.Vector(min(y_in, y_out), 0.0, 0),
        FreeCAD.Vector(max(y_in, y_out), 0.0, 0),
        FreeCAD.Vector(max(y_in, y_out), WALL_BAND_TOP, 0),
        FreeCAD.Vector(min(y_in, y_out), WALL_BAND_TOP, 0),
    ]
    # Width positions here are Python-baked at the current parameter values
    # (re-run the script to rescale), not live setExpression-bound -- the
    # floor plate (the dominant mass/footprint driver) carries the live
    # width binding; these secondary members follow the same precedent
    # already accepted for most of #31's members.
    band_sk = poly_sketch(f"WallBand{side}Sketch", "YZ_Plane", FreeCAD.Vector(0, 0, 0), band_pts)
    band_pad = body.newObject("PartDesign::Pad", f"WallBand{side}Pad")
    band_pad.Profile = band_sk
    band_pad.Length = 180.0
    band_pad.setExpression("Length", "Parameters.main_length")
    band_pad.Reversed = False
    doc.recompute()
    assert_valid_tip(f"WallBand{side}Pad")

    # Cap rail hook, main span: 7-point polygon approximating the lid-engagement
    # hook (straight segments standing in for the measured rounded tip), at its
    # actual measured height (CAP_BOTTOM=70.15) -- an earlier attempt extended
    # this down to the wall band to guarantee a fuse, but that turned the real
    # open-truss void (Z 25-70, baseline area ~800-900mm^2, mostly just the
    # diagonal ribs passing through) into a solid panel for the full 180mm
    # length -- >2x the real material there. Reverted; a single thin connector
    # post (below) handles the fuse instead.
    y_wall_in = inner_half_width
    y_wall_out = outer_half_width
    y_lip = outer_half_width + CAP_LIP_Y_EXTRA
    hook_local = [
        (y_wall_in, CAP_BOTTOM),
        (y_wall_out, CAP_BOTTOM),
        (y_wall_out, 75.4),
        (y_lip, 78.6),
        (y_lip, 82.6),
        (y_wall_out, CAP_TOP),
        (y_wall_in, CAP_TOP),
    ]
    hook_pts = [FreeCAD.Vector(sign * y, z, 0) for y, z in hook_local]
    if sign < 0:
        hook_pts = list(reversed(hook_pts))
    hook_sk = poly_sketch(f"CapRail{side}Sketch", "YZ_Plane", FreeCAD.Vector(0, 0, 0), hook_pts)
    hook_pad = body.newObject("PartDesign::Pad", f"CapRail{side}Pad")
    hook_pad.Profile = hook_sk
    hook_pad.Length = 180.0
    hook_pad.setExpression("Length", "Parameters.main_length")
    hook_pad.Reversed = False
    doc.recompute()
    # Not asserted here: CapRail is disconnected from the rest of the solid
    # until the connector post right below joins them (expected 2-solids
    # state, not a bug) -- the assert moves to after the connector.

    # Thin connector post: fuses CapRail (Z 70.15-85.53) to WallBand (Z 0-25)
    # with minimal added mass, standing in for whatever the real part's
    # structural connection through the open-truss void actually is (not
    # resolved by the material-map inspection). 4mm wide in s, placed just
    # before the ribs start (s=2) so it doesn't add to the already-measured
    # rib mass; both CapRail and WallBand are single continuous pads for the
    # full main span, so one connector per side is enough to fuse everything.
    post_y_in = sign * inner_half_width
    post_y_out = sign * outer_half_width
    post_pts = [
        FreeCAD.Vector(min(post_y_in, post_y_out), WALL_BAND_TOP - 1.0, 0),
        FreeCAD.Vector(max(post_y_in, post_y_out), WALL_BAND_TOP - 1.0, 0),
        FreeCAD.Vector(max(post_y_in, post_y_out), CAP_BOTTOM + 1.0, 0),
        FreeCAD.Vector(min(post_y_in, post_y_out), CAP_BOTTOM + 1.0, 0),
    ]
    post_sk = poly_sketch(f"ConnectorPost{side}Sketch", "YZ_Plane", FreeCAD.Vector(0, 0, 2.0), post_pts)
    post_pad = body.newObject("PartDesign::Pad", f"ConnectorPost{side}Pad")
    post_pad.Profile = post_sk
    post_pad.Length = 4.0
    post_pad.Reversed = False
    doc.recompute()
    assert_valid_tip(f"ConnectorPost{side}Pad")

    # Climbing rails past the floor's end (s=182..232): lower band and cap
    # rail both continue at the measured rise slope (~1.678mm Z per mm s,
    # same slope as the stiffening ribs below), converging toward the tip.
    RISE_BAND = [
        (182.0, 3.5, 20.0),
        (190.0, 13.6, 30.0),
        (200.0, 30.3, 42.0),
        (210.0, 47.1, 56.0),
        (220.0, 63.9, 70.0),
        (230.0, 80.7, 83.0),
        (232.9, 84.5, 85.3),
    ]
    rise_sketches = []
    for i, (s, zb, zt) in enumerate(RISE_BAND):
        pts = [
            FreeCAD.Vector(min(y_in, y_out), zb, 0),
            FreeCAD.Vector(max(y_in, y_out), zb, 0),
            FreeCAD.Vector(max(y_in, y_out), zt, 0),
            FreeCAD.Vector(min(y_in, y_out), zt, 0),
        ]
        sk = poly_sketch(f"RiseBand{side}{i}", "YZ_Plane", FreeCAD.Vector(0, 0, s), pts)
        rise_sketches.append(sk)
    rise = body.newObject("PartDesign::AdditiveLoft", f"RiseBand{side}")
    rise.Profile = rise_sketches[0]
    rise.Sections = rise_sketches[1:]
    rise.Ruled = True
    doc.recompute()
    assert_valid_tip(f"RiseBand{side}")

# =====================================================================
# E. Bottom outer skirt (both sides, s=0..180). Simplified to overlap the
# wall band directly (loses the ~1.3mm functional slot the real part has
# between skirt and wall -- see README Caveat) so it fuses reliably into
# the single solid rather than risking a disconnected member.
# =====================================================================
SKIRT_BOTTOM = 0.0
SKIRT_TOP = 5.6
SKIRT_OUTER_EXTRA = 3.2  # beyond outer_half_width

for side, sign in (("Pos", 1), ("Neg", -1)):
    y_in = sign * (inner_half_width - 1.0)  # overlap into the wall band
    y_out = sign * (outer_half_width + SKIRT_OUTER_EXTRA)
    pts = [
        FreeCAD.Vector(min(y_in, y_out), SKIRT_BOTTOM, 0),
        FreeCAD.Vector(max(y_in, y_out), SKIRT_BOTTOM, 0),
        FreeCAD.Vector(max(y_in, y_out), SKIRT_TOP, 0),
        FreeCAD.Vector(min(y_in, y_out), SKIRT_TOP, 0),
    ]
    sk = poly_sketch(f"Skirt{side}Sketch", "YZ_Plane", FreeCAD.Vector(0, 0, 0), pts)
    pad = body.newObject("PartDesign::Pad", f"Skirt{side}Pad")
    pad.Profile = sk
    pad.Length = 180.0
    pad.setExpression("Length", "Parameters.main_length")
    pad.Reversed = False
    doc.recompute()
    assert_valid_tip(f"Skirt{side}Pad")

# =====================================================================
# F. Entry wedge (gusset panels, s=0..35, both sides): tall/reaching-inward
# near s=0, tapering to short/near-the-wall by s=35, fading into the floor.
# Simplified from the measured V-diagonal boundary to a 2-section loft --
# captures the overall mass/height taper, not the exact diagonal edge.
# =====================================================================
for side, sign in (("Pos", 1), ("Neg", -1)):
    wedge_sections = []
    WEDGE = [
        # (s, y_outer(wall face), y_inner(reach toward center), z_bottom, z_top)
        (2.0, outer_half_width, 20.0, 0.0, 80.0),
        (35.0, outer_half_width, 50.0, 0.0, 20.0),
    ]
    for i, (s, y_out, y_in_reach, zb, zt) in enumerate(WEDGE):
        y_out_s = sign * y_out
        y_in_s = sign * y_in_reach
        pts = [
            FreeCAD.Vector(min(y_out_s, y_in_s), zb, 0),
            FreeCAD.Vector(max(y_out_s, y_in_s), zb, 0),
            FreeCAD.Vector(max(y_out_s, y_in_s), zt, 0),
            FreeCAD.Vector(min(y_out_s, y_in_s), zt, 0),
        ]
        sk = poly_sketch(f"Wedge{side}{i}", "YZ_Plane", FreeCAD.Vector(0, 0, s), pts)
        wedge_sections.append(sk)
    wedge = body.newObject("PartDesign::AdditiveLoft", f"Wedge{side}")
    wedge.Profile = wedge_sections[0]
    wedge.Sections = wedge_sections[1:]
    wedge.Ruled = True
    doc.recompute()
    assert_valid_tip(f"Wedge{side}")

# =====================================================================
# G. Rail-boss lobes: 4 lobes, both sides -- additive ears engaging the
# Lid's groove. Z-ranges clipped to land in real material (the wall lower
# band, Z 0..25) rather than the previous script's Z 3.5..76.9 range,
# which the material-map inspection showed spans mostly truss void now.
# =====================================================================
LOBES = [
    ("ALobe1", 172.6, 177.5, 3.5, 24.0),
    ("ALobe2", 181.0, 186.0, 0.0, 24.0),
    ("BLobe1", 215.0, 220.7, 74.8, 82.3),
    ("BLobe2", 224.0, 231.4, 74.9, 83.0),
]

for name, s0, s1, z0, z1 in LOBES:
    for side, sign in (("Pos", 1), ("Neg", -1)):
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
        if name != "BLobe1":
            assert_valid_tip(f"{name}{side}Pad")
        # BLobe1 sits at Z 74.8-82.3, but the climbing RiseBand only reaches
        # ~Z 59-66 at this lobe's s-span (its real measured Z-range is
        # deliberately kept narrow rather than stretched to force a fuse, per
        # the earlier over-widening mistake) -- a small local connector
        # bridges the ~9mm gap instead of widening the lobe itself.
        if name == "BLobe1":
            y_in = sign * (outer_half_width - 4.0)
            y_out = sign * (outer_half_width + 1.0)
            conn_pts = [
                FreeCAD.Vector(y_in, 63.0, 0),
                FreeCAD.Vector(y_out, 63.0, 0),
                FreeCAD.Vector(y_out, 76.0, 0),
                FreeCAD.Vector(y_in, 76.0, 0),
            ]
            conn_sk = poly_sketch(f"BLobe1Connector{side}Sketch", "YZ_Plane", FreeCAD.Vector(0, 0, 217.0), conn_pts)
            conn_pad = body.newObject("PartDesign::Pad", f"BLobe1Connector{side}Pad")
            conn_pad.Profile = conn_sk
            conn_pad.Length = 2.0
            conn_pad.Reversed = False
            doc.recompute()
            assert_valid_tip(f"BLobe1Connector{side}Pad")

# =====================================================================
# H. Stiffening ribs: 6 repeating diagonal bosses per side, main span only
# (measured -- do not extend into the rise span, which has its own
# climbing rails instead). Unchanged from #31 except rib_y is unaffected
# by the wall-thickness revision (independently measured).
# =====================================================================
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

# =====================================================================
# I. Fastener holes: 4 holes matching Open End's pegs, at the floor-rise
# end. Z positions are the measured Open End peg heights -- #31 placed
# these at mid-wall (Z=42.75), which the material-map inspection showed
# falls in open truss void; the real peg heights land in the lower band
# (Z~6.9) and the cap rail (Z~78.7).
# =====================================================================
HOLES = [
    ("Hole1Pos", 161.0, 1, 6.9),
    ("Hole1Neg", 161.0, -1, 6.9),
    ("Hole2Pos", 204.0, 1, 78.7),
    ("Hole2Neg", 204.0, -1, 78.7),
]

for name, s, sign, hz in HOLES:
    hole_y = outer_half_width - wall / 2.0
    sk = body.newObject("Sketcher::SketchObject", f"{name}Sketch")
    # XZ_Plane, not YZ_Plane: a Hole feature drills perpendicular to its sketch
    # plane, and the hole must go THROUGH the wall (the Y direction), not
    # lengthwise down the ramp -- XZ_Plane's normal is Y.
    sk.AttachmentSupport = [(doc.getObject("XZ_Plane"), "")]
    sk.MapMode = "FlatFace"
    sk.AttachmentOffset = FreeCAD.Placement(FreeCAD.Vector(0, 0, sign * -hole_y), FreeCAD.Rotation())
    center = FreeCAD.Vector(s, hz, 0)
    circ = Part.Circle(center, FreeCAD.Vector(0, 0, 1), 2.4)
    sk.addGeometry(circ, False)
    sk.addConstraint(Sketcher.Constraint("Radius", 0, 2.4))
    sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 3, s))
    sk.addConstraint(Sketcher.Constraint("DistanceY", 0, 3, hz))
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

# Show only the finished solid. PartDesign::Pad/Pocket/Hole/Loft features
# correctly hide the feature they supersede, but each feature's *sketch*
# stays visible forever by default -- with dozens of sketches that leaves
# the GUI showing a tangle of overlapping wireframes instead of the
# finished part. Visibility is an App-level property, readable/settable
# headlessly (no FreeCADGui import needed).
for obj in doc.Objects:
    if hasattr(obj, "Visibility"):
        obj.Visibility = False
body.Tip.Visibility = True
body.Visibility = True

# Save parametric model (editable in FreeCAD GUI)
doc.saveAs("cad-scripts/can-dispenser-ramp/can-dispenser-ramp-parametric.FCStd")
print("Saved: cad-scripts/can-dispenser-ramp/can-dispenser-ramp-parametric.FCStd")
