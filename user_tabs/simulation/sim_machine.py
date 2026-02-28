#!/usr/bin/env python3

from vtk_vismach import *
import hal
import sys
import os
import threading
import time


# =================================================
# Paths
# =================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CFG_DIR  = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
path_stl = os.path.join(CFG_DIR, "machine") + os.sep



# =================================================
# Load STL files
# =================================================
try:
    frame = ReadPolyData("frame.stl", path_stl)
    frame.set_group("Machine")

    x_axis = ReadPolyData("x_axis.stl", path_stl)
    x_axis.set_group("Machine")

    y_axis = ReadPolyData("y_axis.stl", path_stl)
    y_axis.set_group("Machine")

    z_axis = ReadPolyData("z_axis.stl", path_stl)
    z_axis.set_group("Machine")

except Exception as detail:
    print(detail)
    raise SystemExit("Vismach requires STL files in working directory")


# =================================================
# HAL component + pins
# =================================================
c = hal.component("machine")

c.newpin("work_offset_x", hal.HAL_FLOAT, hal.HAL_OUT)
c.newpin("work_offset_y", hal.HAL_FLOAT, hal.HAL_OUT)
c.newpin("work_offset_z", hal.HAL_FLOAT, hal.HAL_OUT)

c.ready()

options = sys.argv[1:]


# =================================================
# Compute WORK offset (machine - work)
# =================================================
def update_offsets():
    try:
        mx = hal.get_value("joint.0.pos-fb")
        my = hal.get_value("joint.1.pos-fb")
        mz = hal.get_value("joint.2.pos-fb")

        wx = hal.get_value("halui.axis.x.pos-relative")
        wy = hal.get_value("halui.axis.y.pos-relative")
        wz = hal.get_value("halui.axis.z.pos-relative")

        c.work_offset_x = mx - wx
        c.work_offset_y = my - wy
        c.work_offset_z = mz - wz
    except Exception:
        pass


def updater():
    while True:
        update_offsets()
        time.sleep(0.1)


threading.Thread(target=updater, daemon=True).start()


# =================================================
# Read machine limits from HAL (INI pins)
# =================================================
def get_limit(pin):
    return hal.get_value(pin)


xmin = get_limit("ini.x.min_limit")
xmax = get_limit("ini.x.max_limit")

ymin = get_limit("ini.y.min_limit")
ymax = get_limit("ini.y.max_limit")

zmin = get_limit("ini.z.min_limit")
zmax = get_limit("ini.z.max_limit")

print("Machine limits from INI:")
print("X:", xmin, xmax)
print("Y:", ymin, ymax)
print("Z:", zmin, zmax)


# =================================================
# Machine limit box
# =================================================
limits = Box(
    c,
    xmin, ymin, zmin,
    xmax, ymax, zmax
)

# transparent box WITH outlines
limits.GetProperty().SetRepresentationToSurface()
limits.GetProperty().EdgeVisibilityOn()
limits.GetProperty().SetLineWidth(1.0)
limits.set_group("Limits")

# visual wrapper node (goes into tree)
limits_vis = Color([limits], 0.9, 0.9, 0.9, 0.1)


# =================================================
# Base (frame)
# =================================================
base_actor = Color([frame], 0.45, 0.45, 0.45, 1)
base_actor = Translate([base_actor], -760, -122, -294)

base = Collection([base_actor])


# =================================================
# Work coordinate system (DRO + toolpath + workpiece)
# =================================================
dro_axes = Axes(200)
dro_axes.set_group("Work Zero")

gcode_path = GCodePath()
gcode_path.set_group("Toolpath")
gcode_path.rapid_container.group = gcode_path.group

workpiece = WorkpieceBox(sx=200.0, sy=120.0, sz=25.0, ox=0.0, oy=0.0, oz=0.0)
workpiece.set_group("Workpiece")

# transparent workpiece WITH outlines (same style idea as limits)
workpiece.GetProperty().SetRepresentationToSurface()
workpiece.GetProperty().EdgeVisibilityOn()
workpiece.GetProperty().SetLineWidth(2.0)

