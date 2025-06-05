import threading
import time
import serial
import logging
from typing import Optional, Dict, Tuple
import cv2
import board
import busio
import adafruit_bno055
import adafruit_gps
import RPi.GPIO as GPIO
from config import ConfigManager
from logging_config import LoggerSetup, PerformanceProfiler

class HardwareInterface:
    def __init__(self):
        # Initialize configuration
        self.config = ConfigManager()
        
        # Setup logging
        self.log_setup = LoggerSetup()
        self.logger = self.log_setup.get_logger()
        
        # Initialize hardware components
        self._setup_gpio()
        self._setup_camera()
        self._setup_lora()
        self._setup_imu()
        self._setup_gps()
        
        # Threading control
        self.running = False
        self.sensor_thread: Optional[threading.Thread] = None
        
        # Register configuration observer
        self.config.register_observer(self._handle_config_change)

    def _setup_gpio(self):
        """Setup GPIO pins"""
        try:
            GPIO.setmode(GPIO.BCM)
            self.status_led = self.config.get('hardware.gpio.status_led', 18)
            self.error_led = self.config.get('hardware.gpio.error_led', 23)
            
            GPIO.setup(self.status_led, GPIO.OUT)
            GPIO.setup(self.error_led, GPIO.OUT)
            
            # Initialize LED states
            GPIO.output(self.status_led, GPIO.LOW)
            GPIO.output(self.error_led, GPIO.LOW)
            
            self.logger.info("GPIO initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize GPIO: {e}")
            raise

    def _setup_camera(self):
        """Setup CSI camera"""
        try:
            gst_str = (
                f"nvarguscamerasrc ! "
                f"video/x-raw(memory:NVMM), "
                f"width={self.config.get('hardware.camera.width', 1280)}, "
                f"height={self.config.get('hardware.camera.height', 720)}, "
                f"format=(string)NV12, "
                f"framerate={self.config.get('hardware.camera.fps', 30)}/1 ! "
                f"nvvidconv ! "
                f"video/x-raw, format=(string)BGRx ! "
                f"videoconvert ! "
                f"video/x-raw, format=(string)BGR ! "
                f"appsink"
            )
            
            self.camera = cv2.VideoCapture(gst_str, cv2.CAP_GSTREAMER)
            
            if not self.camera.isOpened():
                raise RuntimeError("Failed to open camera")
            
            self.logger.info("Camera initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize camera: {e}")
            raise

    def _setup_lora(self):
        """Setup LoRa UART communication"""
        try:
            port = self.config.get('hardware.lora.port', '/dev/ttyUSB0')
            baud_rate = self.config.get('hardware.lora.baud_rate', 115200)
            
            self.lora = serial.Serial(
                port=port,
                baudrate=baud_rate,
                timeout=1
            )
            
            self.logger.info("LoRa communication initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize LoRa: {e}")
            raise

    def _setup_imu(self):
        """Setup IMU over I2C"""
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.imu = adafruit_bno055.BNO055_I2C(i2c)
            self.logger.info("IMU initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize IMU: {e}")
            raise

    def _setup_gps(self):
        """Setup GPS module"""
        try:
            uart = serial.Serial("/dev/ttyTHS1", baudrate=9600, timeout=1)
            self.gps = adafruit_gps.GPS(uart, debug=False)
            
            # Initialize the GPS module
            self.gps.send_command(b'PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
            self.gps.send_command(b'PMTK220,1000')
            
            self.logger.info("GPS initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize GPS: {e}")
            raise

    def start(self):
        """Start hardware interface"""
        if not self.running:
            self.running = True
            self.sensor_thread = threading.Thread(target=self._sensor_loop)
            self.sensor_thread.start()
            GPIO.output(self.status_led, GPIO.HIGH)
            self.logger.info("Hardware interface started")

    def stop(self):
        """Stop hardware interface"""
        if self.running:
            self.running = False
            if self.sensor_thread:
                self.sensor_thread.join()
            GPIO.output(self.status_led, GPIO.LOW)
            self.logger.info("Hardware interface stopped")

    @PerformanceProfiler.profile(logging.getLogger(__name__))
    def get_frame(self) -> Optional[np.ndarray]:
        """Get frame from camera"""
        try:
            ret, frame = self.camera.read()
            if ret:
                return frame
            else:
                self.logger.warning("Failed to capture frame")
                return None
        except Exception as e:
            self.logger.error(f"Error capturing frame: {e}")
            return None

    def send_lora_message(self, message: str) -> bool:
        """Send message over LoRa"""
        try:
            self.lora.write(message.encode())
            return True
        except Exception as e:
            self.logger.error(f"Failed to send LoRa message: {e}")
            return False

    def read_lora_message(self) -> Optional[str]:
        """Read message from LoRa"""
        try:
            if self.lora.in_waiting:
                return self.lora.readline().decode().strip()
            return None
        except Exception as e:
            self.logger.error(f"Failed to read LoRa message: {e}")
            return None

    def get_imu_data(self) -> Dict[str, float]:
        """Get IMU sensor data"""
        try:
            return {
                'acceleration': self.imu.acceleration,
                'magnetic': self.imu.magnetic,
                'gyro': self.imu.gyro,
                'euler': self.imu.euler,
                'quaternion': self.imu.quaternion,
                'linear_acceleration': self.imu.linear_acceleration,
                'gravity': self.imu.gravity
            }
        except Exception as e:
            self.logger.error(f"Failed to read IMU data: {e}")
            return {}

    def get_gps_data(self) -> Dict[str, float]:
        """Get GPS data"""
        try:
            if self.gps.update():
                return {
                    'latitude': self.gps.latitude,
                    'longitude': self.gps.longitude,
                    'altitude': self.gps.altitude_m,
                    'speed': self.gps.speed_knots,
                    'satellites': self.gps.satellites
                }
            return {}
        except Exception as e:
            self.logger.error(f"Failed to read GPS data: {e}")
            return {}

    def set_error_led(self, state: bool):
        """Set error LED state"""
        try:
            GPIO.output(self.error_led, state)
        except Exception as e:
            self.logger.error(f"Failed to set error LED: {e}")

    def _sensor_loop(self):
        """Main sensor reading loop"""
        while self.running:
            try:
                # Read and process sensor data
                imu_data = self.get_imu_data()
                gps_data = self.get_gps_data()
                lora_message = self.read_lora_message()
                
                # Process data as needed
                
                time.sleep(0.1)  # Adjust sampling rate as needed
                
            except Exception as e:
                self.logger.error(f"Error in sensor loop: {e}")
                self.set_error_led(True)
                time.sleep(1)

    def _handle_config_change(self, new_config: Dict):
        """Handle configuration changes"""
        # Update relevant parameters based on new configuration
        pass

    def __del__(self):
        """Cleanup resources"""
        self.stop()
        
        if hasattr(self, 'camera'):
            self.camera.release()
        
        if hasattr(self, 'lora'):
            self.lora.close()
        
        GPIO.cleanup()

# Example usage
if __name__ == '__main__':
    interface = HardwareInterface()
    interface.start()
    
    # Example: Capture and save a frame
    frame = interface.get_frame()
    if frame is not None:
        cv2.imwrite('test_frame.jpg', frame)
    
    # Example: Send LoRa message
    interface.send_lora_message("Hello from Jetson!")
    
    # Example: Read sensor data
    print("IMU Data:", interface.get_imu_data())
    print("GPS Data:", interface.get_gps_data())
    
    interface.stop() 