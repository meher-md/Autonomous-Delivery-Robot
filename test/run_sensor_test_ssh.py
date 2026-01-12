
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
        
        print("Checking for Serial Ports...")
        stdin, stdout, stderr = client.exec_command("ls -l /dev/ttyACM* /dev/ttyUSB*")
        print(stdout.read().decode())
        print(stderr.read().decode())

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
