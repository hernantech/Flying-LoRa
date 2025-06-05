import os
import time
import threading
import logging
import subprocess
from typing import Dict, Optional, List
import psutil
from config import ConfigManager
from logging_config import LoggerSetup, PerformanceProfiler
from metrics import MetricsCollector

class ResourceManager:
    def __init__(self):
        # Initialize configuration
        self.config = ConfigManager()
        
        # Setup logging
        self.log_setup = LoggerSetup()
        self.logger = self.log_setup.get_logger()
        
        # Initialize metrics
        self.metrics = MetricsCollector()
        
        # Threading control
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # System paths
        self.cpu_gov_path = "/sys/devices/system/cpu/cpu{}/cpufreq/scaling_governor"
        self.gpu_freq_path = "/sys/devices/gpu.0/devfreq/17000000.gv11b/max_freq"
        self.fan_speed_path = "/sys/devices/pwm-fan/target_pwm"
        self.thermal_zones = "/sys/class/thermal/thermal_zone*"
        
        # Current state
        self.current_power_mode = None
        self.critical_temp = self.config.get('resources.thermal_throttle_temp', 80)
        
        # Process priorities
        self.process_priorities = {
            'detection_service': -10,  # High priority
            'hardware_interface': -5,
            'websocket_server': 0,
            'logging_service': 10  # Low priority
        }
        
        # Register configuration observer
        self.config.register_observer(self._handle_config_change)

    def start(self):
        """Start resource management"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop)
            self.monitor_thread.start()
            self.logger.info("Resource manager started")

    def stop(self):
        """Stop resource management"""
        if self.running:
            self.running = False
            if self.monitor_thread:
                self.monitor_thread.join()
            self.logger.info("Resource manager stopped")

    def set_power_mode(self, mode: str):
        """Set power mode (5W/10W)"""
        try:
            if mode not in ['5W', '10W']:
                raise ValueError("Invalid power mode")
            
            if mode == '5W':
                self._set_cpu_governor('powersave')
                self._set_gpu_freq(76800000)  # Minimum frequency
            else:  # 10W
                self._set_cpu_governor('ondemand')
                self._set_gpu_freq(1300500000)  # Maximum frequency
            
            self.current_power_mode = mode
            self.logger.info(f"Power mode set to {mode}")
            
        except Exception as e:
            self.logger.error(f"Failed to set power mode: {e}")

    def _set_cpu_governor(self, governor: str):
        """Set CPU governor for all cores"""
        try:
            cpu_count = psutil.cpu_count()
            for cpu in range(cpu_count):
                gov_path = self.cpu_gov_path.format(cpu)
                if os.path.exists(gov_path):
                    with open(gov_path, 'w') as f:
                        f.write(governor)
            
            self.logger.info(f"CPU governor set to {governor}")
            
        except Exception as e:
            self.logger.error(f"Failed to set CPU governor: {e}")
            raise

    def _set_gpu_freq(self, freq: int):
        """Set GPU maximum frequency"""
        try:
            if os.path.exists(self.gpu_freq_path):
                with open(self.gpu_freq_path, 'w') as f:
                    f.write(str(freq))
                
                self.logger.info(f"GPU frequency set to {freq}")
            
        except Exception as e:
            self.logger.error(f"Failed to set GPU frequency: {e}")
            raise

    def set_process_priority(self, pid: int, priority: int):
        """Set process priority (nice value)"""
        try:
            os.setpriority(os.PRIO_PROCESS, pid, priority)
            self.logger.info(f"Process {pid} priority set to {priority}")
            
        except Exception as e:
            self.logger.error(f"Failed to set process priority: {e}")

    def get_thermal_zones(self) -> Dict[str, float]:
        """Get temperature readings from all thermal zones"""
        temps = {}
        try:
            for zone in subprocess.glob.glob(self.thermal_zones):
                type_path = os.path.join(zone, 'type')
                temp_path = os.path.join(zone, 'temp')
                
                if os.path.exists(type_path) and os.path.exists(temp_path):
                    with open(type_path, 'r') as f:
                        zone_type = f.read().strip()
                    with open(temp_path, 'r') as f:
                        # Temperature is in millicelsius
                        temp = float(f.read().strip()) / 1000
                    temps[zone_type] = temp
            
            return temps
            
        except Exception as e:
            self.logger.error(f"Failed to read thermal zones: {e}")
            return {}

    def set_fan_speed(self, speed: int):
        """Set fan speed (0-255)"""
        try:
            speed = max(0, min(255, speed))  # Clamp value
            if os.path.exists(self.fan_speed_path):
                with open(self.fan_speed_path, 'w') as f:
                    f.write(str(speed))
                
                self.logger.info(f"Fan speed set to {speed}")
            
        except Exception as e:
            self.logger.error(f"Failed to set fan speed: {e}")

    def get_memory_usage(self) -> Dict[str, float]:
        """Get memory usage statistics"""
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            return {
                'total': mem.total,
                'available': mem.available,
                'used': mem.used,
                'free': mem.free,
                'swap_total': swap.total,
                'swap_used': swap.used
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get memory usage: {e}")
            return {}

    def get_process_stats(self) -> List[Dict]:
        """Get statistics for monitored processes"""
        stats = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                if proc.info['name'] in self.process_priorities.keys():
                    stats.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cpu_percent': proc.info['cpu_percent'],
                        'memory_percent': proc.info['memory_percent'],
                        'priority': os.getpriority(os.PRIO_PROCESS, proc.info['pid'])
                    })
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get process stats: {e}")
            return []

    @PerformanceProfiler.profile(logging.getLogger(__name__))
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Get system metrics
                temps = self.get_thermal_zones()
                mem_usage = self.get_memory_usage()
                proc_stats = self.get_process_stats()
                
                # Check thermal throttling
                max_temp = max(temps.values()) if temps else 0
                if max_temp > self.critical_temp:
                    self._handle_thermal_throttling(max_temp)
                
                # Adjust process priorities if needed
                self._adjust_priorities(proc_stats)
                
                # Update metrics
                self._update_metrics(temps, mem_usage, proc_stats)
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                time.sleep(5)  # Wait before retrying

    def _handle_thermal_throttling(self, temp: float):
        """Handle thermal throttling"""
        try:
            # Increase fan speed
            current_speed = int(open(self.fan_speed_path, 'r').read().strip())
            new_speed = min(255, current_speed + 50)
            self.set_fan_speed(new_speed)
            
            # Reduce GPU frequency
            if self.current_power_mode == '10W':
                self._set_gpu_freq(76800000)  # Minimum frequency
                self.logger.warning(f"Thermal throttling activated at {temp}°C")
            
        except Exception as e:
            self.logger.error(f"Failed to handle thermal throttling: {e}")

    def _adjust_priorities(self, proc_stats: List[Dict]):
        """Adjust process priorities based on system load"""
        try:
            for proc in proc_stats:
                target_priority = self.process_priorities.get(proc['name'])
                if target_priority is not None and proc['priority'] != target_priority:
                    self.set_process_priority(proc['pid'], target_priority)
            
        except Exception as e:
            self.logger.error(f"Failed to adjust priorities: {e}")

    def _update_metrics(self, temps: Dict[str, float], mem_usage: Dict[str, float], proc_stats: List[Dict]):
        """Update system metrics"""
        try:
            # Temperature metrics
            for zone, temp in temps.items():
                self.metrics.temperature.labels(zone=zone).set(temp)
            
            # Memory metrics
            self.metrics.memory_usage.set(mem_usage['used'])
            self.metrics.memory_available.set(mem_usage['available'])
            
            # Process metrics
            for proc in proc_stats:
                self.metrics.process_cpu.labels(
                    process=proc['name']
                ).set(proc['cpu_percent'])
                self.metrics.process_memory.labels(
                    process=proc['name']
                ).set(proc['memory_percent'])
            
        except Exception as e:
            self.logger.error(f"Failed to update metrics: {e}")

    def _handle_config_change(self, new_config: Dict):
        """Handle configuration changes"""
        try:
            # Update thermal threshold
            self.critical_temp = new_config.get('resources.thermal_throttle_temp', 80)
            
            # Update power mode if changed
            new_mode = new_config.get('resources.power_mode')
            if new_mode and new_mode != self.current_power_mode:
                self.set_power_mode(new_mode)
            
        except Exception as e:
            self.logger.error(f"Failed to handle config change: {e}")

# Example usage
if __name__ == '__main__':
    manager = ResourceManager()
    manager.start()
    
    # Example: Set power mode
    manager.set_power_mode('10W')
    
    # Example: Monitor for a while
    time.sleep(60)
    
    manager.stop() 