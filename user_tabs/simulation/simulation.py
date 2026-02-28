# VTK Vismach simulation tab for probe_basic
# Based on vtk-vismach by Sigma1912 (David Mueller)
# Origin: https://github.com/Sigma1912/vtk-vismach

import os, sys
import vtk
import hal
import math

from qtpy import uic
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QWidget, QVBoxLayout, QCheckBox
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

TAB_DIR = os.path.dirname(os.path.abspath(__file__))

# Prefer local usertab modules first
if TAB_DIR not in sys.path:
    sys.path.insert(0, TAB_DIR)

# Optional: keep config dir too, but AFTER TAB_DIR if you still import other config modules
CFG_DIR = os.path.abspath(os.path.join(TAB_DIR, "..", ".."))
if CFG_DIR not in sys.path:
    sys.path.append(CFG_DIR)

import sim_machine as machine
from vtk_vismach import _Plotter, ModelGroups




class UserTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        uic.loadUi(os.path.join(os.path.dirname(__file__), ui_file), self)

        # --- View buttons ---
        self._ortho_flip = {"XY": -1, "XZ": -1, "YZ": -1}

        self.btnYZ.clicked.connect(lambda: self.set_ortho_view_flip("YZ"))
        self.btnXZ.clicked.connect(lambda: self.set_ortho_view_flip("XZ"))
        self.btnXY.clicked.connect(lambda: self.set_ortho_view_flip("XY"))
        self.btnDimetric.clicked.connect(self.set_dimetric_view)
        self.btnZUp.clicked.connect(self.set_z_up_viewup)
        self.btnShowAll.clicked.connect(self.show_all)

        # --- Projection ---
        self.rbtnPerspective.toggled.connect(self.on_projection_changed)
        self.rbtnParallel.toggled.connect(self.on_projection_changed)


        # --- put VTK widget inside the Designer frame ---
        self.vtkInteractor = QVTKRenderWindowInteractor(self.vtkContainer)
        layout = self.vtkContainer.layout()
        if layout is None:
            layout = QVBoxLayout(self.vtkContainer)
            layout.setContentsMargins(0, 0, 0, 0)
            self.vtkContainer.setLayout(layout)
        layout.addWidget(self.vtkInteractor)

        # --- build your vismach model (must NOT start main window) ---
        self.comp, self.model, self.huds, self.gcode_path, self.workpiece = machine.build_vismach_model()

        # -----------------------------
        # Stock (workpiece) controls
        # -----------------------------
        if self.workpiece is not None:
            self.spStockSizeX.valueChanged.connect(self.apply_stock)
            self.spStockSizeY.valueChanged.connect(self.apply_stock)
            self.spStockSizeZ.valueChanged.connect(self.apply_stock)

            self.spStockOffsetX.valueChanged.connect(self.apply_stock)
            self.spStockOffsetY.valueChanged.connect(self.apply_stock)
            self.spStockOffsetZ.valueChanged.connect(self.apply_stock)



        # --- renderer / render window ---
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.2, 0.3, 0.4)

        self.renderWindow = self.vtkInteractor.GetRenderWindow()
        self.renderWindow.AddRenderer(self.renderer)

        if self.workpiece is not None:
            self.apply_stock()


        self.renderer.AddActor(self.model)

        # -----------------------------
        # Model group visibility UI
        # -----------------------------
        self.model_groups = ModelGroups(self.model)
        self.group_checkboxes = []

        # a layout inside your Designer widget groupsContainer
        grp_layout = self.groupsContainer.layout()
        if grp_layout is None:
            grp_layout = QVBoxLayout(self.groupsContainer)
            grp_layout.setContentsMargins(0, 0, 0, 0)
            self.groupsContainer.setLayout(grp_layout)

        

        for group in self.model_groups.groups_in_model.keys():
            cb = QCheckBox(f"{group}")
            cb.setObjectName(group)
            cb.setChecked(True)
            cb.toggled.connect(self.update_groups)
            grp_layout.addWidget(cb)
            self.group_checkboxes.append(cb)    
        self.update_groups()

        # --- backplot ---
        self.vcomp = hal.component("vismach_tab")
        self.vcomp.newpin("plotclear", hal.HAL_BIT, hal.HAL_IN)
        self.vcomp.ready()
        


        self.backplot = _Plotter(self.model, self.vcomp, "plotclear")
        self._pending_plotclear = False
        self.renderer.AddActor(self.backplot)

        # HUDs
        if self.huds:
            for hud in self.huds:
                self.renderer.AddActor(hud)

        # -----------------------------
        # Tracking state
        # -----------------------------
        self.trackMode = "None"              # "None" | "Tool" | "Work"
        self.last_tracking_position = None   # (x,y,z) or None

        # -----------------------------
        # Tracking radio buttons
        # -----------------------------
        self.rbtnTrackNone.toggled.connect(self.on_tracking_changed)
        self.rbtnTrackTool.toggled.connect(self.on_tracking_changed)
        self.rbtnTrackWork.toggled.connect(self.on_tracking_changed)

        # -----------------------------
        # HUD checkbox
        # -----------------------------
        self.ckShowHud.toggled.connect(self.on_hud_toggled)
        # optional default on:
        self.ckShowHud.setChecked(True)

        # -----------------------------
        # Backplot clear button
        # -----------------------------
        self.btnClearBackplot.clicked.connect(self.on_clear_backplot)

        # --- Match standalone interaction behavior (drag-only rotation) ---
        interactor = self.vtkInteractor.GetRenderWindow().GetInteractor()
        style = vtk.vtkInteractorStyleTrackballCamera()
        interactor.SetInteractorStyle(style)


        # init interactor + update loop
        self.vtkInteractor.Initialize()
        self._update_scene()
        QTimer.singleShot(0, self._init_camera_view)




        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_scene)
        self.timer.start(50)

    def _update_scene(self):
        # update model nodes (same idea as vtk_vismach.main update loop)
        def walk(obj):
            if hasattr(obj, "GetParts"):
                parts = obj.GetParts()
                parts.InitTraversal()
                while True:
                    item = parts.GetNextProp()
                    if item is None:
                        break
                    if hasattr(item, "update"):
                        item.update()
                    if hasattr(item, "transform"):
                        item.transform()
                    if hasattr(item, "capture"):
                        item.capture()
                    if isinstance(item, vtk.vtkAssembly):
                        walk(item)

        walk(self.model)

        if self.gcode_path is not None:
            self.gcode_path.check_for_update()

        # one-cycle clear pulse for backplot
        if getattr(self, "_pending_plotclear", False):
            try:
                self.vcomp.plotclear = 1
            except Exception:
                try:
                    self.vcomp["plotclear"] = True
                except Exception:
                    pass

        self.backplot.update()

        # drop the pulse after update has consumed it
        if getattr(self, "_pending_plotclear", False):
            try:
                self.vcomp.plotclear = 0
            except Exception:
                try:
                    self.vcomp["plotclear"] = False
                except Exception:
                    pass
            self._pending_plotclear = False


        if self.huds:
            for hud in self.huds:
                hud.update()

        # -----------------------------
        # Camera tracking (Tool / Work)
        # -----------------------------
        if self.trackMode in ("Tool", "Work") and hasattr(self.backplot, "tool_tracker"):
            cam = self.renderer.GetActiveCamera()
            fp = cam.GetFocalPoint()
            cp = cam.GetPosition()

            if self.trackMode == "Tool":
                m = self.backplot.tool_tracker.current_matrix
            else:
                m = self.backplot.work_tracker.current_matrix

            x = m.GetElement(0, 3)
            y = m.GetElement(1, 3)
            z = m.GetElement(2, 3)

            if self.last_tracking_position is None:
                self.last_tracking_position = (x, y, z)
            else:
                lx, ly, lz = self.last_tracking_position
                dx, dy, dz = (x - lx), (y - ly), (z - lz)

                cam.SetFocalPoint(fp[0] + dx, fp[1] + dy, fp[2] + dz)
                cam.SetPosition(cp[0] + dx, cp[1] + dy, cp[2] + dz)

                self.last_tracking_position = (x, y, z)


        self.renderWindow.Render()


    def _capture_zoom(self):
        cam = self._camera()
        return {
            "parallel": bool(cam.GetParallelProjection()),
            "parallel_scale": cam.GetParallelScale(),
            "distance": cam.GetDistance(),
            "view_angle": cam.GetViewAngle(),
        }

    def _restore_zoom(self, z):
        cam = self._camera()
        if z["parallel"]:
            cam.SetParallelScale(z["parallel_scale"])
        else:
            # Keep view angle as-is (or restore it)
            cam.SetViewAngle(z["view_angle"])
            # Distance is implied by position/focal; we'll preserve it in the view functions



    def _camera(self):
        return self.renderer.GetActiveCamera()



    def _reset_camera_fit(self):
        # VTK-fit for both perspective + parallel (also fixes ParallelScale)
        self.renderer.ResetCamera()
        self.renderer.ResetCameraClippingRange()


    def _scene_bounds(self):
        """
        Return (xmin,xmax,ymin,ymax,zmin,zmax) for the current visible model.
        """
        b = self.model.GetBounds()
        # If bounds are invalid (can happen before first render), force a render once
        if b is None or b[0] > b[1]:
            self.renderWindow.Render()
            b = self.model.GetBounds()
        return b


    def show_all(self):
        self._reset_camera_fit()
        self.renderWindow.Render()


    def on_projection_changed(self):
        cam = self._camera()

        # Distance from camera to focal point (VTK provides this)
        d = cam.GetDistance()
        if d <= 1e-9:
            d = 1e-9

        if self.rbtnParallel.isChecked():
            # --- Perspective -> Parallel: choose ParallelScale to match current vertical FOV ---
            view_angle_deg = cam.GetViewAngle()
            view_angle_rad = math.radians(view_angle_deg)

            parallel_scale = d * math.tan(0.5 * view_angle_rad)

            cam.ParallelProjectionOn()
            cam.SetParallelScale(parallel_scale)

        else:
            # --- Parallel -> Perspective: choose ViewAngle to match current ParallelScale ---
            parallel_scale = cam.GetParallelScale()
            if parallel_scale <= 1e-12:
                parallel_scale = 1e-12

            view_angle_rad = 2.0 * math.atan(parallel_scale / d)
            view_angle_deg = math.degrees(view_angle_rad)

            # Optional clamp to avoid extreme FOV values
            view_angle_deg = max(1.0, min(170.0, view_angle_deg))

            cam.ParallelProjectionOff()
            cam.SetViewAngle(view_angle_deg)

        # Keep framing stable: no ResetCamera() here
        self.renderer.ResetCameraClippingRange()
        self.renderWindow.Render()


    def _init_camera_view(self):
        # 1) Fit once so the initial camera distance / ParallelScale is sane
        self._reset_camera_fit()

        # 2) Then apply your preferred startup orientation without changing zoom
        self.set_dimetric_view()



    def set_z_up_viewup(self):
        """
        Force Z as up direction (useful after trackball rotations).
        """
        cam = self._camera()
        cam.SetViewUp(0, 0, 1)
        self.renderWindow.Render()

    def set_dimetric_view(self):
        z = self._capture_zoom()

        b = self._scene_bounds()
        xmin, xmax, ymin, ymax, zmin, zmax = b
        cx = 0.5 * (xmin + xmax)
        cy = 0.5 * (ymin + ymax)
        cz = 0.5 * (zmin + zmax)

        cam = self._camera()
        d = max(cam.GetDistance(), 1e-6)

        cam.SetFocalPoint(cx, cy, cz)

        # A nice dimetric direction (normalized-ish). You can tweak signs to taste.
        # This just sets orientation; zoom comes from d / ParallelScale.
        vx, vy, vz = (1.0, -1.0, 0.8)
        n = (vx*vx + vy*vy + vz*vz) ** 0.5
        vx, vy, vz = (vx/n, vy/n, vz/n)

        cam.SetPosition(cx + vx * d, cy + vy * d, cz + vz * d)
        cam.SetViewUp(0, 0, 1)
        cam.OrthogonalizeViewUp()

        if z["parallel"]:
            cam.SetParallelScale(z["parallel_scale"])

        self.renderer.ResetCameraClippingRange()
        self.renderWindow.Render()


    def set_ortho_view_flip(self, plane):
        # toggle direction each time the same button is pressed
        self._ortho_flip[plane] *= -1
        self.set_ortho_view(plane, direction=self._ortho_flip[plane])

    def set_ortho_view(self, plane, direction=1):
        z = self._capture_zoom()

        b = self._scene_bounds()
        xmin, xmax, ymin, ymax, zmin, zmax = b
        cx = 0.5 * (xmin + xmax)
        cy = 0.5 * (ymin + ymax)
        cz = 0.5 * (zmin + zmax)

        cam = self._camera()

        # Preserve current distance-to-focal for perspective mode
        d = max(cam.GetDistance(), 1e-6)

        cam.SetFocalPoint(cx, cy, cz)

        if plane == "XY":
            cam.SetPosition(cx, cy, cz + direction * d)
            cam.SetViewUp(0, 1, 0)
        elif plane == "XZ":
            cam.SetPosition(cx, cy + direction * d, cz)
            cam.SetViewUp(0, 0, 1)
        elif plane == "YZ":
            cam.SetPosition(cx + direction * d, cy, cz)
            cam.SetViewUp(0, 0, 1)

        cam.OrthogonalizeViewUp()

        # Restore zoom for parallel (ParallelScale). Perspective zoom preserved by using d.
        if z["parallel"]:
            cam.SetParallelScale(z["parallel_scale"])

        self.renderer.ResetCameraClippingRange()
        self.renderWindow.Render()



    
    def on_tracking_changed(self):
        if self.rbtnTrackTool.isChecked():
            self.trackMode = "Tool"
        elif self.rbtnTrackWork.isChecked():
            self.trackMode = "Work"
        else:
            self.trackMode = "None"

        # reset tracking baseline so camera doesn't jump
        self.last_tracking_position = None

    def on_hud_toggled(self, checked):
        if self.huds:
            for hud in self.huds:
                hud.SetVisibility(1 if checked else 0)
        self.renderWindow.Render()

    def on_clear_backplot(self):
        # request a one-cycle clear pulse (handled in _update_scene)
        self._pending_plotclear = True

    def apply_stock(self):
        if not self.workpiece:
            return

        sx = self.spStockSizeX.value()
        sy = self.spStockSizeY.value()
        sz = self.spStockSizeZ.value()

        ox = self.spStockOffsetX.value()
        oy = self.spStockOffsetY.value()
        oz = self.spStockOffsetZ.value()

        self.workpiece.set_params(sx, sy, sz, ox, oy, oz)
        self.renderWindow.Render()


    def update_groups(self):
        self.model_groups.update(self.group_checkboxes)
        #self._reset_camera_fit()
        self.renderWindow.Render()




        



