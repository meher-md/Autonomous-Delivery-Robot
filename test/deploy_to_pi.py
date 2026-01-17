#!/usr/bin/env python3
import paramiko
import os
import sys
HOSTNAME = '192.168.200.13'
USERNAME = 'pi'
PASSWORD = 'admin'
PORT = 22
FILES_TO_TRANSFER = [
    ('src/andino/andino_firmware/src/app.cpp', 'ws/src/andino/andino_firmware/src/app.cpp'),
    ('src/andino/andino_firmware/src/app.h', 'ws/src/andino/andino_firmware/src/app.h'),
    ('src/andino/andino_firmware/platformio.ini', 'ws/src/andino/andino_firmware/platformio.ini'),
    ('src/andino/andino_base/src/diffdrive_andino.cpp', 'ws/src/andino/andino_base/src/diffdrive_andino.cpp'),
    ('src/andino/andino_base/include/andino_base/wheel.h', 'ws/src/andino/andino_base/include/andino_base/wheel.h'),
    ('src/andino/andino_description/config/andino/hardware.yaml', 'ws/src/andino/andino_description/config/andino/hardware.yaml'),
    ('src/andino/andino_control/config/andino_controllers.yaml', 'ws/src/andino/andino_control/config/andino_controllers.yaml'),
    ('src/andino/andino_control/launch/andino_control.launch.py', 'ws/src/andino/andino_control/launch/andino_control.launch.py'),
    ('src/andino/andino_description/urdf/include/andino_control.urdf.xacro', 'ws/src/andino/andino_description/urdf/include/andino_control.urdf.xacro'),
    ('src/andino/andino_description/urdf/andino.urdf.xacro', 'ws/src/andino/andino_description/urdf/andino.urdf.xacro'),
    ('src/andino/andino_bringup/config/ekf.yaml', 'ws/src/andino/andino_bringup/config/ekf.yaml'),
    ('src/andino/andino_bringup/scripts/range_to_laserscan.py', 'ws/src/andino/andino_bringup/scripts/range_to_laserscan.py'),
    ('src/andino/andino_bringup/CMakeLists.txt', 'ws/src/andino/andino_bringup/CMakeLists.txt'),
    ('src/andino/andino_bringup/launch/andino_robot.launch.py', 'ws/src/andino/andino_bringup/launch/andino_robot.launch.py'),
    ('src/andino/andino_navigation/params/nav2_params.yaml', 'ws/src/andino/andino_navigation/params/nav2_params.yaml'),
    ('src/andino/andino_bringup/config/cyclonedds.xml', 'ws/src/andino/andino_bringup/config/cyclonedds.xml'),
    ('src/andino/andino_description/urdf/temp_urdf_snippet.xml', 'ws/src/andino/andino_description/urdf/temp_urdf_snippet.xml'),
]
COMMANDS_TO_RUN = [
    "source /opt/ros/humble/setup.bash && cd ~/ws && colcon build --symlink-install --cmake-clean-first --packages-select andino_base andino_control andino_description andino_bringup andino_navigation"
]
def create_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOSTNAME, PORT, USERNAME, PASSWORD, timeout=10)
        return client
    except Exception as e:
        print(f"Failed to connect: {e}")
        return None
def upload_files(sftp):
    local_base = '/home/mo/ws/'
    print("Starting file upload...")
    for local_rel, remote_rel in FILES_TO_TRANSFER:
        local_path = os.path.join(local_base, local_rel)
        remote_path = remote_rel 
        try:
            print(f"Uploading {local_rel} -> {remote_path}...")
            sftp.put(local_path, remote_path)
            print("OK")
        except Exception as e:
            print(f"Failed to upload {local_rel}: {e}")
def run_remote_commands(client):
    print("\nRunning remote commands...")
    for cmd in COMMANDS_TO_RUN:
        print(f"Executing: {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd)
        for line in iter(stdout.readline, ""):
            print(line, end="")
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            print(f"Error executing command: {cmd}")
            print(stderr.read().decode())
        else:
            print("Command Success.\n")
def main():
    client = create_ssh_client()
    if not client:
        sys.exit(1)
    client.exec_command("mkdir -p ws/src/andino/andino_bringup/scripts")
    
    # Sync time
    import time
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"Syncing remote time to: {current_time}")
    # Using sudo -S to accept password from stdin if needed, though often pi user has passwordless sudo.
    # We try both or just assume passwordless or use the password variable.
    # Safe approach: echo password | sudo -S date ...
    sync_cmd = f'echo {PASSWORD} | sudo -S date -s "{current_time}"'
    stdin, stdout, stderr = client.exec_command(sync_cmd)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status == 0:
        print("Time synced successfully.")
    else:
        print(f"Failed to sync time: {stderr.read().decode()}")

    sftp = client.open_sftp()
    upload_files(sftp)
    sftp.close()
    run_remote_commands(client)
    client.close()
    print("\nDeployment Completed.")
if __name__ == '__main__':
    main()
