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


def assert_valid_tip(label, require_single_solid=True):
    """require_single_solid=False for a window where the cap rail is a
    deliberately still-disconnected floating member -- it only rejoins the
    main mass via the per-tooth connectors added after the rib loop, matching
    the real part's genuinely intermittent rib-to-cap-rail contact. isValid()
    is still checked either way."""
    n_solids = len(body.Tip.Shape.Solids)
    if not body.Tip.Shape.isValid() or (require_single_solid and n_solids != 1):
        raise RuntimeError(
            f"Invalid or non-solid geometry after {label} ({body.Tip.Name}): "
            f"isValid={body.Tip.Shape.isValid()}, solids={n_solids}"
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
CAP_BOTTOM = 70.15
# A prior iteration wrongly diagnosed the per-layer mismatch here as a height
# problem (assumed CAP_TOP needed tapering along s) -- a direct re-measurement
# disproved that: the cap rail really is constant-height Z[70.15,85.53] from
# s~10 to s~185. The real defect was CONNECTIVITY (see the per-tooth connector
# loop after the ribs, below), not height -- CAP_TOP stays at its measured value.
CAP_TOP = 85.53
CAP_LIP_Y_EXTRA = 3.4  # outward lip reach beyond the wall's outer face

# Wall band top edge -- NOT flat at Z=25 (the original assumption, documented
# as "sub-tolerance" without dense verification). A direct mesh re-inspection
# this session, isolating the floor+wallband combined wire from the
# separately-floating rib/cap-rail wires at each cross-section (5 distinct
# wires appear from s~38 onward: 2x cap rail, 1x floor+wallband, 2x rib --
# the floor+wallband wire is the one with the widest Y-span, >100mm, spanning
# both sides), found its top edge SMOOTHLY DECLINES from ~33mm near s=34 down
# to ~19mm at s=182 -- not flat, and not a sharp zigzag either (the earlier
# "zigzagging" read was from coarser, less-attributed sampling). This flat-top
# approximation was the actual trigger for spurious "Top solid infill"/
# "Bridge infill" toolpath at Z~25 that regressed two different entry-wedge
# rebuild attempts (see Caveats) -- the real part doesn't present nearly as
# large a contiguous flat top surface there.
WALL_BAND_PROFILE = [
    # (s, top_z) -- s<34 held constant at the s=34 measured value since that
    # span is dominated by the entry wedge/cap-rail-taper merge (a single
    # combined wire in the mesh there, not a separable wall-band edge).
    (0.0, 33.0),
    (34.0, 33.0),
    (40.0, 28.55),
    (60.0, 25.5),
    (90.0, 24.0),
    (120.0, 22.5),
    (150.0, 20.9),
    (182.0, 19.2),
]

for side, sign in (("Pos", 1), ("Neg", -1)):
    band_sketches = []
    for i, (s, zt) in enumerate(WALL_BAND_PROFILE):
        # Outer face measured at Y~67.8, not outer_half_width(66.2) -- a
        # consistent 1.6mm/side gap found via direct mesh re-sampling (5
        # locations, Z 6-20 band, all agreeing to within 0.05mm) after a
        # G-code layer diff flagged a systematic ~3.2mm total Y-narrowing
        # across most of the part's low-to-mid-height layers. 67.8 exactly
        # matches the rib's own outer reach (rib_y + rib_width/2) -- the wall
        # band is genuinely thicker at its outer face than the rest of the
        # wall, flush with where the ribs sit, not thinner than them.
        y_in = sign * inner_half_width
        y_out = sign * (outer_half_width + 1.6)
        pts = [
            FreeCAD.Vector(min(y_in, y_out), 0.0, 0),
            FreeCAD.Vector(max(y_in, y_out), 0.0, 0),
            FreeCAD.Vector(max(y_in, y_out), zt, 0),
            FreeCAD.Vector(min(y_in, y_out), zt, 0),
        ]
        sk = poly_sketch(f"WallBand{side}{i}", "YZ_Plane", FreeCAD.Vector(0, 0, s), pts)
        band_sketches.append(sk)
    band_pad = body.newObject("PartDesign::AdditiveLoft", f"WallBand{side}Pad")
    band_pad.Profile = band_sketches[0]
    band_pad.Sections = band_sketches[1:]
    band_pad.Ruled = True  # the measured decline is piecewise-linear between sample points
    doc.recompute()
    # require_single_solid=False from here on: once the Pos-side cap rail is
    # padded later in this same loop it's a floating member until the
    # per-tooth connectors (after the rib loop) rejoin it -- that floating
    # state is visible to every assert_valid_tip call from this point on,
    # including WallBandNegPad on the loop's second iteration.
    assert_valid_tip(f"WallBand{side}Pad", require_single_solid=False)

    # Cap rail hook, main span: 7-point polygon approximating the lid-engagement
    # hook (straight segments standing in for the measured rounded tip), at its
    # actual measured height (CAP_BOTTOM=70.15) -- a second per-layer diagnostic
    # (this session) found this height/span was ALREADY correct; the real
    # defect was connectivity. Two earlier attempts both got that wrong in
    # opposite directions: extending the hook down to the wall band made the
    # real open-truss void (mostly just the diagonal ribs passing through) a
    # solid panel for the full 180mm length (>2x real material there); a single
    # full-length thin connector post did the same thing at smaller scale. Real
    # mesh inspection found the cap rail is a genuinely disconnected floating
    # member almost everywhere -- it only touches the ribs in narrow ~2-3mm
    # windows, once per rib tooth. Per-tooth connectors (below, after the rib
    # loop) replace both prior attempts.
    y_wall_in = inner_half_width
    y_wall_out = outer_half_width
    y_lip = outer_half_width + CAP_LIP_Y_EXTRA
    # A direct per-layer G-code diff (this session) found the main span's cap
    # rail is uniformly ~4.6mm too wide across nearly the entire part length
    # at Z=83-85.5mm -- NOT an end-taper problem, a shape problem in the main
    # hook profile itself. A precise mesh re-inspection (3 independent s
    # locations, 60/100/140, identical result) found the top of the hook is
    # not a smooth diagonal narrowing from the lip down to the wall face --
    # there's a genuine SHARP STEP at Z=CAP_STEP=83.0 (both edges jump
    # simultaneously: outer Y 68.8->67.3, inner Y 63.0->65.1), above which a
    # narrow 2.2mm RIDGE (Y=CAP_RIDGE_OUT..CAP_RIDGE_IN) runs flat to CAP_TOP
    # -- not the full wall_in..wall_out band the previous shape assumed.
    CAP_STEP_Z = 83.0
    CAP_RIDGE_OUT = 67.3
    CAP_RIDGE_IN = 65.1
    hook_local = [
        (y_wall_in, CAP_BOTTOM),
        (y_wall_out, CAP_BOTTOM),
        (y_wall_out, 75.4),
        (y_lip, 78.6),
        (y_lip, CAP_STEP_Z),
        (CAP_RIDGE_OUT, CAP_STEP_Z),
        (CAP_RIDGE_OUT, CAP_TOP),
        (CAP_RIDGE_IN, CAP_TOP),
        (CAP_RIDGE_IN, CAP_STEP_Z),
        (y_wall_in, CAP_STEP_Z),
    ]
    hook_pts = [FreeCAD.Vector(sign * y, z, 0) for y, z in hook_local]
    if sign < 0:
        hook_pts = list(reversed(hook_pts))
    # Attempted fix (this session): starting the cap rail later than s=0, on
    # the theory the entry wedge zone shouldn't also carry cap-rail material.
    # Reverted -- direct per-layer comparison showed the full-length cap rail
    # was already CORRECT for nearly the entire height range (baseline and
    # candidate agreed from Z=3 up to Z~82.6); shortening it broke that
    # agreement (new ~38mm deviation, Z=79.6-84.6) while leaving the actual
    # narrow top-band mismatch (Z~82.8-85.2, ~12 layers, likely under the 5%
    # fail threshold on its own) completely unchanged. Root cause of that
    # narrow band is still open -- see README Caveat/#34 comment.
    # Entry-end taper (s=0..ENTRY_TAPER_FULL_START): a direct mesh re-inspection
    # (this session, following the user's GUI report that "the top of the part
    # doesn't extend all the length that it's supposed to") found the far end
    # wasn't the only place the cap rail's cross-section changes with s -- the
    # entry end does too, and it's NOT a simple mirror of CapRailTip. Measured
    # Zmax at the entry: flat at 83.03mm from s=0 to s=6 (the hook's lip-tip
    # height only, the final top-closing segment up to CAP_TOP missing), then
    # ramps linearly to the full CAP_TOP=85.53 by s=9, flat from there on. The
    # main hook_pad below only starts at ENTRY_TAPER_FULL_START (s=9), where
    # the flat full-hook cross-section is already correct.
    ENTRY_TAPER_FLAT_END = 6.0
    ENTRY_TAPER_FULL_START = 9.0
    ENTRY_CAP_SHORT_TOP = 83.03
    # Same 10-point topology/order as hook_local (a mismatched point count
    # between loft sections is exactly what produced a non-manifold candidate
    # on an earlier attempt here -- OCC's loft can't find a consistent vertex
    # correspondence). The entry region has no ridge at all (measured Zmax
    # plateaus at 83.03 flat, never reaching CAP_TOP) -- points 5-8 collapse
    # toward the step height with tiny (0.01mm) distinct Z offsets so no two
    # points are exactly coincident (a zero-length edge risked its own
    # degenerate-sketch problems elsewhere in this script).
    short_hook_local = [
        (y_wall_in, CAP_BOTTOM),
        (y_wall_out, CAP_BOTTOM),
        (y_wall_out, 75.4),
        (y_lip, 78.6),
        (y_lip, ENTRY_CAP_SHORT_TOP),
        (CAP_RIDGE_OUT, ENTRY_CAP_SHORT_TOP),
        (CAP_RIDGE_OUT, ENTRY_CAP_SHORT_TOP + 0.01),
        (CAP_RIDGE_IN, ENTRY_CAP_SHORT_TOP + 0.01),
        (CAP_RIDGE_IN, ENTRY_CAP_SHORT_TOP),
        (y_wall_in, ENTRY_CAP_SHORT_TOP),
    ]
    short_hook_pts = [FreeCAD.Vector(sign * y, z, 0) for y, z in short_hook_local]
    if sign < 0:
        short_hook_pts = list(reversed(short_hook_pts))
    entry_s0_sk = poly_sketch(f"CapRailEntryStart{side}Sketch", "YZ_Plane",
                               FreeCAD.Vector(0, 0, 0.0), short_hook_pts)
    entry_flat_sk = poly_sketch(f"CapRailEntryFlat{side}Sketch", "YZ_Plane",
                                 FreeCAD.Vector(0, 0, ENTRY_TAPER_FLAT_END), short_hook_pts)
    entry_full_sk = poly_sketch(f"CapRailEntryFull{side}Sketch", "YZ_Plane",
                                 FreeCAD.Vector(0, 0, ENTRY_TAPER_FULL_START), hook_pts)
    entry_taper = body.newObject("PartDesign::AdditiveLoft", f"CapRailEntryTaper{side}")
    entry_taper.Profile = entry_s0_sk
    entry_taper.Sections = [entry_flat_sk, entry_full_sk]
    entry_taper.Ruled = True  # plateau then linear ramp -- matches the measured shape
    doc.recompute()

    # Start 0.5mm before the taper's own endpoint -- genuine volume overlap,
    # not a flush touching face, which OCC has left as two separate solids
    # elsewhere in this script (see WallBand/CapRail's own history above).
    HOOK_PAD_START = ENTRY_TAPER_FULL_START - 0.5
    hook_sk = poly_sketch(f"CapRail{side}Sketch", "YZ_Plane",
                           FreeCAD.Vector(0, 0, HOOK_PAD_START), hook_pts)
    hook_pad = body.newObject("PartDesign::Pad", f"CapRail{side}Pad")
    hook_pad.Profile = hook_sk
    # Length: a direct mesh re-inspection (this session, ticket #34) found
    # the cap rail present continuously past s~185 (every prior measurement
    # pass wrongly assumed it stopped there) -- this directly matches the
    # user's own visual finding ("the top of the part doesn't extend all the
    # length that it's supposed to"). But a first attempt to extend it flat
    # to the full ramp_length overshot: a per-layer G-code diff found the
    # real cap rail's LENGTH-vs-Z relationship isn't uniform near the tip --
    # at Z~70 (near CAP_BOTTOM) material recedes to s~223.7, while at Z~85
    # (near CAP_TOP) it reaches the true tip s~232.8. A tapering loft section
    # below (CapRailTip) covers s=CAP_TAPER_START..ramp_length; this pad only
    # goes to CAP_TAPER_START, where the flat cross-section is still correct.
    CAP_TAPER_START = 223.7
    hook_pad.Length = CAP_TAPER_START - HOOK_PAD_START
    hook_pad.Reversed = False
    doc.recompute()
    # Not asserted here: CapRail is disconnected from the rest of the solid
    # until the per-tooth connectors (added after the rib loop below) join
    # them -- expected multi-solid state at this point, not a bug.

    # Tip taper (s=CAP_TAPER_START..ramp_length): the cap rail's cross-section
    # shrinks from the full hook height (bottom=CAP_BOTTOM) down to a thin
    # flat sliver at the true tip -- measured slope ~1.65-1.68mm Z per mm s,
    # matching the rest of the part's rise ratio. There's too little material
    # left there for the lip/rounded-tip detail to matter, but the tip profile
    # must still share hook_pts' 7-point topology -- lofting a 7-point profile
    # against an unrelated 4-point rectangle (the original approach here) is
    # exactly the bug class fixed in the entry-taper above: OCC can't find a
    # consistent vertex correspondence and produces a self-intersecting,
    # non-manifold surface (only caught once the manifold pre-check existed
    # to catch it -- FreeCAD's own isValid() does not). Fix: proportionally
    # compress hook_local's own height range down to [tip_bottom_end, CAP_TOP]
    # instead, preserving all 7 points and their correspondence -- the hook
    # shape shrinks toward the tip rather than being replaced by a rectangle.
    # This session tried both a finer-sectioned loft and a combined Y+Z
    # compression here (per the "2D-varying boundary" diagnosis) -- both
    # hung the FreeCAD build (OCC struggling with the resulting topology,
    # not a script bug) and were reverted rather than risk shipping a build
    # that doesn't complete at all. Reverted to the known-working 2-section,
    # Z-only compression below. This member's 0-for-3 track record on
    # rebuild attempts is now 0-for-5; the real fix likely needs a
    # different construction primitive entirely (e.g. a genuine Sweep/Pipe
    # along a spine, not a Loft between hand-built polygon sections) rather
    # than another loft-section variant.
    # AdditivePipe-family fix (this session), replacing the compressed-Z 2-section
    # loft above (0-for-5 track record; either a no-op or a build-hanging OCC
    # topology). Direct dense Y-Z cross-section probing near the tip (s=223-233,
    # Z=70-85.4, 1-4mm intervals) found the real shape isn't a shrinking hook --
    # it's the SAME hook cross-section (unchanged Y values throughout) whose
    # material simply RECEDES in length at a rate that depends on Z: low-Z
    # material recedes first (~s=223.7 at Z=70.15, matching CAP_TAPER_START
    # almost exactly), high-Z material reaches nearly the true tip (~s=232.9 at
    # Z=85.4). The relationship is close to linear (slope ~0.6mm-s per mm-Z) and
    # was measured directly, not assumed. This is naturally a set of loft
    # sections at DIFFERENT s positions, each using hook_local's own 10-point
    # topology with each point's Z clipped up to whatever Z is still "present"
    # at that s (points that have already receded collapse to the threshold
    # height instead of being physically removed, keeping topology/point-count
    # identical across every section -- the same fix that solved the earlier
    # entry-taper non-manifold bug).
    TIP_RECEDE = [  # (Z, s) measured via Mesh.crossSections, Pos side, s = X - meshXmin
        (CAP_BOTTOM, CAP_TAPER_START),
        (71.0, 224.25), (72.0, 224.84), (73.0, 225.44), (74.0, 226.03),
        (76.0, 227.23), (77.0, 227.82), (78.0, 228.42), (79.0, 229.02),
        (80.0, 229.61), (81.0, 230.21), (82.0, 230.80), (83.0, 231.40),
        (84.0, 232.00), (85.0, 232.59),
        (CAP_TOP, 232.9),
    ]

    def z_min_present_at(s):
        pts = TIP_RECEDE
        if s <= pts[0][1]:
            return pts[0][0]
        if s >= pts[-1][1]:
            return pts[-1][0]
        for (z0, s0), (z1, s1) in zip(pts, pts[1:]):
            if s0 <= s <= s1:
                t = (s - s0) / (s1 - s0)
                return z0 + t * (z1 - z0)
        raise RuntimeError(f"z_min_present_at({s}): unreachable")

    TIP_SECTION_S = [CAP_TAPER_START, 226.03, 228.42, 230.21, 231.40, 232.00, 232.59, 232.9]
    tip_sketches = []
    for i, s in enumerate(TIP_SECTION_S):
        z_thresh = z_min_present_at(s)
        # Add a tiny monotonic-in-point-order epsilon so clipping several
        # points to the same threshold near the tip never leaves two points
        # exactly coincident (a zero-length edge OCC rejects outright) --
        # same trick as the entry-taper fix above.
        clipped_local = [(y, max(z, z_thresh + 0.001 * j)) for j, (y, z) in enumerate(hook_local)]
        clipped_pts = [FreeCAD.Vector(sign * y, z, 0) for y, z in clipped_local]
        if sign < 0:
            clipped_pts = list(reversed(clipped_pts))
        sk = poly_sketch(f"CapRailTip{side}{i}Sketch", "YZ_Plane", FreeCAD.Vector(0, 0, s), clipped_pts)
        tip_sketches.append(sk)
    tip = body.newObject("PartDesign::AdditiveLoft", f"CapRailTip{side}")
    tip.Profile = tip_sketches[0]
    tip.Sections = tip_sketches[1:]
    tip.Ruled = True  # the measured recede curve is close to linear between sample points
    doc.recompute()

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
    assert_valid_tip(f"RiseBand{side}", require_single_solid=False)

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
    assert_valid_tip(f"Skirt{side}Pad", require_single_solid=False)

# =====================================================================
# F. Entry scoop (s=0..~40, both sides): NOT a solid gusset-panel wedge --
# a user-provided side-view screenshot of the real part showed a large,
# continuous, rounded/parabolic OPENING here (not solid panels with a small
# V-cut), and a dense mesh re-inspection this session confirmed it precisely.
#
# The real shape is a rounded scoop: at each Z, material exists for
# Y > boundary_y(Z) (void is INBOARD, toward center -- not outboard toward
# the wall as the old wedge assumed), and that material's reach in s shrinks
# smoothly as Z increases (S_MAX(Z) below) -- large reach (~39mm) near the
# floor, tapering to ~0 near the cap rail. Both curves were measured via a
# validated ray-casting probe against the real mesh (own from-scratch tool --
# Mesh.crossSections()'s wire grouping proved unreliable, see repo history)
# and are s-independent within a section's active range -- i.e. this is a
# fixed Y(Z) profile whose reach in s is itself a function of Z, not a
# profile that changes shape as it's swept along s. Built as a single
# AdditiveLoft stacked along Z (not along s, unlike every other member in
# this script) with a 4-point rectangular section per measured Z: Y from
# boundary_y(Z) to inner_half_width+overlap (fusing into the wall band),
# s from 0 to S_MAX(Z)+overlap. Consistent 4-point topology across all
# sections avoids the mismatched-point-count non-manifold AdditiveLoft bug
# hit earlier in this ticket's history.
# =====================================================================
SCOOP_OVERLAP_Y = 2.0   # into the wall band, for a genuine fuse
SCOOP_OVERLAP_S = 0.5   # past S_MAX, same reason
# (Z, boundary_y, S_MAX) -- boundary_y and S_MAX measured directly (dense
# ray-casting probe, s=0.3-40 / Z=17-83); Z=55/60 boundary_y linearly
# interpolated toward inner_half_width (measured only up to Z=50 directly),
# Z>=65 clamped to inner_half_width since the scoop has visibly merged into
# the wall band there (probe at s=1.0 found the full cross-section already
# solid from Y=0 up for Z>=40, well within this shrinking-reach range).
SCOOP_DATA = [
    (16.0, 3.86, 39.07),  # Z lowered from measured 17.0: floor top is 16.67,
                          # a bare 17.0 start left a ~0.33mm air gap that
                          # caused a huge (~189%) per-layer extrusion spike
                          # right at that seam -- same boundary_y/s_max as
                          # measured, just extended down for overlap.
    # Z=18..50 replaced (this session): the boundary here is genuinely a
    # circular arc, not the straight-line/coarse fit the old points implied.
    # Direct ray-cast probing (own facet-intersection tool, not
    # Mesh.crossSections()) at s=1/10/20 found IDENTICAL boundary_y(Z)
    # profiles at all three -- the arc's shape doesn't change with s across
    # that whole span, only how far it's carved in s does (S_MAX below,
    # unchanged from the prior fit). Circle fit on (Y, Z) points at s=1,
    # Y<=15 (residuals <0.01mm): center Z=40.2, R=23.5 -- boundary_y(Z) =
    # sqrt(R^2 - (Z-cz)^2). This is what the user's side/rear-view screenshots
    # were showing as a smooth rounded curve; the old points (12.05, 18.63,
    # 24.85, 31.06, 37.28...) grew roughly linearly without bound, well past
    # the arc's actual max reach of Y=R=23.5 at its Z=40.2 peak -- correct at
    # Z=20 (12.05 vs 12.01) but increasingly wrong above that. S_MAX values
    # unchanged (linearly interpolated from the same prior fit at these finer
    # Z steps) -- only the curve's shape changed, not its length-wise reach.
    (18.0, 7.71, 35.91),
    (20.0, 12.01, 32.75),
    (22.0, 14.87, 30.23),
    (24.0, 17.02, 27.71),
    (26.0, 18.72, 25.64),
    (28.0, 20.09, 24.03),
    (30.0, 21.17, 22.42),
    (32.0, 22.02, 21.29),
    (34.0, 22.67, 20.16),
    (36.0, 23.12, 19.06),
    (38.0, 23.40, 17.99),
    (40.0, 23.50, 16.93),
    (42.0, 23.43, 15.86),
    (44.0, 23.19, 14.79),
    (46.0, 22.77, 13.73),
    (48.0, 22.17, 12.66),
    (50.0, 21.36, 11.60),
    (55.0, None, 9.16),   # boundary_y interpolated below toward inner_half_width
    (60.0, None, 7.16),
    (65.0, None, 5.61),
    (70.0, None, 4.45),
    (75.0, None, 3.67),
    (80.0, None, 3.27),
    # Z=83 measured s_max=0.50 -- a razor-thin rectangle there self-intersected
    # (PrusaSlicer flagged a ~38x extrusion-length spike, 101,294mm vs
    # baseline's 2,607mm, undetected by isValid()/manifold checks). Dropping
    # it entirely (loft stopping flat at Z=80) turned out worse: /cad-slice's
    # per-layer signal sums extrusion across the WHOLE cross-section at each
    # Z, not per-member, so the abrupt Z=80 cutoff (real material continues,
    # just thinning, up to ~83) corrupted layers 374/404-407 (Z=74.8-81.4) --
    # net regression from 127 to 201 failing layers even though the scoop's
    # own s<45 region measured zero failures in isolation. Fix: keep the loft
    # going to Z=83, but clip s_max to a safe minimum (1.5mm, not the
    # measured 0.50mm) so the section stays non-degenerate -- a small
    # documented simplification of the true tip shape, not a dropped feature.
    (83.0, inner_half_width, 1.5),
]

for side, sign in (("Pos", 1), ("Neg", -1)):
    scoop_sections = []
    for i, (z, boundary_y, s_max) in enumerate(SCOOP_DATA):
        if boundary_y is None:
            # Interpolate from the last measured point (50.0, 49.49) toward
            # inner_half_width by Z=65, then hold at inner_half_width.
            frac = min(1.0, (z - 50.0) / (65.0 - 50.0))
            boundary_y = 49.49 + frac * (inner_half_width - 49.49)
            boundary_y = min(boundary_y, inner_half_width)
        y_lo = sign * boundary_y
        y_hi = sign * (inner_half_width + SCOOP_OVERLAP_Y)
        s_hi = s_max + SCOOP_OVERLAP_S
        pts = [
            FreeCAD.Vector(0.0, min(y_lo, y_hi), 0),
            FreeCAD.Vector(s_hi, min(y_lo, y_hi), 0),
            FreeCAD.Vector(s_hi, max(y_lo, y_hi), 0),
            FreeCAD.Vector(0.0, max(y_lo, y_hi), 0),
        ]
        sk = poly_sketch(f"Scoop{side}{i}", "XY_Plane", FreeCAD.Vector(0, 0, z), pts)
        scoop_sections.append(sk)
    scoop = body.newObject("PartDesign::AdditiveLoft", f"Scoop{side}")
    scoop.Profile = scoop_sections[0]
    scoop.Sections = scoop_sections[1:]
    scoop.Ruled = True  # measured curves are smooth but not analytically simple; Ruled tracks samples directly
    doc.recompute()
    assert_valid_tip(f"Scoop{side}", require_single_solid=False)

# =====================================================================
# G. Rail-boss lobes: 4 lobes, both sides -- additive ears engaging the
# Lid's groove. Z-ranges clipped to land in real material (the wall lower
# band, Z 0..25) rather than the previous script's Z 3.5..76.9 range,
# which the material-map inspection showed spans mostly truss void now.
# =====================================================================
# ALobe1/2 Z-range corrected by a second mesh re-inspection: the real feature
# in this region is a small foot near the floor (Z 4.4-9.4), not a Z 0-24
# rail matching the wall-band height as previously assumed.
LOBES = [
    ("ALobe1", 172.6, 177.5, 4.4, 9.4),
    ("ALobe2", 181.0, 186.0, 4.4, 9.4),
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
            assert_valid_tip(f"{name}{side}Pad", require_single_solid=False)
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
            assert_valid_tip(f"BLobe1Connector{side}Pad", require_single_solid=False)

# =====================================================================
# H. Stiffening ribs: 6 repeating diagonal bosses per side, main span only
# (measured -- do not extend into the rise span, which has its own
# climbing rails instead). Unchanged from #31 except rib_y is unaffected
# by the wall-thickness revision (independently measured).
#
# RESTORED (was accidentally lost by a `git checkout --` revert in a prior
# session that meant to discard an unrelated hole-rotation experiment but
# reset the whole file to the last git commit instead, silently dropping
# this fix along with it -- 107 failing layers regressed back to 138): the
# wall band's top edge declines with `s` (WALL_BAND_PROFILE, section B/C/D
# above), so a single fixed RIB_Z_START=23.0 for every rib loses overlap
# for the later ribs once the band's local top drops below ~25mm -- direct
# measurement found rib 4 had only 0.49mm of overlap and rib 5 was fully
# disconnected (-0.73mm), matching the user's GUI observation. Fix: clamp
# each rib's own bottom Z down (never up -- the early ribs already have
# plenty of overlap and shouldn't move) to guarantee a minimum 2mm overlap
# into the wall band's actual local height at that specific rib's `s`.
# =====================================================================
RIB_RUN = 21.0
RIB_RISE = 35.5
RIB_PERIOD = 22.83
RIB_FIRST_START = 34.0
RIB_Z_START = 23.0
RIB_BOTTOM_OVERLAP = 2.0
RIB_COUNT = 6
rib_thickness = sheet.get("rib_thickness")
rib_y = sheet.get("rib_y")


def wall_band_top_at(s):
    """Linear interpolation of WALL_BAND_PROFILE's (s, top_z) samples."""
    pts = WALL_BAND_PROFILE
    if s <= pts[0][0]:
        return pts[0][1]
    if s >= pts[-1][0]:
        return pts[-1][1]
    for (s0, z0), (s1, z1) in zip(pts, pts[1:]):
        if s0 <= s <= s1:
            t = (s - s0) / (s1 - s0)
            return z0 + t * (z1 - z0)
    raise RuntimeError(f"wall_band_top_at({s}): unreachable")


def rib_bottom_z(s_start):
    return min(RIB_Z_START, wall_band_top_at(s_start) - RIB_BOTTOM_OVERLAP)


rib_width = sheet.get("rib_width")

theta = math.atan2(RIB_RISE, RIB_RUN)
nx, nz = -math.sin(theta), math.cos(theta)  # unit normal to the spine

rib_z_starts = []  # per-rib bottom Z, needed again by the connectors below
for k in range(RIB_COUNT):
    s_start = RIB_FIRST_START + k * RIB_PERIOD
    z_start = rib_bottom_z(s_start)
    rib_z_starts.append(z_start)
    half_t = rib_thickness / 2.0
    pts = [
        FreeCAD.Vector(s_start - nx * half_t, z_start - nz * half_t, 0),
        FreeCAD.Vector(s_start + nx * half_t, z_start + nz * half_t, 0),
        FreeCAD.Vector(s_start + RIB_RUN + nx * half_t, z_start + RIB_RISE + nz * half_t, 0),
        FreeCAD.Vector(s_start + RIB_RUN - nx * half_t, z_start + RIB_RISE - nz * half_t, 0),
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
        assert_valid_tip(f"Rib{k}{side}Pad", require_single_solid=False)

# =====================================================================
# H2. Cap-rail connectors: the cap rail (Z 70.15-85.53) has been a floating
# member since it was padded in step B/C/D -- a second mesh re-inspection
# found the real part connects it to the rest of the structure only in
# narrow ~2-3mm windows, once per rib tooth, roughly where each tooth's
# climb peaks (RIB_Z_START+RIB_RISE=58.5, the closest real material to the
# cap rail's underside at 70.15 -- an 11.65mm gap, vs. ~45mm from the wall
# band). This replaces two earlier over-fill attempts (a full-length cap-to-
# band panel, then a full-length thin post) that both turned the real open
# truss void into solid material for the whole 180mm span. One connector per
# rib tooth per side (6 teeth x 2 sides = 12) is a documented simplification
# of the real part's irregular tooth-boundary bridging (see README Caveat) --
# it reproduces the "connects only intermittently" structure without chasing
# every irregular transition exactly.
# =====================================================================
# The connector used to be an axis-aligned box (a YZ_Plane rectangle, one
# fixed s) bridging straight up from the rib's peak to the cap rail -- the
# user visually inspected the file and found this reads as an orthogonal jog
# rather than a continuation of the rib's own diagonal. Fixed: build the
# connector as a parallelogram on the SAME XZ_Plane sketch pattern as the
# ribs themselves (same nx,nz spine normal), continuing at the identical
# slope from the rib's peak edge up into the cap rail, so it reads as one
# continuous diagonal member, not a rib-then-post shape.
#
# Peak Z now varies per rib (rib_z_starts[k] + RIB_RISE) since rib_bottom_z()
# was restored above -- each connector's own rise/run to reach the cap rail
# is computed from its own rib's actual peak, not one shared constant.
for k in range(RIB_COUNT):
    s_start = RIB_FIRST_START + k * RIB_PERIOD
    s_peak = s_start + RIB_RUN  # tooth's end/peak position
    rib_peak_z = rib_z_starts[k] + RIB_RISE
    conn_dz = (CAP_BOTTOM + 1.0) - rib_peak_z  # rise needed to reach 1mm into the cap rail
    conn_ds = conn_dz / (RIB_RISE / RIB_RUN)   # run at the rib's own slope
    half_t = rib_thickness / 2.0
    pts = [
        FreeCAD.Vector(s_peak - nx * half_t, rib_peak_z - nz * half_t, 0),
        FreeCAD.Vector(s_peak + nx * half_t, rib_peak_z + nz * half_t, 0),
        FreeCAD.Vector(s_peak + conn_ds + nx * half_t, rib_peak_z + conn_dz + nz * half_t, 0),
        FreeCAD.Vector(s_peak + conn_ds - nx * half_t, rib_peak_z + conn_dz - nz * half_t, 0),
    ]
    for side, sign in (("Pos", 1), ("Neg", -1)):
        sk = poly_sketch(
            f"CapConnector{k}{side}Sketch", "XZ_Plane", FreeCAD.Vector(0, 0, sign * -rib_y), pts
        )
        pad = body.newObject("PartDesign::Pad", f"CapConnector{k}{side}Pad")
        pad.Profile = sk
        pad.Length = rib_width
        pad.setExpression("Length", "Parameters.rib_width")
        pad.SideType = "Symmetric"
        doc.recompute()

# All cap-rail connectors are in -- the whole truss should now be one solid.
assert_valid_tip("AllCapConnectors")

# =====================================================================
# I. Fastener hole: re-measured this session -- the previous s=161/204,
# Y-oriented, 4-hole construction is replaced entirely. The user confirmed
# "the pegs are near the tip, right where the cap rail converges" -- the
# old positions were never actually confirmed against the mesh (see README
# Caveats #8/#9). Direct Y-Z plane slicing (perpendicular to X) near the tip
# found a genuine small nested void distinct from every known member: a
# consistent Y[64.60,69.60] (5.0mm) x Z[76.43,81.43] (5.0mm) loop from
# s~=219 to s~=227, centered at Y~=67.1, Z~=78.9 -- a round hole drilled
# along X, sized almost exactly to fastener_hole_diameter (4.8mm). It sits
# inside the BLobe1/BLobe2 rail-boss Z-range (74.8-83), which is almost
# certainly why an earlier whole-mesh scan missed it -- that loop was
# filtered out as "already-known rail-boss lobe" without noticing a
# distinct void nested inside it. A wider scan (s=150-232, every 3mm) found
# no second hole: the only other small-loop candidates matched already-known
# members exactly (ALobe1/2's own Z 4.4-9.4 range at s~177-183, the cap-rail
# tip's own narrowing taper at s~231) -- **only ONE hole per side**, not the
# previously-assumed two-position/four-hole layout.
# =====================================================================
HOLE_S = 223.0
HOLE_Y = 67.1
HOLE_Z = 78.9

for side, sign in (("Pos", 1), ("Neg", -1)):
    name = f"Hole{side}"
    sk = body.newObject("Sketcher::SketchObject", f"{name}Sketch")
    # YZ_Plane, not XZ_Plane: a Hole feature drills perpendicular to its
    # sketch plane, and this hole goes along X (into the +X-facing material
    # near the tip), not through the side wall in Y like the old, unconfirmed
    # construction assumed.
    sk.AttachmentSupport = [(doc.getObject("YZ_Plane"), "")]
    sk.MapMode = "FlatFace"
    sk.AttachmentOffset = FreeCAD.Placement(FreeCAD.Vector(0, 0, HOLE_S), FreeCAD.Rotation())
    center = FreeCAD.Vector(sign * HOLE_Y, HOLE_Z, 0)
    circ = Part.Circle(center, FreeCAD.Vector(0, 0, 1), 2.4)
    sk.addGeometry(circ, False)
    sk.addConstraint(Sketcher.Constraint("Radius", 0, 2.4))
    sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 3, sign * HOLE_Y))
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
