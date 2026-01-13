import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import open3d as o3d
import numpy as np
import copy
import threading
import os
import signal
import subprocess
import time
from datetime import datetime
from PIL import Image, ImageTk

# --- ROS 2 Imports (Try/Except เพื่อกัน Error ถ้ารันนอก ROS environment) ---
HAS_ROS = False
try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import PointCloud2, Imu
    HAS_ROS = True
except ImportError:
    print("Warning: 'rclpy' or 'sensor_msgs' not found. Sensor Monitor will be disabled.")

# ตรวจสอบ matplotlib
try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# ================= CLASS: SENSOR MONITOR (Logic) =================
if HAS_ROS:
    class SensorMonitorNode(Node):
        def __init__(self, callback_func):
            super().__init__('sensor_monitor_node')
            self.gui_callback = callback_func
            self.lidar_count = 0
            self.imu_count = 0
            
            # --- Config ---
            self.target_lidar_hz = 10.0
            self.target_imu_hz = 50.0
            self.tolerance = 0.2

            # Subscribers
            self.create_subscription(PointCloud2, '/velodyne_points', self.lidar_cb, 10)
            self.create_subscription(Imu, '/imu/data', self.imu_cb, 10)
            
            # Timer 1 sec
            self.create_timer(1.0, self.calculate_hz)

        def lidar_cb(self, msg): self.lidar_count += 1
        def imu_cb(self, msg): self.imu_count += 1

        def calculate_hz(self):
            l_hz = self.lidar_count
            i_hz = self.imu_count
            self.lidar_count = 0
            self.imu_count = 0
            
            l_status = "LOW" if l_hz < (self.target_lidar_hz * (1 - self.tolerance)) else "OK"
            i_status = "LOW" if i_hz < (self.target_imu_hz * (1 - self.tolerance)) else "OK"
            
            # ส่งค่ากลับไปที่ GUI Thread (ผ่าน MonitorThread)
            self.gui_callback(l_hz, l_status, i_hz, i_status)

    class MonitorThread(threading.Thread):
        def __init__(self, callback_func):
            super().__init__()
            self.callback = callback_func
            self._stop_event = threading.Event()
            self.node = None

        def run(self):
            if not rclpy.ok(): rclpy.init()
            self.node = SensorMonitorNode(self.callback)
            while not self._stop_event.is_set() and rclpy.ok():
                rclpy.spin_once(self.node, timeout_sec=0.1)
            
            self.node.destroy_node()
            if rclpy.ok(): rclpy.shutdown()

        def stop(self):
            self._stop_event.set()

