
import paramiko

HOSTNAME = '192.168.79.13'
USERNAME = 'pi'
PASSWORD = 'admin'
PORT = 22

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"Connecting to {HOSTNAME}...")
        client.connect(HOSTNAME, PORT, USERNAME, PASSWORD, timeout=10)
        
        print("Checking USB Bus (lsusb)...")
        stdin, stdout, stderr = client.exec_command("lsusb")
        print(stdout.read().decode())
        
        print("Checking Kernel Logs for USB Events...")
        # Check for any USB attach/detach events
        stdin, stdout, stderr = client.exec_command("dmesg | grep -i usb | tail -n 20")
        print(stdout.read().decode())
        
        print("Checking for Configured Device /dev/ttyUSB_ARDUINO...")
        stdin, stdout, stderr = client.exec_command("ls -l /dev/ttyUSB_ARDUINO")
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        print("Checking for ALL Serial Ports (USB & UART)...")
        # Check /dev/ttyACM*, /dev/ttyUSB*, AND /dev/ttyAMA* (UART)
        stdin, stdout, stderr = client.exec_command("ls -l /dev/ttyACM* /dev/ttyUSB* /dev/ttyAMA* /dev/serial*")
        print(stdout.read().decode())

        print("Stopping ROS (if running) to free Serial Port...")
        client.exec_command("pkill -9 -f component_container_mt")
        client.exec_command("pkill -F /tmp/to_kill.pid") 
        # Just generic kill
        client.exec_command("pkill -f andino_bringup")
        
        print("Running sensor test on Pi...")
        # Run unbuffered python to see output immediately
        stdin, stdout, stderr = client.exec_command("python3 -u ~/ws/test_sensor_pi.py")
        
        # Stream output
        try:
            for line in iter(stdout.readline, ""):
                print(line, end="")
        except KeyboardInterrupt:
            print("Stopping...")
            
    except Exception as e:
        print(f"Failed: {e}")
    finally:
        client.close()

if __name__ == '__main__':
    main()
