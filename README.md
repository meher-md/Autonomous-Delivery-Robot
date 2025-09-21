# Autonomous Delivery Robot  

An **Autonomous Delivery Robot** built with **ROS 2 Humble** and **Gazebo (gz sim)** using the **Andino robot** as a base platform.  
The robot integrates multiple sensors and AI modules to perform **navigation, package delivery, and autonomous decision making**.  

---

## 📌 Overview  
This project extends the Andino robot simulation with additional sensors and AI modules to create a **Delivery Robot** that can:  
- Navigate autonomously using **Nav2**.  
- Use a generic **YOLO model + QR code detection** to identify and validate recipient barcodes.  
- Use **OCR** to read door numbers and confirm delivery location.  
- Employ **ultrasonic sensors + lidar + IMU** for obstacle detection and motion tracking.  
- Monitor **battery level** and autonomously navigate to a charging station when low.  

---

## 🚀 Features  
- **Navigation**: Full ROS 2 Nav2 stack integration.  
- **Perception**:  
  - YOLO model for object & QR detection.  
  - OCR model for reading text/numbers on doors.  
- **Sensors**:  
  - Lidar & Ultrasonic sensors for obstacle avoidance.  
  - IMU for odometry and movement accuracy.  
- **Energy Management**:  
  - Battery monitoring system.  
  - Auto-docking at charging point.  
- **Gazebo Simulation**:  
  - Andino robot base.  
  - Extended URDF with custom sensors.  
- **ROS–Gazebo Bridge** (`ros_gz_bridge`).  

---

## 📂 Project Structure  
```bash
ws/
 ├── src/                     # ROS 2 packages
 │   ├── andino_description    # Robot description (URDF/Xacro)
 │   ├── andino_gz             # Gazebo simulation
 │   ├── delivery_ai           # YOLO + QR + OCR modules
 │   ├── navigation_configs    # Nav2 setup
 │   └── battery_manager       # Battery monitoring node
 ├── build/                    # (ignored)
 ├── install/                  # (ignored)
 ├── log/                      # (ignored)
 ├── README.md
 ├── LICENSE
 └── requirements.txt


## 🖥️ Requirements  

- **OS**: Ubuntu 22.04 (Jammy)  
- **ROS 2**: Humble Hawksbill  
- **Gazebo**: Fortress or Garden  

Install ROS 2 and Gazebo packages first:  
```bash
sudo apt update
sudo apt install ros-humble-desktop
sudo apt install ros-humble-ros-gz ros-humble-rqt ros-humble-rqt-plot ros-humble-plotjuggler-ros
