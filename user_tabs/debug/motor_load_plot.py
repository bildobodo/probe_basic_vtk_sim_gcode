
#!/usr/bin/env python3
"""
Motor and Spindle Load Plotter for LinuxCNC
Plots X, Y, Z axis loads and spindle load as percentage (0–300%)
"""

import subprocess
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
import time

# Configuration
HISTORY_SIZE = 500
UPDATE_INTERVAL = 200  # ms
MAX_PERCENT = 300.0

class LoadPlotter:
    def __init__(self):
        self.time_data = deque(maxlen=HISTORY_SIZE)

        # Buffers for loads
        self.x_load = deque(maxlen=HISTORY_SIZE)
        self.y_load = deque(maxlen=HISTORY_SIZE)
        self.z_load = deque(maxlen=HISTORY_SIZE)
        self.spindle_load = deque(maxlen=HISTORY_SIZE)

        self.start_time = time.time()

        # Create figure with 2 rows × 2 columns
        self.fig, self.axes = plt.subplots(2, 2, figsize=(12, 8))
        self.fig.suptitle('Motor and Spindle Load Monitor (0–300%)', fontsize=14, fontweight='bold')
        self.fig.canvas.manager.set_window_title('Motor and Spindle Load Monitor')

        # X Load
        self.ax_x = self.axes[0, 0]
        self.ax_x.set_title('X Axis Load')
        self.ax_x.set_ylabel('Load (%)')
        self.line_x, = self.ax_x.plot([], [], 'b-', linewidth=1.5, zorder=3)
        self.ax_x.set_ylim(0, MAX_PERCENT)
        self.ax_x.grid(True)

        # Y Load
        self.ax_y = self.axes[0, 1]
        self.ax_y.set_title('Y Axis Load')
        self.ax_y.set_ylabel('Load (%)')
        self.line_y, = self.ax_y.plot([], [], 'g-', linewidth=1.5, zorder=3)
        self.ax_y.set_ylim(0, MAX_PERCENT)
        self.ax_y.grid(True)

        # Z Load
        self.ax_z = self.axes[1, 0]
        self.ax_z.set_title('Z Axis Load')
        self.ax_z.set_ylabel('Load (%)')
        self.line_z, = self.ax_z.plot([], [], 'r-', linewidth=1.5, zorder=3)
        self.ax_z.set_ylim(0, MAX_PERCENT)
        self.ax_z.grid(True)

        # Spindle Load
        self.ax_spindle = self.axes[1, 1]
        self.ax_spindle.set_title('Spindle Load')
        self.ax_spindle.set_ylabel('Load (%)')
        self.line_spindle, = self.ax_spindle.plot([], [], 'm-', linewidth=1.5, zorder=3)
        self.ax_spindle.set_ylim(0, MAX_PERCENT)
        self.ax_spindle.grid(True)

        # Color bands for all axes
        for ax in [self.ax_x, self.ax_y, self.ax_z, self.ax_spindle]:
            ax.axhspan(0, 100, facecolor='lightgreen', alpha=0.3, zorder=0)
            ax.axhspan(100, 200, facecolor='lightyellow', alpha=0.3, zorder=0)
            ax.axhspan(200, 300, facecolor='lightcoral', alpha=0.3, zorder=0)

        # Track fills
        self.fill_x = None
        self.fill_y = None
        self.fill_z = None
        self.fill_spindle = None

        plt.tight_layout()

    def get_hal_value(self, pin):
        try:
            result = subprocess.run(['halcmd', 'getp', pin], capture_output=True, text=True, timeout=0.1)
            return float(result.stdout.strip())
        except:
            return 0.0

    def calculate_percentage(self, torque):
        # Convert torque to percentage and remove sign
        return abs(round(torque / 10.0))  # Adjust divisor if needed

    def update(self, frame):
        current_time = time.time() - self.start_time

        x_load = self.calculate_percentage(self.get_hal_value('lcec.0.JOINT0_X.actual-torque'))
        y_load = self.calculate_percentage(self.get_hal_value('lcec.0.JOINT1_Y.actual-torque'))
        z_load = self.calculate_percentage(self.get_hal_value('lcec.0.JOINT2_Z.actual-torque'))
        spindle_load = self.calculate_percentage(self.get_hal_value('lcec.0.SPINDLE0.actual-torque'))


        # Append data
        self.time_data.append(current_time)
        self.x_load.append(x_load)
        self.y_load.append(y_load)
        self.z_load.append(z_load)
        self.spindle_load.append(spindle_load)

        t = np.array(self.time_data)

        # Update plots and fills
        self.line_x.set_data(t, self.x_load)
        self.ax_x.set_xlim(t.min(), t.max())
        self.ax_x.relim(); self.ax_x.autoscale_view()
        if self.fill_x: self.fill_x.remove()
        self.fill_x = self.ax_x.fill_between(t, self.x_load, color='blue', alpha=0.3, zorder=1)

        self.line_y.set_data(t, self.y_load)
        self.ax_y.set_xlim(t.min(), t.max())
        self.ax_y.relim(); self.ax_y.autoscale_view()
        if self.fill_y: self.fill_y.remove()
        self.fill_y = self.ax_y.fill_between(t, self.y_load, color='green', alpha=0.3, zorder=1)

        self.line_z.set_data(t, self.z_load)
        self.ax_z.set_xlim(t.min(), t.max())
        self.ax_z.relim(); self.ax_z.autoscale_view()
        if self.fill_z: self.fill_z.remove()
        self.fill_z = self.ax_z.fill_between(t, self.z_load, color='red', alpha=0.3, zorder=1)

        self.line_spindle.set_data(t, self.spindle_load)
        self.ax_spindle.set_xlim(t.min(), t.max())
        self.ax_spindle.relim(); self.ax_spindle.autoscale_view()
        if self.fill_spindle: self.fill_spindle.remove()
        self.fill_spindle = self.ax_spindle.fill_between(t, self.spindle_load, color='magenta', alpha=0.3, zorder=1)

        return (self.line_x, self.line_y, self.line_z, self.line_spindle)

    def run(self):
        self.anim = FuncAnimation(self.fig, self.update, interval=UPDATE_INTERVAL, blit=False, cache_frame_data=False)
        plt.show()

def main():
    print("Starting Motor and Spindle Load Plotter...")
    plotter = LoadPlotter()
    plotter.run()

if __name__ == '__main__':
    main()
