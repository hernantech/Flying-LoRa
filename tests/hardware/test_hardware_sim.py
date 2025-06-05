import pytest
import numpy as np
import time
from typing import Dict, List, Tuple
from unittest.mock import MagicMock

from simulation import SimulatedHardwareInterface
from hardware_interface import HardwareInterface

class TestHardwareSimulation:
    @pytest.fixture(scope="function")
    def hardware(self):
        """Initialize simulated hardware"""
        hw = SimulatedHardwareInterface()
        yield hw
        hw.cleanup()

    def test_camera_initialization(self, hardware):
        """Test camera initialization"""
        assert hardware.initialize_camera() is True

    def test_camera_frame_reading(self, hardware):
        """Test camera frame reading"""
        # Read multiple frames
        for _ in range(10):
            success, frame = hardware.read_camera_frame()
            
            # Check frame properties
            assert success is True
            assert isinstance(frame, np.ndarray)
            assert frame.shape == (480, 640, 3)
            assert frame.dtype == np.uint8
            
            # Check frame content
            assert np.any(frame != 0), "Frame should not be completely black"
            
            time.sleep(0.1)  # Simulate realistic frame rate

    def test_gps_location(self, hardware):
        """Test GPS location simulation"""
        # Get multiple readings
        locations = [hardware.get_gps_location() for _ in range(10)]
        
        # Check data structure
        for loc in locations:
            assert isinstance(loc, dict)
            assert all(key in loc for key in ['latitude', 'longitude', 'altitude', 'accuracy', 'timestamp'])
            
            # Check value ranges
            assert 37.7 <= loc['latitude'] <= 37.8
            assert -122.5 <= loc['longitude'] <= -122.3
            assert 90 <= loc['altitude'] <= 110
            assert loc['accuracy'] > 0
            assert isinstance(loc['timestamp'], float)
        
        # Check that values change between readings
        lats = [loc['latitude'] for loc in locations]
        lons = [loc['longitude'] for loc in locations]
        
        assert len(set(lats)) > 1, "Latitude should vary between readings"
        assert len(set(lons)) > 1, "Longitude should vary between readings"

    def test_telemetry_data(self, hardware):
        """Test telemetry data simulation"""
        # Get multiple readings
        readings = [hardware.get_telemetry() for _ in range(10)]
        
        # Check data structure
        for reading in readings:
            assert isinstance(reading, dict)
            assert all(key in reading for key in [
                'cpu_temp', 'gpu_temp', 'battery_voltage', 'memory_usage'
            ])
            
            # Check value ranges
            assert 35 <= reading['cpu_temp'] <= 85
            assert 45 <= reading['gpu_temp'] <= 95
            assert 10.5 <= reading['battery_voltage'] <= 12.6
            assert 20 <= reading['memory_usage'] <= 95
        
        # Check that values change between readings
        cpu_temps = [r['cpu_temp'] for r in readings]
        gpu_temps = [r['gpu_temp'] for r in readings]
        
        assert len(set(cpu_temps)) > 1, "CPU temperature should vary between readings"
        assert len(set(gpu_temps)) > 1, "GPU temperature should vary between readings"

    def test_long_running_simulation(self, hardware):
        """Test long-running simulation stability"""
        start_time = time.time()
        duration = 5  # Run for 5 seconds
        
        frame_count = 0
        error_count = 0
        
        while time.time() - start_time < duration:
            try:
                # Read frame
                success, frame = hardware.read_camera_frame()
                if success:
                    frame_count += 1
                
                # Get telemetry
                telemetry = hardware.get_telemetry()
                assert all(key in telemetry for key in [
                    'cpu_temp', 'gpu_temp', 'battery_voltage', 'memory_usage'
                ])
                
                # Get GPS
                location = hardware.get_gps_location()
                assert all(key in location for key in [
                    'latitude', 'longitude', 'altitude', 'accuracy', 'timestamp'
                ])
                
                time.sleep(0.1)  # Simulate realistic update rate
                
            except Exception as e:
                error_count += 1
                print(f"Error during long-running test: {e}")
        
        # Check results
        assert frame_count > 0, "Should have received frames"
        assert error_count == 0, "Should not have encountered errors"
        
        # Calculate and print metrics
        elapsed = time.time() - start_time
        fps = frame_count / elapsed
        
        print(f"\nLong-running test metrics:")
        print(f"Duration: {elapsed:.1f} seconds")
        print(f"Frames captured: {frame_count}")
        print(f"Average FPS: {fps:.1f}")

    def test_error_handling(self, hardware):
        """Test error handling in hardware simulation"""
        # Test camera failure simulation
        hardware.simulation.running = False  # Simulate hardware failure
        success, frame = hardware.read_camera_frame()
        
        # Should still return a frame, even if black
        assert success is True
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (480, 640, 3)
        assert not np.any(frame), "Should return black frame on failure"
        
        # Restore simulation
        hardware.simulation.running = True

    def test_resource_cleanup(self, hardware):
        """Test resource cleanup"""
        # Get initial resource state
        initial_memory = hardware.simulation.get_telemetry()['memory_usage']
        
        # Perform operations
        for _ in range(10):
            success, frame = hardware.read_camera_frame()
            hardware.get_gps_location()
            hardware.get_telemetry()
        
        # Cleanup
        hardware.cleanup()
        
        # Check simulation state
        assert not hardware.simulation.running, "Simulation should be stopped"
        
        # Check resource usage
        import psutil
        current_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        # Memory usage should not have increased significantly
        assert current_memory - initial_memory < 50, "Memory usage increased too much"

    def test_concurrent_access(self, hardware):
        """Test concurrent access to hardware interface"""
        import threading
        
        # Shared counters
        frame_count = 0
        error_count = 0
        lock = threading.Lock()
        
        def worker():
            nonlocal frame_count, error_count
            
            try:
                # Read frame
                success, frame = hardware.read_camera_frame()
                if success:
                    with lock:
                        nonlocal frame_count
                        frame_count += 1
                
                # Get telemetry
                telemetry = hardware.get_telemetry()
                
                # Get GPS
                location = hardware.get_gps_location()
                
            except Exception as e:
                with lock:
                    nonlocal error_count
                    error_count += 1
                print(f"Error in worker thread: {e}")
        
        # Create and start threads
        threads = []
        for _ in range(5):  # 5 concurrent threads
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Check results
        assert frame_count > 0, "Should have received frames"
        assert error_count == 0, "Should not have encountered errors"

if __name__ == '__main__':
    pytest.main([__file__, '-v']) 