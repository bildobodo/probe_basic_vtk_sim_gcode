
#!/usr/bin/env python3
"""
Real-time Position Plot for LinuxCNC (No startup check)
Shows commanded vs actual position and following error for X, Y, Z axes
Includes XY and 3D trajectory plots
"""

import subprocess
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
import time
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

# Configuration
HISTORY_SIZE = 500
UPDATE_INTERVAL = 50  # ms

class RealtimePlotter:
    def __init__(self):
        self.time_data = deque(maxlen=HISTORY_SIZE)

        # Buffers for X, Y, Z
        self.x_cmd, self.x_fb, self.x_err = deque(maxlen=HISTORY_SIZE), deque(maxlen=HISTORY_SIZE), deque(maxlen=HISTORY_SIZE)
        self.y_cmd, self.y_fb, self.y_err = deque(maxlen=HISTORY_SIZE), deque(maxlen=HISTORY_SIZE), deque(maxlen=HISTORY_SIZE)
        self.z_cmd, self.z_fb, self.z_err = deque(maxlen=HISTORY_SIZE), deque(maxlen=HISTORY_SIZE), deque(maxlen=HISTORY_SIZE)

        self.start_time = time.time()

        # Layout: 3 rows × 3 columns
        self.fig = plt.figure(figsize=(16, 10))
        self.fig.suptitle('LinuxCNC Real-Time Position Monitor (X, Y, Z)', fontsize=14, fontweight='bold')

        # GridSpec for flexible layout
        gs = self.fig.add_gridspec(3, 3)

        # Position plots
        self.ax_x_pos = self.fig.add_subplot(gs[0, 0])
        self.ax_y_pos = self.fig.add_subplot(gs[0, 1])
        self.ax_z_pos = self.fig.add_subplot(gs[0, 2])

        self.ax_x_pos.set_title('X Position')
        self.ax_x_pos.set_xlabel('Time (s)')
        self.ax_x_pos.set_ylabel('Position (mm)')

        self.ax_y_pos.set_title('Y Position')
        self.ax_y_pos.set_xlabel('Time (s)')
        self.ax_y_pos.set_ylabel('Position (mm)')

        self.ax_z_pos.set_title('Z Position')
        self.ax_z_pos.set_xlabel('Time (s)')
        self.ax_z_pos.set_ylabel('Position (mm)')

        self.line_x_cmd, = self.ax_x_pos.plot([], [], 'b-', label='Command')
        self.line_x_fb, = self.ax_x_pos.plot([], [], 'r-', label='Feedback')
        self.ax_x_pos.legend(); self.ax_x_pos.grid(True)

        self.line_y_cmd, = self.ax_y_pos.plot([], [], 'b-', label='Command')
        self.line_y_fb, = self.ax_y_pos.plot([], [], 'r-', label='Feedback')
        self.ax_y_pos.legend(); self.ax_y_pos.grid(True)

        self.line_z_cmd, = self.ax_z_pos.plot([], [], 'b-', label='Command')
        self.line_z_fb, = self.ax_z_pos.plot([], [], 'r-', label='Feedback')
        self.ax_z_pos.legend(); self.ax_z_pos.grid(True)

        # Error plots
        self.ax_x_err = self.fig.add_subplot(gs[1, 0])
        self.ax_y_err = self.fig.add_subplot(gs[1, 1])
        self.ax_z_err = self.fig.add_subplot(gs[1, 2])

        self.ax_x_err.set_title('X Following Error')
        self.ax_x_err.set_xlabel('Time (s)')
        self.ax_x_err.set_ylabel('Error (µm)')

        self.ax_y_err.set_title('Y Following Error')
        self.ax_y_err.set_xlabel('Time (s)')
        self.ax_y_err.set_ylabel('Error (µm)')

        self.ax_z_err.set_title('Z Following Error')
        self.ax_z_err.set_xlabel('Time (s)')
        self.ax_z_err.set_ylabel('Error (µm)')

        self.line_x_err, = self.ax_x_err.plot([], [], 'g-')
        self.line_y_err, = self.ax_y_err.plot([], [], 'g-')
        self.line_z_err, = self.ax_z_err.plot([], [], 'g-')

        for ax in [self.ax_x_err, self.ax_y_err, self.ax_z_err]:
            ax.axhline(y=0, color='k', linewidth=0.5)
            ax.axhline(y=20, color='r', linestyle='--', linewidth=0.5)
            ax.axhline(y=-20, color='r', linestyle='--', linewidth=0.5)
            ax.grid(True)

        # XY trajectory
        self.ax_xy = self.fig.add_subplot(gs[2, 0])
        self.ax_xy.set_title('XY Trajectory')
        self.ax_xy.set_xlabel('X (mm)')
        self.ax_xy.set_ylabel('Y (mm)')
        self.line_xy_cmd, = self.ax_xy.plot([], [], 'b-', alpha=0.5)
        self.line_xy_fb, = self.ax_xy.plot([], [], 'r-', alpha=0.7)
        self.ax_xy.set_aspect('equal', adjustable='datalim')
        self.ax_xy.grid(True)

        # 3D trajectory
        self.ax_xyz = self.fig.add_subplot(gs[2, 1], projection='3d')
        self.ax_xyz.set_title('XYZ Trajectory')
        self.ax_xyz.set_xlabel('X (mm)')
        self.ax_xyz.set_ylabel('Y (mm)')
        self.ax_xyz.set_zlabel('Z (mm)')
        self.line_xyz_cmd, = self.ax_xyz.plot([], [], [], 'b-', alpha=0.5)
        self.line_xyz_fb, = self.ax_xyz.plot([], [], [], 'r-', alpha=0.7)

        # Stats in bottom-right
        self.ax_stats = self.fig.add_subplot(gs[2, 2])
        self.ax_stats.axis('off')
        self.stats_text = self.ax_stats.text(0.0, 1.0, '', transform=self.ax_stats.transAxes,
                                             fontsize=11, verticalalignment='top', fontfamily='monospace')

        plt.tight_layout()

    def get_hal_value(self, pin):
        try:
            result = subprocess.run(['halcmd', 'getp', pin], capture_output=True, text=True, timeout=0.1)
            return float(result.stdout.strip())
        except:
            return 0.0

    def update(self, frame):
        current_time = time.time() - self.start_time

        # HAL pins
        x_cmd = self.get_hal_value('joint.0.motor-pos-cmd')
        x_fb  = self.get_hal_value('joint.0.motor-pos-fb')
        x_err = self.get_hal_value('joint.0.f-error') * 1000

        y_cmd = self.get_hal_value('joint.1.motor-pos-cmd')
        y_fb  = self.get_hal_value('joint.1.motor-pos-fb')
        y_err = self.get_hal_value('joint.1.f-error') * 1000

        z_cmd = self.get_hal_value('joint.2.motor-pos-cmd')
        z_fb  = self.get_hal_value('joint.2.motor-pos-fb')
        z_err = self.get_hal_value('joint.2.f-error') * 1000

        # Append data
        self.time_data.append(current_time)
        self.x_cmd.append(x_cmd); self.x_fb.append(x_fb); self.x_err.append(x_err)
        self.y_cmd.append(y_cmd); self.y_fb.append(y_fb); self.y_err.append(y_err)
        self.z_cmd.append(z_cmd); self.z_fb.append(z_fb); self.z_err.append(z_err)

        t = np.array(self.time_data)

        # Update position plots
        self.line_x_cmd.set_data(t, self.x_cmd); self.line_x_fb.set_data(t, self.x_fb)
        self.ax_x_pos.relim(); self.ax_x_pos.autoscale_view()

        self.line_y_cmd.set_data(t, self.y_cmd); self.line_y_fb.set_data(t, self.y_fb)
        self.ax_y_pos.relim(); self.ax_y_pos.autoscale_view()

        self.line_z_cmd.set_data(t, self.z_cmd); self.line_z_fb.set_data(t, self.z_fb)
        self.ax_z_pos.relim(); self.ax_z_pos.autoscale_view()

        # Update error plots
        self.line_x_err.set_data(t, self.x_err); self.ax_x_err.relim(); self.ax_x_err.autoscale_view()
        self.line_y_err.set_data(t, self.y_err); self.ax_y_err.relim(); self.ax_y_err.autoscale_view()
        self.line_z_err.set_data(t, self.z_err); self.ax_z_err.relim(); self.ax_z_err.autoscale_view()

        # XY trajectory
        self.line_xy_cmd.set_data(self.x_cmd, self.y_cmd)
        self.line_xy_fb.set_data(self.x_fb, self.y_fb)
        self.ax_xy.relim(); self.ax_xy.autoscale_view()

        # 3D trajectory
        self.line_xyz_cmd.set_data_3d(self.x_cmd, self.y_cmd, self.z_cmd)
        self.line_xyz_fb.set_data_3d(self.x_fb, self.y_fb, self.z_fb)

        # Adjust limits dynamically
        if len(self.x_cmd) > 1:
            self.ax_xyz.set_xlim(min(self.x_cmd), max(self.x_cmd))
            self.ax_xyz.set_ylim(min(self.y_cmd), max(self.y_cmd))
            self.ax_xyz.set_zlim(min(self.z_cmd), max(self.z_cmd))

        # Stats
        if len(self.x_err) > 10:
            stats = (
                f"X Err: Cur {x_err:+.1f} Min {min(self.x_err):+.1f} Max {max(self.x_err):+.1f} RMS {np.sqrt(np.mean(np.array(self.x_err)**2)):.1f}\n"
                f"Y Err: Cur {y_err:+.1f} Min {min(self.y_err):+.1f} Max {max(self.y_err):+.1f} RMS {np.sqrt(np.mean(np.array(self.y_err)**2)):.1f}\n"
                f"Z Err: Cur {z_err:+.1f} Min {min(self.z_err):+.1f} Max {max(self.z_err):+.1f} RMS {np.sqrt(np.mean(np.array(self.z_err)**2)):.1f}"
            )
            self.stats_text.set_text(stats)

        return (self.line_x_cmd, self.line_x_fb, self.line_y_cmd, self.line_y_fb,
                self.line_z_cmd, self.line_z_fb, self.line_x_err, self.line_y_err,
                self.line_z_err, self.line_xy_cmd, self.line_xy_fb,
                self.line_xyz_cmd, self.line_xyz_fb, self.stats_text)

    def run(self):
        self.anim = FuncAnimation(self.fig, self.update, interval=UPDATE_INTERVAL, blit=False, cache_frame_data=False)
        plt.show()

def main():
    print("Starting Real-Time Position Plotter with Z-axis and 3D trajectory...")
    plotter = RealtimePlotter()
    plotter.run()

if __name__ == '__main__':
    main()