# ================= CLASS 1: ROS 2 RECORDER (Tab 1) =================
class ROS2RecorderPanel:
    def __init__(self, parent):
        self.parent_frame = parent
        self.frame = tk.Frame(parent)
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.processes = {} 
        self.monitor_thread = None
        
        # --- UI Group 1: Hardware ---
        lb_hw = tk.LabelFrame(self.frame, text="1. Hardware Control", font=("Arial", 10, "bold"), fg="blue")
        lb_hw.pack(fill="x", pady=5)
        
        self.btn_lidar = self.create_toggle_btn(lb_hw, "Start LiDAR (VLP16)", self.toggle_lidar)
        self.btn_imu = self.create_toggle_btn(lb_hw, "Start IMU (Witmotion)", self.toggle_imu)
        self.btn_tf = self.create_toggle_btn(lb_hw, "Start TF (Static)", self.toggle_tf)
        
        # เพิ่ม Label แสดงสถานะ Hz
        self.lbl_sensor_health = tk.Label(lb_hw, text="Sensor Health: Waiting for data...", font=("Consolas", 9), fg="gray")
        self.lbl_sensor_health.pack(side="bottom", anchor="w", padx=10, pady=2)
        
        # Start Monitor Thread
        if HAS_ROS:
            self.start_monitor()
        else:
            self.lbl_sensor_health.config(text="Sensor Monitor: Disabled (No ROS)", fg="red")

        # --- UI Group 2: Visualization ---
        lb_viz = tk.LabelFrame(self.frame, text="2. Visualization", font=("Arial", 10, "bold"))
        lb_viz.pack(fill="x", pady=5)
        self.btn_rviz = self.create_toggle_btn(lb_viz, "Open RViz2", self.toggle_rviz)

        # --- UI Group 3: Recording ---
        lb_rec = tk.LabelFrame(self.frame, text="3. Data Recording", font=("Arial", 10, "bold"), fg="red")
        lb_rec.pack(fill="x", pady=5)
        
        tk.Label(lb_rec, text="Bag Name:").pack(side="left", padx=5)
        self.bag_name = tk.StringVar(value="my_scan_data")
        tk.Entry(lb_rec, textvariable=self.bag_name, width=20).pack(side="left", padx=5)
        
        self.btn_record = tk.Button(lb_rec, text="⚫ Start Recording", bg="#ffcccb", command=self.toggle_record)
        self.btn_record.pack(side="left", padx=10, fill="x", expand=True)
        self.lbl_rec_status = tk.Label(lb_rec, text="Status: Idle", fg="gray")
        self.lbl_rec_status.pack(side="right", padx=10)

        # --- UI Group 4: Log ---
        lb_log = tk.LabelFrame(self.frame, text="Terminal Log")
        lb_log.pack(fill="both", expand=True, pady=5)
        self.log_area = scrolledtext.ScrolledText(lb_log, height=8, bg="black", fg="#00ff00", font=("Consolas", 9))
        self.log_area.pack(fill="both", expand=True)

    def start_monitor(self):
        self.monitor_thread = MonitorThread(self.on_sensor_update)
        self.monitor_thread.start()

    def on_sensor_update(self, l_hz, l_status, i_hz, i_status):
        # ใช้ after เพื่อ update GUI บน Main Thread อย่างปลอดภัย
        self.frame.after(0, lambda: self._update_ui_health(l_hz, l_status, i_hz, i_status))

    def _update_ui_health(self, l_hz, l_status, i_hz, i_status):
        text = f"Lidar: {l_hz}Hz | IMU: {i_hz}Hz"
        
        # Check logic
        is_bad = False
        if l_status == "LOW" and l_hz > 0: # >0 เพื่อกันตอนเพิ่งเริ่ม
            text += " ⚠️ LIDAR LOW!"
            is_bad = True
        if i_status == "LOW" and i_hz > 0:
            text += " ⚠️ IMU LOW!"
            is_bad = True
            
        if is_bad:
            self.lbl_sensor_health.config(text=text, fg="red", font=("Consolas", 9, "bold"))
            # แจ้งลง Log ด้วย
            self.log(f"WARNING: Sensor Lag! L={l_hz}Hz, I={i_hz}Hz")
        else:
            self.lbl_sensor_health.config(text=text, fg="green", font=("Consolas", 9))

    def create_toggle_btn(self, parent, text, cmd):
        btn = tk.Button(parent, text="▶ " + text, bg="#e0e0e0", command=cmd, width=30, anchor="w")
        btn.pack(pady=2, padx=5, fill="x")
        return btn

    def log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_area.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_area.see(tk.END)

    def run_cmd(self, key, cmd_str, btn_widget):
        if key in self.processes:
            self.stop_cmd(key, btn_widget)
            return

        self.log(f"Starting {key}...")
        try:
            proc = subprocess.Popen(f"bash -c '{cmd_str}'", shell=True, preexec_fn=os.setsid)
            self.processes[key] = proc
            btn_widget.config(text=f"⏹ Stop {key}", bg="#81c784")
        except Exception as e:
            self.log(f"Error: {e}")

    def stop_cmd(self, key, btn_widget):
        if key in self.processes:
            self.log(f"Stopping {key}...")
            proc = self.processes[key]
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGINT)
                try:
                    proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired: 
                    self.log(f"{key} did not stop gracefully. Force killing...")
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    
            except Exception as e:
                self.log(f"Error stopping {key}: {e}")
            
            del self.processes[key]
            original_text = btn_widget.cget("text").replace("⏹ Stop ", "")
            btn_widget.config(text=f"▶ Start {original_text}", bg="#e0e0e0")
    def toggle_lidar(self):
        cmd = "source /opt/ros/jazzy/setup.bash && ros2 launch velodyne velodyne-all-nodes-VLP16-launch.py"
        self.run_cmd("LiDAR", cmd, self.btn_lidar)

    def toggle_imu(self):
        launch_path = f"{os.path.expanduser('~')}/imu_system.launch.py"
        if not os.path.exists(launch_path):
            self.log(f"Error: Launch file not found at {launch_path}")
            return
        cmd = f"source ~/ros2_ws/install/setup.bash && ros2 launch {launch_path}"
        self.run_cmd("IMU", cmd, self.btn_imu)

    def toggle_tf(self):
        cmd = "source /opt/ros/jazzy/setup.bash && ros2 run tf2_ros static_transform_publisher --x 0 --y 0 --z 1.36 --yaw 0 --pitch 0 --roll 0 --frame-id base_link --child-frame-id velodyne & ros2 run tf2_ros static_transform_publisher --x 0 --y 0.04 --z 0.96 --yaw 0 --pitch 0 --roll 0 --frame-id base_link --child-frame-id imu_link"
        self.run_cmd("TF", cmd, self.btn_tf)

    def toggle_rviz(self):
        cmd = "source /opt/ros/jazzy/setup.bash && ros2 run rviz2 rviz2"
        self.run_cmd("RViz", cmd, self.btn_rviz)

    def toggle_record(self):
        key = "Recorder"
        if key in self.processes:
            self.stop_cmd(key, self.btn_record)
            self.btn_record.config(text="⚫ Start Recording", bg="#ffcccb")
            self.lbl_rec_status.config(text="Status: Saved", fg="blue")
        else:
            name = self.bag_name.get().strip()
            if not name: name = "rec_data"
            save_path = os.path.expanduser("~/lidsrT1/bagfiles/")
            os.makedirs(save_path, exist_ok=True)
            full_name = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            cmd = f"source /opt/ros/jazzy/setup.bash && cd {save_path} && ros2 bag record -o {full_name} -a"
            self.log(f"Recording: {full_name}")
            
            proc = subprocess.Popen(f"bash -c '{cmd}'", shell=True, preexec_fn=os.setsid)
            self.processes[key] = proc
            
            self.btn_record.config(text="⏹ Stop Recording", bg="red", fg="white")
            self.lbl_rec_status.config(text="Status: 🔴 RECORDING...", fg="red")
            
    def cleanup(self):
        # ฟังก์ชันปิด Thread เมื่อปิดโปรแกรม
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread.join()

