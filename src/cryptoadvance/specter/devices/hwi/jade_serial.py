import serial.tools.list_ports
import serial

def close_open_ports():
    ports = list(serial.tools.list_ports.comports())
    if len(ports) > 0:
        port = ports[0].device
        try:
            ser = serial.Serial(port)
            if ser.is_open:
                ser.close()
        except serial.SerialException as e:
            print(f"Failed to close port {port}: {e}")

def connect_to_jade():
    close_open_ports()

    # Existing connection logic here
    try:
        # Replace with actual Jade connection code
        # Example:
        # serial_connection = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
        print("Connected to Jade")
    except serial.SerialException as e:
        print(f"Failed to connect to Jade: {e}")