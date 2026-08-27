import FreeCAD
import Part

doc = FreeCAD.newDocument("SanderVacAdapter")

# --- Parameters (Spreadsheet) ---
sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")

# Primary parameters
sheet.set("A1", "sander_od");        sheet.set("B1", "34.0");   sheet.setAlias("B1", "sander_od")
sheet.set("A2", "vac_od");           sheet.set("B2", "44.75");  sheet.setAlias("B2", "vac_od")
sheet.set("A3", "sander_clearance"); sheet.set("B3", "0.3");    sheet.setAlias("B3", "sander_clearance")
sheet.set("A4", "vac_clearance");    sheet.set("B4", "0.3");    sheet.setAlias("B4", "vac_clearance")
sheet.set("A5", "wall");             sheet.set("B5", "3.0");    sheet.setAlias("B5", "wall")
sheet.set("A6", "sander_len");       sheet.set("B6", "25.0");   sheet.setAlias("B6", "sander_len")
sheet.set("A7", "vac_len");          sheet.set("B7", "25.0");   sheet.setAlias("B7", "vac_len")
sheet.set("A8", "chamfer_w");        sheet.set("B8", "1.5");    sheet.setAlias("B8", "chamfer_w")
sheet.set("A9", "overlap");          sheet.set("B9", "1.0");    sheet.setAlias("B9", "overlap")

# Derived parameters (spreadsheet formulas — keeps geometry expressions simple)
sheet.set("A10", "sander_id");       sheet.set("B10", "=B1 + 2 * B3");    sheet.setAlias("B10", "sander_id")
sheet.set("A11", "vac_id");          sheet.set("B11", "=B2 + 2 * B4");    sheet.setAlias("B11", "vac_id")
sheet.set("A12", "sander_inner_r");  sheet.set("B12", "=B10 / 2");        sheet.setAlias("B12", "sander_inner_r")
sheet.set("A13", "vac_inner_r");     sheet.set("B13", "=B11 / 2");        sheet.setAlias("B13", "vac_inner_r")
sheet.set("A14", "sander_outer_r");  sheet.set("B14", "=B12 + B5");       sheet.setAlias("B14", "sander_outer_r")
sheet.set("A15", "vac_outer_r");     sheet.set("B15", "=B13 + B5");       sheet.setAlias("B15", "vac_outer_r")
sheet.set("A16", "total_len");       sheet.set("B16", "=B6 + B7");        sheet.setAlias("B16", "total_len")
sheet.set("A17", "vac_body_h");      sheet.set("B17", "=B7 + B9");        sheet.setAlias("B17", "vac_body_h")
sheet.set("A18", "sander_body_h");   sheet.set("B18", "=B6 + B9");        sheet.setAlias("B18", "sander_body_h")
sheet.set("A19", "sander_body_z");   sheet.set("B19", "=B7 - B9");        sheet.setAlias("B19", "sander_body_z")
sheet.set("A20", "chamfer_vac_r1");  sheet.set("B20", "=B13 + B8");       sheet.setAlias("B20", "chamfer_vac_r1")
sheet.set("A21", "chamfer_sand_r2"); sheet.set("B21", "=B12 + B8");       sheet.setAlias("B21", "chamfer_sand_r2")
sheet.set("A22", "chamfer_sand_z");  sheet.set("B22", "=B16 - B8");       sheet.setAlias("B22", "chamfer_sand_z")

# Transition chamfer: slopes outer wall from vac_outer_r down to sander_outer_r at the step
sheet.set("A23", "transition_h");    sheet.set("B23", "8.0");             sheet.setAlias("B23", "transition_h")
sheet.set("A24", "transition_z");    sheet.set("B24", "=B17");             sheet.setAlias("B24", "transition_z")

doc.recompute()

# --- Outer body ---
# Vac-end outer cylinder (larger diameter), positioned at z=0
vac_body = doc.addObject("Part::Cylinder", "VacBody")
vac_body.setExpression("Radius", "Parameters.vac_outer_r")
vac_body.setExpression("Height", "Parameters.vac_body_h")