# ================= CLASS 2: MANUAL TRANSFORM TOOL =================
class ManualTransformTool:
    def __init__(self, master_root, pcd, on_confirm_callback):
        self.master_root = master_root
        self.original_pcd = copy.deepcopy(pcd)
        self.temp_pcd = copy.deepcopy(pcd)
        self.on_confirm = on_confirm_callback
        
        self.window = tk.Toplevel(master_root)
        self.window.title("Step 3: Manual Transform")
        self.window.geometry("400x650")
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.rot_x = tk.DoubleVar(value=0.0); self.rot_y = tk.DoubleVar(value=0.0); self.rot_z = tk.DoubleVar(value=0.0)
        self.trans_x = tk.DoubleVar(value=0.0); self.trans_y = tk.DoubleVar(value=0.0); self.trans_z = tk.DoubleVar(value=0.0)
        self.show_box = tk.BooleanVar(value=True)
        
        self.create_ui()
        self.needs_update = True
        
        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window(window_name="Preview Transform", width=800, height=600)
        self.vis.add_geometry(self.temp_pcd)
        self.axis = o3d.geometry.TriangleMesh.create_coordinate_frame(size=2.0, origin=[0, 0, 0])
        self.vis.add_geometry(self.axis)
        self.current_bbox = o3d.geometry.LineSet()
        self.vis.add_geometry(self.current_bbox)
        self.running = True
        self.run_vis_loop()

    def create_ui(self):
        lf_rot = tk.LabelFrame(self.window, text="Rotation", padx=5, pady=5, fg="blue")
        lf_rot.pack(fill="x", padx=10, pady=5)
        self.add_slider(lf_rot, "Roll (X)", self.rot_x, -180, 180)
        self.add_slider(lf_rot, "Pitch (Y)", self.rot_y, -180, 180)
        self.add_slider(lf_rot, "Yaw (Z)", self.rot_z, -180, 180)
        lf_trans = tk.LabelFrame(self.window, text="Translation", padx=5, pady=5, fg="green")
        lf_trans.pack(fill="x", padx=10, pady=5)
        self.add_slider(lf_trans, "X", self.trans_x, -50, 50)
        self.add_slider(lf_trans, "Y", self.trans_y, -50, 50)
        self.add_slider(lf_trans, "Z", self.trans_z, -50, 50)
        tk.Checkbutton(self.window, text="Show Yellow Box", variable=self.show_box, command=self.flag_update).pack()
        btn_frame = tk.Frame(self.window, pady=10)
        btn_frame.pack(fill="x")
        tk.Button(btn_frame, text="Reset", command=self.reset_values, bg="orange").pack(side="left", padx=10, expand=True)
        tk.Button(btn_frame, text="✅ Confirm", command=self.apply_and_close, bg="green", fg="white").pack(side="right", padx=10, expand=True)

    def add_slider(self, parent, label, var, min_val, max_val):
        frame = tk.Frame(parent); frame.pack(fill="x")
        tk.Label(frame, text=label, width=8, anchor="w").pack(side="left")
        tk.Scale(frame, variable=var, from_=min_val, to=max_val, orient="horizontal", resolution=0.1, command=lambda x: self.flag_update()).pack(side="left", fill="x", expand=True)

    def flag_update(self): self.needs_update = True
    def get_transform_matrix(self):
        rx, ry, rz = np.deg2rad(self.rot_x.get()), np.deg2rad(self.rot_y.get()), np.deg2rad(self.rot_z.get())
        R = o3d.geometry.get_rotation_matrix_from_xyz((rx, ry, rz))
        T = np.array([self.trans_x.get(), self.trans_y.get(), self.trans_z.get()])
        mat = np.eye(4); mat[:3, :3] = R; mat[:3, 3] = T
        return mat
    def run_vis_loop(self):
        if not self.running: return
        try:
            if not self.vis.poll_events(): self.running = False; self.window.destroy(); return
        except: return
        if self.needs_update:
            trans_mat = self.get_transform_matrix()
            self.temp_pcd.points = self.original_pcd.points
            self.temp_pcd.colors = self.original_pcd.colors
            self.temp_pcd.transform(trans_mat)
            self.vis.update_geometry(self.temp_pcd)
            self.vis.remove_geometry(self.current_bbox, reset_bounding_box=False)
            if self.show_box.get():
                bbox = self.temp_pcd.get_axis_aligned_bounding_box()
                bbox.color = (1, 1, 0)
                self.current_bbox = bbox
                self.vis.add_geometry(self.current_bbox, reset_bounding_box=False)
            self.needs_update = False 
        self.vis.update_renderer()
        self.window.after(20, self.run_vis_loop)
    def reset_values(self):
        for v in [self.rot_x, self.rot_y, self.rot_z, self.trans_x, self.trans_y, self.trans_z]: v.set(0.0)
        self.flag_update()
    def apply_and_close(self): self.running = False; self.vis.destroy_window(); self.window.destroy(); self.on_confirm(self.temp_pcd)
    def on_close(self): self.running = False; self.vis.destroy_window(); self.window.destroy()

