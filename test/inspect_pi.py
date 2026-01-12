
import paramiko
import sys

HOSTNAME = '192.168.79.13'
USERNAME = 'pi'
PASSWORD = 'admin'
PORT = 22

def inspect_file(filepath):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOSTNAME, PORT, USERNAME, PASSWORD, timeout=10)
        
        cmd = f"cat {filepath}"
        stdin, stdout, stderr = client.exec_command(cmd)
        
        content = stdout.read().decode()
        error = stderr.read().decode()
        
        if error:
            print(f"Error reading file:\n{error}")
        else:
            print(f"--- Content of {filepath} ---")
            print(content)
            print("--- End of Content ---")
            
        client.close()

    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == '__main__':
    # Inspect the installed launch file (which is what runs)
    # Note: install/andino_control/share/andino_control/launch/andino_control.launch.py
    # But since we use symlink-install, it should point to src.
    # We will check src just to be sure what is on disk.
    inspect_file("~/ws/src/andino/andino_control/config/andino_controllers.yaml")
