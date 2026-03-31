Terminal Allergy Project 🤧 (V2)
โปรแกรม GUI สำหรับควบคุมระบบ LiDAR SLAM และประมวลผล Point Cloud (PCD) แบบครบวงจร พัฒนาด้วย Python และ ROS 2 Jazzy

โปรเจกต์นี้ใช้โครงสร้างแบบ Hybrid Workspace คือแยกส่วน Backend (ROS 2 Packages สำหรับ SLAM และ Drivers ของเซนเซอร์) และ Frontend (Python GUI) ออกจากกันเพื่อความยืดหยุ่นในการพัฒนา

📂 โครงสร้างโปรเจกต์ (Project Structure)
Plaintext
```
terminal_Allergy_project/
├── gui_app/                 # Frontend: โค้ดโปรแกรม Python GUI หลัก
│   ├── main.py              # ไฟล์รันโปรแกรมหลัก
│   └── requirements.txt     # รายชื่อ Library Python ที่ต้องใช้
├── ros2_ws/                 # Backend: ROS 2 Workspace (เก็บ Source Code SLAM และ Drivers)
│   ├── src/
│   │   ├── lidarslam_ros2/  # ระบบทำแผนที่ (SLAM)
│   │   ├── velodyne/        # Driver สำหรับ LiDAR VLP-16
│   │   └── witmotion_ros2/  # Driver สำหรับ IMU Witmotion
└── venv/                    # Environment: (สร้างเองตอนติดตั้ง) สำหรับเก็บ Library Python แยก

```
✅ สิ่งที่ต้องมี (Prerequisites)

OS: Ubuntu 24.04 LTS (Noble Numbat)

ROS Version: ROS 2 Jazzy Jalisco

Python: 3.12 ขึ้นไป

Hardware: Velodyne VLP-16, Witmotion IMU

🚀 การติดตั้ง (Installation)
ทำตามขั้นตอนทีละสเต็ป เพื่อเตรียมระบบให้พร้อมใช้งานตั้งแต่เริ่มต้น

1. ดาวน์โหลดโปรเจกต์ (Clone Repository)
```
git clone https://github.com/supawitnonsena-noob/terminal_Allergy_project.git
cd terminal_Allergy_project

```
2. ติดตั้งระบบหลังบ้าน (Setup Backend - ROS 2)
ขั้นตอนนี้จะติดตั้งไลบรารีที่จำเป็นสำหรับเซนเซอร์และ Build ระบบ SLAM ให้พร้อมใช้งาน

Bash

# 2.1 ติดตั้งไลบรารีระบบที่จำเป็น (สำหรับ IMU และ Venv)
```
sudo apt update
sudo apt install -y python3-venv libasio-dev

```
# 2.2 โหลด Environment ของ ROS 2
```

source /opt/ros/jazzy/setup.bash

```

# 2.3 ติดตั้ง ROS Dependencies
```

cd ~/terminal_Allergy_project/ros2_ws
rosdep install --from-paths src --ignore-src -r -y

```

# 2.4 Build Workspace (อาจใช้เวลาสักพัก)
```

colcon build --symlink-install

```
3. ติดตั้งสภาพแวดล้อม Python (Setup Frontend Environment)
เราจะสร้าง Virtual Environment (venv) เพื่อลง Library เสริมสำหรับ GUI โดยเปิดโหมดให้มองเห็น ROS 2 ได้ด้วย

Bash

# 3.1 กลับมาที่โฟลเดอร์โปรเจกต์หลัก
```

cd ~/terminal_Allergy_project

```
# 3.2 สร้าง venv (สำคัญมาก: ต้องมี --system-site-packages เพื่อให้เห็น rclpy ของ ROS 2)
```

python3 -m venv venv --system-site-packages

```
# 3.3 เปิดใช้งาน venv
```
source venv/bin/activate

```
# 3.4 ติดตั้ง Library ที่โค้ด GUI ต้องใช้
```

pip install numpy open3d matplotlib Pillow

```
# หรือถ้ามีไฟล์ requirements.txt: pip install -r gui_app/requirements.txt
(หมายเหตุ: แนะนำให้ตั้งค่า Udev Rules สำหรับเซนเซอร์ IMU ให้ผูกกับพอร์ต /dev/imu เสมอ เพื่อป้องกันปัญหาพอร์ต USB สลับตำแหน่งเมื่อรีสตาร์ทเครื่อง)

🎮 วิธีการใช้งาน (How to Run)
ทุกครั้งที่จะใช้งานโปรแกรม ให้เปิด Terminal ใหม่และรันคำสั่งตามลำดับนี้:

1. เข้าสู่โฟลเดอร์โปรเจกต์
```

cd ~/terminal_Allergy_project

```
2. โหลดระบบ ROS 2 Backend (เพื่อให้รู้จัก SLAM และ Drivers)
```

source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash

```
3. โหลด Python Environment (เพื่อให้รู้จัก Open3D, Matplotlib)
```

source venv/bin/activate

```
4. รันโปรแกรม GUI
```
python3 gui_app/main.py

```

วีดีโอสอนติดตั้ง
https://youtu.be/Q8vRc2G-AHU?si=CxiIC53zqH7QBB86
