import os
import subprocess
from qtpy import uic
from qtpy.QtWidgets import QWidget
from qtpyvcp.utilities import logger

LOG = logger.getLogger(__name__)


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)

        # Load UI from same folder as this file
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        uic.loadUi(os.path.join(os.path.dirname(__file__), ui_file), self)

        # Buttons
        self.FerrorPlot.clicked.connect(self.show_ferror_plot)
        self.LoadPlot.clicked.connect(self.show_motor_load_plot)

    def _tab_dir(self):
        return os.path.dirname(os.path.abspath(__file__))

    def show_ferror_plot(self):
        script_path = os.path.join(self._tab_dir(), "ferror_plot.py")

        if not os.path.exists(script_path):
            LOG.error(f"Script not found: {script_path}")
            return

        try:
            subprocess.Popen(["python3", script_path])
            LOG.info(f"Started ferror plot: {script_path}")
        except Exception as e:
            LOG.error(f"Failed to start ferror plot: {e}")

    def show_motor_load_plot(self):
        script_path = os.path.join(self._tab_dir(), "motor_load_plot.py")

        if not os.path.exists(script_path):
            LOG.error(f"Script not found: {script_path}")
            return

        try:
            subprocess.Popen(["python3", script_path])
            LOG.info(f"Started motor load plot: {script_path}")
        except Exception as e:
            LOG.error(f"Failed to start motor load plot: {e}")
