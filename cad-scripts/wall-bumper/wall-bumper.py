import FreeCAD
import Part

doc = FreeCAD.newDocument("WallBumper")

# --- Parameters (Spreadsheet) ---
sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")

# Primary dimensions
sheet.set("A1", "total_length");      sheet.set("B1", "35.0");  sheet.setAlias("B1", "total_length")      # max 38.1 mm (1.5 in)
sheet.set("A2", "flange_width");      sheet.set("B2", "10.0");  sheet.setAlias("B2", "flange_width")      # contact face Y
sheet.set("A3", "flange_depth");      sheet.set("B3", "10.0");  sheet.setAlias("B3", "flange_depth")      # contact face Z (1 cm sq)
sheet.set("A4", "flange_thickness");  sheet.set("B4", "4.0");   sheet.setAlias("B4", "flange_thickness")  # X thickness of each flange
sheet.set("A5", "web_width");      sheet.set("B5", "6.0");        sheet.setAlias("B5", "web_width")      # narrowed web Y (I-shape visible from top)

# Derived dimensions
sheet.set("A6", "web_length");    sheet.set("B6", "=B1 - 2 * B4");  sheet.setAlias("B6", "web_length")    # space between flanges
sheet.set("A7", "web_y_offset");  sheet.set("B7", "=(B2 - B5) / 2"); sheet.setAlias("B7", "web_y_offset")  # center web in Y
sheet.set("A8", "flange2_x");     sheet.set("B8", "=B1 - B4");       sheet.setAlias("B8", "flange2_x")     # X start of second flange

doc.recompute()

# Bin-side contact flange
flange1 = doc.addObject("Part::Box", "Flange1")
flange1.setExpression("Length", "Parameters.flange_thickness")
flange1.setExpression("Width",  "Parameters.flange_width")
flange1.setExpression("Height", "Parameters.flange_depth")

# Connecting web — same height as flanges (flat build plate, no supports), narrower in Y only
web = doc.addObject("Part::Box", "Web")
web.setExpression("Length", "Parameters.web_length")
web.setExpression("Width",  "Parameters.web_width")
web.setExpression("Height", "Parameters.flange_depth")
web.setExpression("Placement.Base.x", "Parameters.flange_thickness")
web.setExpression("Placement.Base.y", "Parameters.web_y_offset")

# Wall-side contact flange
flange2 = doc.addObject("Part::Box", "Flange2")
flange2.setExpression("Length", "Parameters.flange_thickness")
flange2.setExpression("Width",  "Parameters.flange_width")
flange2.setExpression("Height", "Parameters.flange_depth")
flange2.setExpression("Placement.Base.x", "Parameters.flange2_x")

# Fuse flange1 + web, then add flange2
fuse1 = doc.addObject("Part::Fuse", "Fuse1")
fuse1.Base = flange1
fuse1.Tool = web

bumper = doc.addObject("Part::Fuse", "Bumper")
bumper.Base = fuse1
bumper.Tool = flange2

doc.recompute()

doc.saveAs("/home/developer/cad-output/wall-bumper.FCStd")
print("Saved: /home/developer/cad-output/wall-bumper.FCStd")