# ================= CLASS 3: PROCESSOR PANEL =================
class PCDProcessorPanel:
    def __init__(self, parent, root_tk):
        self.frame = tk.Frame(parent)
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.root = root_tk
        
        # ตัวแปร State
        self.input_path = tk.StringVar()
        self.output_base = tk.StringVar()
        self.manual_transformed_pcd = None 
        self.current_processed_pcd = None
        self.pcd_original = None # เก็บค่า Original ไว้สำหรับกดปุ่ม Test
        
        self.save_pcd = tk.BooleanVar(value=True)
        self.save_map = tk.BooleanVar(value=True)

        # --- 1. File Selection ---
        f1 = tk.LabelFrame(self.frame, text="1. File Selection", padx=10, pady=5, font=("Arial", 10, "bold"))
        f1.pack(fill="x", pady=5)
        tk.Label(f1, text="Input PCD:").grid(row=0, column=0, sticky="w")
        tk.Entry(f1, textvariable=self.input_path, width=40).grid(row=0, column=1, padx=5)
        tk.Button(f1, text="Browse...", command=self.browse_input).grid(row=0, column=2)
        tk.Button(f1, text="👁 View", command=self.view_input).grid(row=0, column=3, padx=2)
        tk.Label(f1, text="Output Name:").grid(row=1, column=0, sticky="w")
        tk.Entry(f1, textvariable=self.output_base, width=40).grid(row=1, column=1, padx=5)
        tk.Label(f1, text="(no ext)").grid(row=1, column=2, sticky="w")

        # --- 2. Denoise ---
        f2 = tk.LabelFrame(self.frame, text="2. Denoise Settings", padx=10, pady=5, font=("Arial", 10, "bold"))
        f2.pack(fill="x", pady=5)
        tk.Label(f2, text="Neighbors (nb):").grid(row=0, column=0, sticky="w")
        self.nb_neighbors = tk.IntVar(value=50)
        tk.Entry(f2, textvariable=self.nb_neighbors, width=8).grid(row=0, column=1, sticky="w")
        tk.Label(f2, text="Std Ratio:").grid(row=0, column=2, sticky="w", padx=10)
        self.std_ratio = tk.DoubleVar(value=1.0)
        tk.Entry(f2, textvariable=self.std_ratio, width=8).grid(row=0, column=3, sticky="w")
        
        # เพิ่มปุ่ม Test Denoise กลับมา
        self.btn_test_denoise = tk.Button(f2, text="▶ Test Denoise", bg="#bbdefb", command=self.run_test_denoise)
        self.btn_test_denoise.grid(row=0, column=4, padx=10)

        # --- 3. Manual Transform ---
        f3 = tk.LabelFrame(self.frame, text="3. Manual Transformation", padx=10, pady=5, font=("Arial", 10, "bold"), fg="blue")
        f3.pack(fill="x", pady=5)
        self.btn_transform = tk.Button(f3, text="🛠 Open Manual Transform Tool", command=self.open_manual_transform, state="disabled")
        self.btn_transform.pack(fill="x", pady=5)
        self.lbl_transform_status = tk.Label(f3, text="Status: Using Original Position", fg="gray")
        self.lbl_transform_status.pack()

        # --- 4. Map Gen ---
        f4 = tk.LabelFrame(self.frame, text="4. Map Generation (2D Slice)", padx=10, pady=5, font=("Arial", 10, "bold"), fg="darkred")
        f4.pack(fill="x", pady=5)
        tk.Label(f4, text="Min Z (Cut Floor):").grid(row=0, column=0, sticky="w")
        self.min_z = tk.DoubleVar(value=0.2)
        tk.Entry(f4, textvariable=self.min_z, width=10).grid(row=0, column=1, sticky="w")
        tk.Label(f4, text="Max Z (Cut Ceiling):").grid(row=0, column=2, sticky="w", padx=10)
        self.max_z = tk.DoubleVar(value=1.5)
        tk.Entry(f4, textvariable=self.max_z, width=10).grid(row=0, column=3, sticky="w")
        tk.Label(f4, text="Resolution (m/px):").grid(row=1, column=0, sticky="w")
        self.map_res = tk.DoubleVar(value=0.05)
        tk.Entry(f4, textvariable=self.map_res, width=10).grid(row=1, column=1, sticky="w")

        # --- 5. Analysis ---
        f5 = tk.LabelFrame(self.frame, text="5. Analysis", padx=10, pady=5, font=("Arial", 10, "bold"), fg="purple")
        f5.pack(fill="x", pady=5)
        self.btn_analyze = tk.Button(f5, text="📊 Analyze Wall Statistics", command=self.run_wall_analysis, state="disabled")
        self.btn_analyze.pack(fill="x", pady=5)

        # --- Save & Run ---
        action_frame = tk.Frame(self.frame, pady=5)
        action_frame.pack(fill="x", padx=10)
        out_opts = tk.Frame(action_frame)
        out_opts.pack(side="top", fill="x", pady=(0,5))
        tk.Checkbutton(out_opts, text="Save .pcd", variable=self.save_pcd).pack(side="left")
        tk.Checkbutton(out_opts, text="Save .pgm/.yaml", variable=self.save_map).pack(side="left", padx=10)

        self.btn_process = tk.Button(action_frame, text="🚀 START PROCESSING", bg="green", fg="white", font=("Arial", 12, "bold"), command=self.start_processing_thread)
        self.btn_process.pack(fill="x", expand=True)
        self.btn_view_result = tk.Button(action_frame, text="👁 View Result (3D)", state="disabled", font=("Arial", 10), command=self.view_result)
        self.btn_view_result.pack(fill="x", pady=(5,0))

        # --- Log ---
        self.log_area = scrolledtext.ScrolledText(self.frame, height=8, state='disabled')
        self.log_area.pack(fill="both", expand=True, padx=10, pady=5)

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def browse_input(self):
        filename = filedialog.askopenfilename(filetypes=[("PCD Files", "*.pcd *.ply *.xyz")])
        if filename:
            self.input_path.set(filename)
            base = os.path.splitext(filename)[0] + "_processed"
            self.output_base.set(base)
            
            # Reset UI
            self.btn_analyze.config(state="disabled")
            self.btn_transform.config(state="normal")
            self.manual_transformed_pcd = None 
            self.lbl_transform_status.config(text="Status: Using Original Position", fg="gray")
            
            # Load into memory for Test Denoise to work
            self.log(f"Loading: {os.path.basename(filename)}")
            self.pcd_original = o3d.io.read_point_cloud(filename)

    def create_yellow_box(self, pcd):
        bbox = pcd.get_axis_aligned_bounding_box()
        bbox.color = (1, 1, 0)
        return bbox

    def view_input(self):
        path = self.input_path.get()
        if path and os.path.exists(path):
            pcd = o3d.io.read_point_cloud(path)
            bbox = self.create_yellow_box(pcd)
            o3d.visualization.draw_geometries([pcd, bbox], window_name="Input View")

    def run_test_denoise(self):
        if not self.pcd_original: 
            messagebox.showwarning("Warning", "Please select input file first")
            return
        
        self.log("Testing Denoise settings...")
        nb = self.nb_neighbors.get()
        ratio = self.std_ratio.get()
        
        # Calculate
        cl, ind = self.pcd_original.remove_statistical_outlier(nb_neighbors=nb, std_ratio=ratio)
        pcd_clean = self.pcd_original.select_by_index(ind)
        pcd_noise = self.pcd_original.select_by_index(ind, invert=True)
        
        # Paint
        pcd_clean.paint_uniform_color([0, 1, 0]) # Green = Keep
        pcd_noise.paint_uniform_color([1, 0, 0]) # Red = Remove
        
        self.log(f"Result: Removed {len(self.pcd_original.points) - len(pcd_clean.points)} points")
        self.log("Opening Preview (Green=Keep, Red=Remove)...")
        o3d.visualization.draw_geometries([pcd_clean, pcd_noise], window_name="Denoise Test")

    def open_manual_transform(self):
        input_file = self.input_path.get()
        if not input_file: return
        self.log("Opening Manual Transform Tool...")
        if self.manual_transformed_pcd:
            source_pcd = self.manual_transformed_pcd
        else:
            source_pcd = o3d.io.read_point_cloud(input_file)
        ManualTransformTool(self.root, source_pcd, self.on_transform_confirm)

    def on_transform_confirm(self, pcd):
        self.manual_transformed_pcd = pcd
        self.lbl_transform_status.config(text="Status: ✅ Manual Transform Applied", fg="green")
        self.log("Manual Transformation Applied.")

    def start_processing_thread(self):
        threading.Thread(target=self.run_process, daemon=True).start()

    def run_process(self):
        input_file = self.input_path.get()
        output_base = self.output_base.get()
        if not input_file: 
            messagebox.showwarning("Warning", "Please select input file")
            return

        self.btn_process.config(state="disabled", text="Processing...")
        self.log("-" * 40)
        try:
            # 1. Use manual transform if available, else load original
            if self.manual_transformed_pcd:
                self.log(f"Using Transformed PCD...")
                pcd = copy.deepcopy(self.manual_transformed_pcd)
            else:
                self.log(f"Loading: {os.path.basename(input_file)}")
                pcd = o3d.io.read_point_cloud(input_file)

            if not pcd.has_points(): return

            # 2. Denoise
            nb = self.nb_neighbors.get()
            ratio = self.std_ratio.get()
            self.log(f"Cleaning Noise (nb={nb}, std={ratio})...")
            cl, ind = pcd.remove_statistical_outlier(nb_neighbors=nb, std_ratio=ratio)
            pcd_clean = pcd.select_by_index(ind)
            self.log(f">> Removed {len(pcd.points) - len(pcd_clean.points)} points.")
            
            final_pcd = pcd_clean
            self.current_processed_pcd = final_pcd

            # Save
            if self.save_pcd.get():
                pcd_name = output_base + ".pcd"
                o3d.io.write_point_cloud(pcd_name, final_pcd)
                self.log(f"✅ Saved PCD: {os.path.basename(pcd_name)}")

            if self.save_map.get():
                self.log("Generating 2D Map...")
                self.generate_and_save_map(final_pcd, output_base)

            self.log("Processing Complete.")
            messagebox.showinfo("Done", "Processing Complete!")
            self.btn_view_result.config(state="normal")
            self.btn_analyze.config(state="normal")

        except Exception as e:
            self.log(f"Error: {e}")
            print(e)
        finally:
            self.btn_process.config(state="normal", text="🚀 START PROCESSING")

    def generate_and_save_map(self, pcd, base_name):
        points = np.asarray(pcd.points)
        min_z_req = self.min_z.get()
        max_z_req = self.max_z.get()
        mask = (points[:, 2] >= min_z_req) & (points[:, 2] <= max_z_req)
        sliced_points = points[mask]
        
        if len(sliced_points) == 0:
            self.log("❌ Error Map: No points in Z range!")
            return

        resolution = self.map_res.get()
        x_points = sliced_points[:, 0]
        y_points = sliced_points[:, 1]
        
        min_x, max_x = np.min(x_points), np.max(x_points)
        min_y, max_y = np.min(y_points), np.max(y_points)
        
        width = int(np.ceil((max_x - min_x) / resolution)) + 1
        height = int(np.ceil((max_y - min_y) / resolution)) + 1
        grid = np.ones((height, width), dtype=np.uint8) * 255 
        
        for x, y in zip(x_points, y_points):
            px = int((x - min_x) / resolution)
            py = int((y - min_y) / resolution)
            py = height - 1 - py 
            if 0 <= px < width and 0 <= py < height:
                grid[py, px] = 0 

        pgm_filename = base_name + ".pgm"
        Image.fromarray(grid).save(pgm_filename)
        self.log(f"✅ Saved PGM: {os.path.basename(pgm_filename)}")

        yaml_filename = base_name + ".yaml"
        yaml_content = f"image: {os.path.basename(pgm_filename)}\nresolution: {resolution}\norigin: [{min_x}, {min_y}, 0.0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n"
        with open(yaml_filename, "w") as f: f.write(yaml_content)
        self.log(f"✅ Saved YAML")

    def view_result(self):
        if self.current_processed_pcd:
             bbox = self.create_yellow_box(self.current_processed_pcd)
             o3d.visualization.draw_geometries([self.current_processed_pcd, bbox], window_name="Result View")
        else:
            messagebox.showwarning("No Result", "No result in RAM")

    def run_wall_analysis(self):
        if not HAS_MATPLOTLIB: return
        if self.current_processed_pcd is None: return
        target_pcd = self.current_processed_pcd
        self.log("Analyzing Wall Thickness...")
        
        plane_model, inliers = target_pcd.segment_plane(distance_threshold=0.01, ransac_n=3, num_iterations=2000)
        [a, b, c, d] = plane_model
        points = np.asarray(target_pcd.points)
        distances = np.abs(points @ np.array([a, b, c]) + d) / np.sqrt(a**2 + b**2 + c**2)
        
        std_dev = np.std(distances)
        p95_dist = np.percentile(distances, 95) 
        self.log(f"Stats: StdDev={std_dev*100:.2f}cm | 95%={p95_dist*2*100:.2f}cm")
        
        plt.figure(figsize=(8, 5))
        plt.hist(distances * 100, bins=50, color='skyblue', edgecolor='black', alpha=0.7)
        plt.title("Wall Thickness Distribution")
        plt.show() 
        
        inlier_cloud = target_pcd.select_by_index(inliers)
        inlier_cloud.paint_uniform_color([0, 1, 0])
        outlier_cloud = target_pcd.select_by_index(inliers, invert=True)
        outlier_cloud.paint_uniform_color([1, 0, 0])
        
        bbox = self.create_yellow_box(target_pcd)
        o3d.visualization.draw_geometries([inlier_cloud, outlier_cloud, bbox], window_name="Analysis")
    def cleanup(self):
        pass

