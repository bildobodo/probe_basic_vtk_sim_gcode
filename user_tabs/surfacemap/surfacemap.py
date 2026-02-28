
import os
import linuxcnc
import yaml
import numpy as np

from qtpy import uic
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QWidget, QVBoxLayout
from qtpyvcp.plugins import getPlugin
from qtpyvcp.utilities import logger
from qtpyvcp.actions.machine_actions import issue_mdi
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from scipy.interpolate import griddata

LOG = logger.getLogger(__name__)
STATUS = getPlugin('status')
TOOL_TABLE = getPlugin('tooltable')
INI_FILE = linuxcnc.ini(os.getenv('INI_FILE_NAME'))

class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        uic.loadUi(os.path.join(os.path.dirname(__file__), ui_file), self)

        # Connect input field signals to update LinuxCNC parameters
        self.surface_scan_x0_3050.editingFinished.connect(self.update_parameters)
        self.surface_scan_x1_3051.editingFinished.connect(self.update_parameters)
        self.surface_scan_y0_3052.editingFinished.connect(self.update_parameters)
        self.surface_scan_y1_3053.editingFinished.connect(self.update_parameters)
        self.surface_scan_xprobes_3054.editingFinished.connect(self.update_parameters)
        self.surface_scan_yprobes_3055.editingFinished.connect(self.update_parameters)
        self.probe_fast_fr_3056.editingFinished.connect(self.update_parameters)
        self.probe_slow_fr_3057.editingFinished.connect(self.update_parameters)
        self.surface_scan_safez_3058.editingFinished.connect(self.update_parameters)
        self.surface_scan_depthz_3059.editingFinished.connect(self.update_parameters)

        # Connect your new button
        self.SaveProbeParameters.clicked.connect(self.save_probe_parameters)

        # Initialize the Matplotlib plot
        self.init_plots()

        # Update on button press
        self.ShowSurfaceMap.clicked.connect(self.update_surface_and_heightmap)

        # Load parameters from YAML on startup
        self.load_yaml_config()

    def get_config_path(self):
        return os.path.join(os.path.dirname(__file__), "surfacemap.yml")


    def load_yaml_config(self):
        try:
            with open(self.get_config_path(), 'r') as f:
                config = yaml.safe_load(f)
            # Set UI fields from config
            self.surface_scan_x0_3050.setText(str(config.get('surface_scan_x0', 0.0)))
            self.surface_scan_x1_3051.setText(str(config.get('surface_scan_x1', 0.0)))
            self.surface_scan_y0_3052.setText(str(config.get('surface_scan_y0', 0.0)))
            self.surface_scan_y1_3053.setText(str(config.get('surface_scan_y1', 0.0)))
            self.surface_scan_xprobes_3054.setText(str(config.get('surface_scan_xprobes', 0.0)))
            self.surface_scan_yprobes_3055.setText(str(config.get('surface_scan_yprobes', 0.0)))
            self.probe_fast_fr_3056.setText(str(config.get('probe_fast_fr', 0.0)))
            self.probe_slow_fr_3057.setText(str(config.get('probe_slow_fr', 0.0)))
            self.surface_scan_safez_3058.setText(str(config.get('surface_scan_safez', 0.0)))
            self.surface_scan_depthz_3059.setText(str(config.get('surface_scan_depthz', 0.0)))
        except Exception as e:
            LOG.error(f"Failed to load YAML config: {e}")

    def save_yaml_config(self):
        config = {
            'surface_scan_x0': float(self.surface_scan_x0_3050.text() or 0.0),
            'surface_scan_x1': float(self.surface_scan_x1_3051.text() or 0.0),
            'surface_scan_y0': float(self.surface_scan_y0_3052.text() or 0.0),
            'surface_scan_y1': float(self.surface_scan_y1_3053.text() or 0.0),
            'surface_scan_xprobes': float(self.surface_scan_xprobes_3054.text() or 0.0),
            'surface_scan_yprobes': float(self.surface_scan_yprobes_3055.text() or 0.0),
            'probe_fast_fr': float(self.probe_fast_fr_3056.text() or 0.0),
            'probe_slow_fr': float(self.probe_slow_fr_3057.text() or 0.0),
            'surface_scan_safez': float(self.surface_scan_safez_3058.text() or 0.0),
            'surface_scan_depthz': float(self.surface_scan_depthz_3059.text() or 0.0),
        }
        try:
            with open(self.get_config_path(), 'w') as f:
                yaml.safe_dump(config, f)
            LOG.info("YAML config saved successfully")
        except Exception as e:
            LOG.error(f"Failed to save YAML config: {e}")

    def save_probe_parameters(self):
        self.save_yaml_config()
        self.update_parameters()

    def update_parameters(self):
        """Write GUI input values to LinuxCNC numbered parameters using issue_mdi"""
        try:
            x0 = float(self.surface_scan_x0_3050.text() or 0.0)
            x1 = float(self.surface_scan_x1_3051.text() or 0.0)
            y0 = float(self.surface_scan_y0_3052.text() or 0.0)
            y1 = float(self.surface_scan_y1_3053.text() or 0.0)
            xprobes = float(self.surface_scan_xprobes_3054.text() or 0.0)
            yprobes = float(self.surface_scan_yprobes_3055.text() or 0.0)
            fast_fr = float(self.probe_fast_fr_3056.text() or 0.0)
            slow_fr = float(self.probe_slow_fr_3057.text() or 0.0)
            safez = float(self.surface_scan_safez_3058.text() or 0.0)
            depthz = float(self.surface_scan_depthz_3059.text() or 0.0)
            issue_mdi(f"#3050 = {x0}")
            issue_mdi(f"#3051 = {x1}")
            issue_mdi(f"#3052 = {y0}")
            issue_mdi(f"#3053 = {y1}")
            issue_mdi(f"#3054 = {xprobes}")
            issue_mdi(f"#3055 = {yprobes}")
            issue_mdi(f"#3056 = {fast_fr}")
            issue_mdi(f"#3057 = {slow_fr}")
            issue_mdi(f"#3058 = {safez}")
            issue_mdi(f"#3059 = {depthz}")
            LOG.info(f"Surface scan parameters updated: x0={x0}, x1={x1}, y0={y0}, y1={y1}, "
                     f"xprobes={xprobes}, yprobes={yprobes}, fast_fr={fast_fr}, slow_fr={slow_fr}, "
                     f"safez={safez}, depthz={depthz}")
        except ValueError as e:
            LOG.error(f"Error updating surface scan parameters: {e}")
        except Exception as e:
            LOG.error(f"Unexpected error updating surface scan parameters: {e}")

    # ... (rest of your plotting and other methods remain unchanged) ...


    def init_plots(self):
        """Initialize 3D surface and 2D height map canvases."""


        # --- 3D surface plot ---
        self.fig_3d = Figure()
        self.canvas_3d = FigureCanvas(self.fig_3d)
        self.ax_3d = self.fig_3d.add_subplot(111, projection='3d')
        layout3d = self.mpl_canvas_container_3d.layout() or QVBoxLayout()
        self.mpl_canvas_container_3d.setLayout(layout3d)
        layout3d.addWidget(self.canvas_3d)

        # --- 2D height map ---
        self.fig_hmap = Figure()
        self.canvas_hmap = FigureCanvas(self.fig_hmap)
        self.ax_hmap = self.fig_hmap.add_subplot(111)
        layout_hmap = self.mpl_canvas_container_hmap.layout() or QVBoxLayout()
        self.mpl_canvas_container_hmap.setLayout(layout_hmap)
        layout_hmap.addWidget(self.canvas_hmap)

    def update_surface_and_heightmap(self):
        """Load probe data and update both 3D surface and 2D height map."""
        config_dir = os.path.dirname(os.getenv('INI_FILE_NAME'))
        filename = os.path.join(config_dir, "probe-results.txt")
        try:
            data = np.loadtxt(filename)
            if data.size == 0:
                LOG.warning("Probe data file is empty")
                return

            # Extract x, y, z
            x = data[:,0]
            y = data[:,1]
            z = data[:,2]

            # Create a grid for interpolation
            xi = np.linspace(min(x), max(x), 20)
            yi = np.linspace(min(y), max(y), 20)
            xi, yi = np.meshgrid(xi, yi)

            # Interpolate z values on the grid using cubic interpolation
            zi = griddata((x, y), z, (xi, yi), method='cubic')

            # Fill NaNs using nearest-neighbor fallback
            zi_nn = griddata((x, y), z, (xi, yi), method='nearest')
            zi = np.where(np.isnan(zi), zi_nn, zi)

            # --- 3D surface plot ---
            self.ax_3d.clear()
            # Surface plot
            self.ax_3d.plot_surface(xi, yi, zi, cmap='viridis', edgecolor='none')
            # Plot original data points
            self.ax_3d.scatter(x, y, z, color='r')
            self.ax_3d.set_title("Interpolated Surface Map")
            self.ax_3d.set_xlabel("X")
            self.ax_3d.set_ylabel("Y")
            self.ax_3d.set_zlabel("Z")
            self.canvas_3d.draw()

            # --- 2D height map ---
            self.ax_hmap.clear()
            # Plot filled contours
            contour = self.ax_hmap.contourf(xi, yi, zi, levels=100, cmap='viridis')
            # Overlay the original measurement points in red
            self.ax_hmap.scatter(x, y, color='r', s=30, label='Measured Points')
            # Set correct aspect ratio
            self.ax_hmap.set_aspect('equal', adjustable='box')
            # --- COLORBAR HANDLING (IMPORTANT) ---
            # Remove old colorbar if it exists
            if hasattr(self, "cbar_hmap") and self.cbar_hmap:
                self.cbar_hmap.remove()
            # Create new colorbar and store reference
            self.cbar_hmap = self.fig_hmap.colorbar(contour, ax=self.ax_hmap, label="Height (mm)")


            self.ax_hmap.set_title("Interpolated Height Map")
            self.ax_hmap.set_xlabel("X")
            self.ax_hmap.set_ylabel("Y")
            self.canvas_hmap.draw()

            LOG.info("Surface and height maps updated successfully")

        except Exception as e:
            LOG.error(f"Failed to update surface and height maps: {e}")