# Sander-end outer cylinder (smaller diameter), overlaps vac end by 'overlap' to guarantee solid union
sander_body = doc.addObject("Part::Cylinder", "SanderBody")
sander_body.setExpression("Radius", "Parameters.sander_outer_r")
sander_body.setExpression("Height", "Parameters.sander_body_h")
sander_body.setExpression("Placement.Base.z", "Parameters.sander_body_z")

# Transition cone: slopes outer wall from vac_outer_r (bottom) to sander_outer_r (top)
# Sits just below the step at z=vac_body_h, adding material to the shoulder and reducing the
# abrupt step that causes stringing in FDM prints.
transition_cone = doc.addObject("Part::Cone", "TransitionCone")
transition_cone.setExpression("Radius1", "Parameters.vac_outer_r")
transition_cone.setExpression("Radius2", "Parameters.sander_outer_r")
transition_cone.setExpression("Height", "Parameters.transition_h")
transition_cone.setExpression("Placement.Base.z", "Parameters.transition_z")

# Fuse the two stepped cylinders, then fuse in the transition cone
step_fuse = doc.addObject("Part::Fuse", "StepFuse")
step_fuse.Base = vac_body
step_fuse.Tool = sander_body

fuse1 = doc.addObject("Part::Fuse", "OuterBody")
fuse1.Base = step_fuse
fuse1.Tool = transition_cone

# --- Inner bores ---
# Vac bore through the vac socket (z=0 to z=vac_len)
vac_bore = doc.addObject("Part::Cylinder", "VacBore")
vac_bore.setExpression("Radius", "Parameters.vac_inner_r")
vac_bore.setExpression("Height", "Parameters.vac_len")

# Sander bore through the sander socket (z=vac_len to z=total_len); shoulder limits insertion depth
sander_bore = doc.addObject("Part::Cylinder", "SanderBore")
sander_bore.setExpression("Radius", "Parameters.sander_inner_r")
sander_bore.setExpression("Height", "Parameters.sander_len")
sander_bore.setExpression("Placement.Base.z", "Parameters.vac_len")

# Subtract vac bore from outer body
cut1 = doc.addObject("Part::Cut", "Cut1")
cut1.Base = fuse1
cut1.Tool = vac_bore

# Subtract sander bore
cut2 = doc.addObject("Part::Cut", "Cut2")
cut2.Base = cut1
cut2.Tool = sander_bore

# --- Entry chamfers (truncated cones ease tube/hose insertion at each opening) ---
# Vac-end chamfer: widens the opening at z=0 (Radius1 > Radius2 so it flares outward at the base)
vac_chamfer = doc.addObject("Part::Cone", "VacChamfer")
vac_chamfer.setExpression("Radius1", "Parameters.chamfer_vac_r1")
vac_chamfer.setExpression("Radius2", "Parameters.vac_inner_r")
vac_chamfer.setExpression("Height", "Parameters.chamfer_w")

# Sander-end chamfer: widens the opening at z=total_len (Radius2 > Radius1 so it flares at the top)
sander_chamfer = doc.addObject("Part::Cone", "SanderChamfer")
sander_chamfer.setExpression("Radius1", "Parameters.sander_inner_r")
sander_chamfer.setExpression("Radius2", "Parameters.chamfer_sand_r2")
sander_chamfer.setExpression("Height", "Parameters.chamfer_w")
sander_chamfer.setExpression("Placement.Base.z", "Parameters.chamfer_sand_z")

# Subtract vac-end chamfer
cut3 = doc.addObject("Part::Cut", "Cut3")
cut3.Base = cut2
cut3.Tool = vac_chamfer

# Subtract sander-end chamfer — this is the final result
result = doc.addObject("Part::Cut", "Result")
result.Base = cut3
result.Tool = sander_chamfer

# --- Recompute and save ---
doc.recompute()
doc.saveAs("/home/developer/cad-output/sander-vac-adapter.FCStd")
print("Saved: /home/developer/cad-output/sander-vac-adapter.FCStd")