# ================= CLASS 5: MAPPING PANEL (Tab 3) =================
# ส่วนที่เพิ่มเข้ามาใหม่สำหรับ Mapping
class MappingPanel:
    def __init__(self, parent):
        self.frame = tk.Frame(parent)
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.process = None # เก็บ Process ของ Mapping
        
        # --- UI Group 1: Mapping Control ---
        lb_map = tk.LabelFrame(self.frame, text="1. SLAM Control", font=("Arial", 10, "bold"), fg="blue")
        lb_map.pack(fill="x", pady=5)
        
        # ปุ่ม Start Mapping (Toggle แบบ Start/Stop)
        self.btn_start_map = tk.Button(lb_map, text="▶ Start Mapping (LidarSLAM)", bg="#e0e0e0", command=self.toggle_mapping, height=2)
        self.btn_start_map.pack(fill="x", padx=10, pady=5)
        
        # --- UI Group 2: Save Map ---
        lb_save = tk.LabelFrame(self.frame, text="2. Save Map", font=("Arial", 10, "bold"), fg="green")
        lb_save.pack(fill="x", pady=5)
        
        # ปุ่ม Save Map (One-shot command)
        self.btn_save_map = tk.Button(lb_save, text="💾 SAVE MAP (Service Call)", bg="#a5d6a7", command=self.save_map, height=2)
        self.btn_save_map.pack(fill="x", padx=10, pady=5)

        # --- UI Group 3: Log ---
        lb_log = tk.LabelFrame(self.frame, text="Mapping Log")
        lb_log.pack(fill="both", expand=True, pady=5)
        self.log_area = scrolledtext.ScrolledText(lb_log, height=10, bg="black", fg="#00ff00", font=("Consolas", 9))
        self.log_area.pack(fill="both", expand=True)

    def log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_area.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_area.see(tk.END)

    def toggle_mapping(self):
        # ถ้ามี Process รันอยู่ -> สั่งหยุด
        if self.process:
            self.stop_mapping()
        else:
            self.start_mapping()

    def start_mapping(self):
        # คำสั่ง Start Mapping: cd ros2_ws && source install/setup.bash && ros2 launch ...
        # ใช้ os.path.expanduser('~') เพื่อให้มั่นใจว่าหา path เจอ
        ws_path = os.path.expanduser('~/ros2_ws')
        cmd = f"cd {ws_path} && source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 launch lidarslam lidarslam.launch.py"
        
        self.log(f"Starting SLAM...")
        self.log(f"Command: {cmd}")
        
        try:
            # ใช้ setsid เพื่อให้ kill process ลูกทั้งหมดได้ง่ายๆ
            self.process = subprocess.Popen(f"bash -c '{cmd}'", shell=True, preexec_fn=os.setsid)
            
            # เปลี่ยนสีและข้อความปุ่ม
            self.btn_start_map.config(text="⏹ Stop Mapping", bg="#ffcccb", fg="red")
        except Exception as e:
            self.log(f"Error starting mapping: {e}")

    def stop_mapping(self):
        if self.process:
            self.log("Stopping SLAM...")
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGINT)
            except Exception as e:
                self.log(f"Error killing process: {e}")
            
            self.process = None
            # คืนค่าปุ่ม
            self.btn_start_map.config(text="▶ Start Mapping (LidarSLAM)", bg="#e0e0e0", fg="black")
            self.log("SLAM Stopped.")

    def save_map(self):
        # คำสั่ง Save Map (Service Call)
        # ใช้ std_srvs/srv/Empty
        cmd = "ros2 service call /map_save std_srvs/srv/Empty" 
        
        self.log(f"Calling Service: /map_save...")
        
        def run_save():
            try:
                # ต้อง source setup ก่อนเรียก service call ด้วย เพื่อความชัวร์
                full_cmd = f"bash -c 'source /opt/ros/jazzy/setup.bash && {cmd}'"
                result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    self.frame.after(0, lambda: self.log("✅ Map Saved Successfully!"))
                    self.frame.after(0, lambda: self.log(result.stdout))
                else:
                    self.frame.after(0, lambda: self.log("❌ Failed to save map."))
                    self.frame.after(0, lambda: self.log(result.stderr))
            except Exception as e:
                self.frame.after(0, lambda: self.log(f"Error: {e}"))

        # รันใน Thread แยกเพื่อไม่ให้ GUI ค้าง
        threading.Thread(target=run_save, daemon=True).start()

    def cleanup(self):
        if self.process:
            self.stop_mapping()