# visual wrapper nodes (go into tree)
workpiece_vis = Color([workpiece], 0.4, 0.8, 1.0, 0.4)
gcode_feed_vis = Color([gcode_path], 0.0, 0.0, 1.0, 1)
gcode_rapid_vis = Color([gcode_path.rapid_container], 1.0, 0.5, 0.0, 1.0)

work_cs = Translate(
    [
        dro_axes,
        workpiece_vis,
        gcode_feed_vis,
        gcode_rapid_vis,
    ],
    c,
    "work_offset_x",
    "work_offset_y",
    "work_offset_z",
)

# apply tool length offset (Z)
work_cs = Translate([work_cs], hal, 0, 0, ("motion.tooloffset.z", -1))


# =================================================
# X axis (child of frame)
# =================================================
x_geo = Color([x_axis], 0.60, 0.40, 0.38, 1)
x_geo = Translate([x_geo], 319, 398, -244)

x = Translate(
    [
        x_geo,
        Capture("work"),
        limits_vis,
        work_cs,
    ],
    hal,
    ("joint.0.pos-fb", -1), 0, 0
)


# =================================================
# Z axis (child of Y) + tool
# =================================================
z_geo = Color([z_axis], 0.35, 0.45, 0.60, 1)
z_geo = Translate([z_geo], 0, 0, 0)

# Visible tool
tool_geo = CylinderZ(
    hal,
    100,
    ("halui.tool.diameter", 0.5)
)
tool_geo = Color([tool_geo], 1, 1, 0, 1)

# Move tool + capture together by tooloffset
tool_and_capture = Translate(
    [
        tool_geo,
        Capture("tool"),
    ],
    hal,
    0, 0, ("motion.tooloffset.z", -1)
)

z = Translate(
    [z_geo, tool_and_capture],
    hal,
    0, 0, ("joint.2.pos-fb", 1)
)


# =================================================
# Y axis (child of frame, carries Z)
# =================================================
y_geo = Color([y_axis], 0.35, 0.50, 0.35, 1)
y_geo = Translate([y_geo], -140, 0, 21)

y = Translate(
    [y_geo, z],  # <-- Z is CHILD of Y (unchanged)
    hal,
    0, ("joint.1.pos-fb", 1), 0
)


# =================================================
# Build model
# =================================================
model = Collection([base, x, y])


# =================================================
# HUD
# =================================================
hud = Hud(color="mint")

hud.add_txt("=== MACHINE STATUS ===")

hud.add_pin("Tool: T{:d}", hal, "halui.tool.number")
hud.add_pin("Tool length: {:6.3f}", hal, "motion.tooloffset.z")
hud.add_pin("Tool diameter: {:6.3f}", hal, "halui.tool.diameter")

hud.add_txt("----------------------")

# WORK coordinates (G54 etc)
hud.add_pin("Work X: {:8.3f}", hal, "halui.axis.x.pos-relative")
hud.add_pin("Work Y: {:8.3f}", hal, "halui.axis.y.pos-relative")
hud.add_pin("Work Z: {:8.3f}", hal, "halui.axis.z.pos-relative")

hud.add_txt("----------------------")

# MACHINE coordinates
hud.add_pin("Machine X: {:8.3f}", hal, "joint.0.pos-fb")
hud.add_pin("Machine Y: {:8.3f}", hal, "joint.1.pos-fb")
hud.add_pin("Machine Z: {:8.3f}", hal, "joint.2.pos-fb")


# =================================================
# Export builder for embedded UI (QtPyVCP tab)
# =================================================
def build_vismach_model():
    """
    Build and return the objects needed to embed this simulation in an existing Qt app.
    Returns: (comp, model, huds_list, gcode_path, workpiece)
    """
    return c, model, [hud], gcode_path, workpiece


# =================================================
# Start standalone Vismach (only when run directly)
# =================================================
if __name__ == "__main__":
    main(
        options,
        c,
        model,
        huds=[hud],
        gcode_path=gcode_path,
        workpiece=workpiece,
        window_width=1000,
        window_height=800,
        window_title="3 Axis Machine",
    )
