import serial
import time
import requests
import json
from typing import Optional
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LoRaReceiver:
    def __init__(self, port: str = '/dev/ttyUSB0', baud_rate: int = 9600, server_url: str = 'http://localhost:8080'):
        """Initialize LoRa receiver with serial port configuration and server URL.
        
        Args:
            port: Serial port where LoRa device is connected
            baud_rate: Baud rate for serial communication
            server_url: Base URL of the Flask server
        """
        self.port = port
        self.baud_rate = baud_rate
        self.server_url = server_url
        self.serial_connection: Optional[serial.Serial] = None
        
    def connect(self) -> bool:
        """Establish connection with the LoRa device."""
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=1
            )
            logger.info(f"Successfully connected to LoRa device on {self.port}")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to LoRa device: {e}")
            return False
            
    def read_lora_data(self) -> Optional[str]:
        """Read data from LoRa device."""
        if not self.serial_connection:
            logger.error("No serial connection established")
            return None
            
        try:
            if self.serial_connection.in_waiting:
                data = self.serial_connection.readline().decode('utf-8').strip()
                return data
        except serial.SerialException as e:
            logger.error(f"Error reading from LoRa device: {e}")
        return None
        
    def update_server_mode(self, mode: int) -> bool:
        """Send mode update to Flask server."""
        try:
            response = requests.post(
                f"{self.server_url}/mode",
                json={"mode": mode},
                timeout=5
            )
            if response.status_code == 200:
                logger.info(f"Successfully updated server mode to {mode}")
                return True
            else:
                logger.error(f"Failed to update mode. Status code: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with server: {e}")
            return False
            
    def process_lora_data(self, data: str) -> None:
        """Process received LoRa data and update server if necessary."""
        try:
            # Assuming LoRa data is JSON formatted with a 'mode' field
            parsed_data = json.loads(data)
            if 'mode' in parsed_data:
                mode = int(parsed_data['mode'])
                if mode in [1, 2, 3]:
                    self.update_server_mode(mode)
                else:
                    logger.warning(f"Received invalid mode value: {mode}")
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LoRa data: {data}")
        except ValueError:
            logger.error(f"Invalid mode format in data: {data}")
            
    def run(self) -> None:
        """Main loop to continuously poll LoRa device and process data."""
        if not self.connect():
            return
            
        logger.info("Starting LoRa receiver loop...")
        while True:
            try:
                data = self.read_lora_data()
                if data:
                    logger.info(f"Received LoRa data: {data}")
                    self.process_lora_data(data)
                time.sleep(0.1)  # Small delay to prevent CPU overuse
            except KeyboardInterrupt:
                logger.info("Stopping LoRa receiver...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(1)  # Longer delay on error
                
        # Cleanup
        if self.serial_connection:
            self.serial_connection.close()
            
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="LoRa Receiver Service")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port for LoRa device")
    parser.add_argument("--baud", type=int, default=9600, help="Baud rate for serial communication")
    parser.add_argument("--server", default="http://localhost:8080", help="Flask server URL")
    
    args = parser.parse_args()
    
    receiver = LoRaReceiver(
        port=args.port,
        baud_rate=args.baud,
        server_url=args.server
    )
    receiver.run() 