# ================= CLASS 4: MAIN APP (Tabs) =================
class PCDMasterApp:
    def __init__(self, root):
        self.root = root
        try:
            self.root.tk.call('wm', 'iconname', self.root._w, "TerminalAllergy")
        except: pass
        self.root.title("Terminal Allergy V2 ")
        self.root.geometry("800x1000")

        try:
            icon_path = os.path.expanduser("~/lidsrT1/app_icon.png")
            if os.path.exists(icon_path):
                self.img_icon = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, self.img_icon)
                print("Icon loaded successfully.")
            else:
                print(f"Warning: Icon file not found at {icon_path}")
        except Exception as e:
            print(f"Error loading icon: {e}")
        
        # จัดการปิดโปรแกรม
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # --- TAB System ---
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)
        
        # Tab 1: Recorder
        self.tab1 = tk.Frame(self.notebook)
        self.notebook.add(self.tab1, text="🔴 Tab 1: Data Recorder")
        self.recorder_panel = ROS2RecorderPanel(self.tab1)
        
        # Tab 2: Processor
        self.tab2 = tk.Frame(self.notebook)
        self.notebook.add(self.tab2, text="⚙️ Tab 2: Processor")
        PCDProcessorPanel(self.tab2, root)

        # Tab 3: Map (เพิ่มใหม่)
        self.tab3 = tk.Frame(self.notebook)
        self.notebook.add(self.tab3, text="🗺️ Tab 3: MAP")
        self.mapping_panel = MappingPanel(self.tab3)

    def on_close(self):
        print("Closing application...")
        
        if hasattr(self, 'mapping_panel'): 
            self.mapping_panel.cleanup()

        if hasattr(self, 'recorder_panel'):
            for key in list(self.recorder_panel.processes.keys()):
                proc = self.recorder_panel.processes[key]
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except: pass
            self.recorder_panel.cleanup()

        # 3. Shutdown ROS Cleanly
        if HAS_ROS and rclpy.ok():
            try:
                rclpy.shutdown()
            except: pass

        print("Application Closed. All nodes Cleanup.")
        

        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PCDMasterApp(root)
    root.mainloop()
