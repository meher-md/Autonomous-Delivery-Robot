
import serial
import time
import sys
import glob

def get_serial_port():
    # Try common ports
    ports = glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyUSB*')
    if not ports:
        return None
    return ports[0] # Return first available

def main():
    port = get_serial_port()
    if not port:
        print("Error: No serial port found (/dev/ttyACM* or /dev/ttyUSB*)")
        return

    baud = 57600
    
    print(f"Connecting to {port} at {baud} baud...")
    
    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(2) # Wait for Arduino reset
        print("Connected.")
        
        # Flush startup messages
        ser.reset_input_buffer()
        
        print("Reading Ultrasonic Sensor (Press Ctrl+C to stop)...")
        while True:
            # Send 's' command
            ser.write(b's\r')
            
            # Read response
            line = ser.readline().decode('utf-8').strip()
            
            if line:
                print(f"Distance: {line} m")
            else:
                print("No response (Timeout)")
            
            time.sleep(0.5)
            
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
        print("Hint: Make sure no ROS node is locking the port (e.g. diffdrive_andino).")
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()

if __name__ == '__main__':
    main()
