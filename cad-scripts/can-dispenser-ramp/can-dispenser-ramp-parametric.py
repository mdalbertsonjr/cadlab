import FreeCAD
import Part
import Sketcher

doc = FreeCAD.newDocument("CanDispenserRamp")

# --- Parameters (Spreadsheet) ---
sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")

# Primary parameters
sheet.set("A1", "can_diameter");     sheet.set("B1", "66.0");   sheet.setAlias("B1", "can_diameter")
sheet.set("A2", "can_height");       sheet.set("B2", "122.7");  sheet.setAlias("B2", "can_height")
sheet.set("A3", "wall");             sheet.set("B3", "3.5");    sheet.setAlias("B3", "wall")
sheet.set("A4", "clearance");        sheet.set("B4", "13.0");   sheet.setAlias("B4", "clearance")
sheet.set("A5", "side_wall_height"); sheet.set("B5", "85.5");   sheet.setAlias("B5", "side_wall_height")
sheet.set("A6", "main_length");      sheet.set("B6", "171.6");  sheet.setAlias("B6", "main_length")
sheet.set("A7", "taper_length");     sheet.set("B7", "61.3");   sheet.setAlias("B7", "taper_length")

# Derived dimensions
sheet.set("A8", "channel_width");    sheet.set("B8", "=B2 + 2 * B3 + B4");  sheet.setAlias("B8", "channel_width")
sheet.set("A9", "trough_width");     sheet.set("B9", "=B8 - 2 * B3");       sheet.setAlias("B9", "trough_width")
sheet.set("A10", "ramp_length");     sheet.set("B10", "=B6 + B7");          sheet.setAlias("B10", "ramp_length")

doc.recompute()

# Outer block spans the full length; the envelope is constant (only the
# interior cut varies along the length)
outer = doc.addObject("Part::Box", "OuterBlock")
outer.setExpression("Length", "Parameters.ramp_length")
outer.setExpression("Width", "Parameters.channel_width")
outer.setExpression("Height", "Parameters.side_wall_height")

# Main-channel cutter: a full-depth open slot for the constant-cross-section span
main_cut = doc.addObject("Part::Box", "MainCut")
main_cut.setExpression("Length", "Parameters.main_length")
main_cut.setExpression("Width", "Parameters.trough_width")
main_cut.setExpression("Height", "Parameters.side_wall_height")
main_cut.setExpression("Placement.Base.y", "Parameters.wall")

# Taper cutter: the open slot narrows continuously to nothing over the taper
# span, where the two side rails close up flush -- a loft from the slot's
# open rectangular profile to a point captures the continuous closing that
# no primitive can. The profile sketch is in the YZ plane (rotated 90 deg
# about Y so its local X/Y axes map to global Z/Y).
profile_open = doc.addObject("Sketcher::SketchObject", "TaperProfileOpen")
profile_open.Placement = FreeCAD.Placement(
    FreeCAD.Vector(0, 0, 0),
    FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90),
)
profile_open.addGeometry(Part.LineSegment(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 1, 0)), False)
profile_open.addGeometry(Part.LineSegment(FreeCAD.Vector(0, 1, 0), FreeCAD.Vector(-1, 1, 0)), False)
profile_open.addGeometry(Part.LineSegment(FreeCAD.Vector(-1, 1, 0), FreeCAD.Vector(-1, 0, 0)), False)
profile_open.addGeometry(Part.LineSegment(FreeCAD.Vector(-1, 0, 0), FreeCAD.Vector(0, 0, 0)), False)
profile_open.addConstraint(Sketcher.Constraint("Coincident", 0, 2, 1, 1))
profile_open.addConstraint(Sketcher.Constraint("Coincident", 1, 2, 2, 1))
profile_open.addConstraint(Sketcher.Constraint("Coincident", 2, 2, 3, 1))
profile_open.addConstraint(Sketcher.Constraint("Coincident", 3, 2, 0, 1))
profile_open.addConstraint(Sketcher.Constraint("Vertical", 0))
profile_open.addConstraint(Sketcher.Constraint("Horizontal", 1))
profile_open.addConstraint(Sketcher.Constraint("Vertical", 2))
profile_open.addConstraint(Sketcher.Constraint("Horizontal", 3))
# Pin vertex 0 (point 1 of edge 0) at the sketch origin -- fully constraining
# POSITION, not just size, is required: an under-constrained profile can
# produce a shape that looks fine on casual access but is silently null
# under isValid()'s deep check.
profile_open.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0.0))
profile_open.addConstraint(Sketcher.Constraint("DistanceY", 0, 1, 0.0))
profile_open.addConstraint(Sketcher.Constraint("DistanceY", 0, 1, 0, 2, 1.0))
profile_open.addConstraint(Sketcher.Constraint("DistanceX", 1, 1, 1, 2, 1.0))
profile_open.setExpression("Constraints[10]", "Parameters.side_wall_height")
profile_open.setExpression("Constraints[11]", "Parameters.trough_width")
profile_open.setExpression("Placement.Base.x", "Parameters.main_length")
profile_open.setExpression("Placement.Base.y", "Parameters.wall")
doc.recompute()
assert profile_open.FullyConstrained, "Taper profile sketch is not fully constrained"

# Taper tip: the point the open slot's cross-section shrinks to at the far end
taper_tip = doc.addObject("Part::Vertex", "TaperTip")
taper_tip.setExpression("X", "Parameters.ramp_length")
taper_tip.setExpression("Y", "Parameters.channel_width / 2")
taper_tip.setExpression("Z", "Parameters.side_wall_height / 2")

# Loft from the open slot profile down to the tip -- the continuous closing
taper_cut = doc.addObject("Part::Loft", "TaperCut")
taper_cut.Sections = [profile_open, taper_tip]
taper_cut.Solid = True
taper_cut.Ruled = True

# Fuse the two cutters into one continuous cutting tool
cutter = doc.addObject("Part::Fuse", "Cutter")
cutter.Base = main_cut
cutter.Tool = taper_cut

# Cut the tool out of the outer block to form the open, tapering channel
result = doc.addObject("Part::Cut", "Result")
result.Base = outer
result.Tool = cutter

doc.recompute()

# Loft/Sweep can silently produce invalid or wrong-topology geometry with no
# error indicator -- assert before saving so a broken result is caught here.
if not result.Shape.isValid() or len(result.Shape.Solids) != 1:
    raise RuntimeError(
        f"Invalid or non-solid geometry after Loft/Sweep: "
        f"isValid={result.Shape.isValid()}, solids={len(result.Shape.Solids)}"
    )

# Save parametric model (editable in FreeCAD GUI)
doc.saveAs("cad-scripts/can-dispenser-ramp/can-dispenser-ramp-parametric.FCStd")
print("Saved: cad-scripts/can-dispenser-ramp/can-dispenser-ramp-parametric.FCStd")
