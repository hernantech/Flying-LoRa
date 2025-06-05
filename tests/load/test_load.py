import time
import threading
import random
import pytest
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

from simulation import SimulationEnvironment, SimulatedLoRaHandler, SimulatedHardwareInterface
from mesh_network import MeshNetworkManager
from data_storage import TimeSeriesDB
from cache_manager import CacheManager

class LoadTest:
    def __init__(self, num_nodes: int = 10, duration: int = 60):
        self.num_nodes = num_nodes
        self.duration = duration
        
        # Initialize components
        self.simulation = SimulationEnvironment()
        self.db = TimeSeriesDB(db_path=":memory:")  # In-memory database for testing
        self.cache = CacheManager()
        
        # Create mesh network nodes
        self.nodes = [
            MeshNetworkManager(f"node_{i}", is_gateway=(i == 0))
            for i in range(num_nodes)
        ]
        
        # Replace LoRa handlers with simulated ones
        for node in self.nodes:
            node.lora = SimulatedLoRaHandler()
        
        # Statistics
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'detections_processed': 0,
            'db_operations': 0,
            'cache_operations': 0,
            'errors': 0
        }
        
        # Start components
        self.simulation.start()
        for node in self.nodes:
            node.start()

    def run_mesh_network_test(self):
        """Test mesh network under load"""
        try:
            with ThreadPoolExecutor(max_workers=self.num_nodes) as executor:
                # Submit message sending tasks
                futures = []
                for i in range(self.num_nodes):
                    futures.append(
                        executor.submit(
                            self._node_communication_task,
                            self.nodes[i],
                            self.nodes[(i + 1) % self.num_nodes].node_id
                        )
                    )
                
                # Wait for all tasks to complete
                for future in as_completed(futures):
                    try:
                        stats = future.result()
                        self._update_stats(stats)
                    except Exception as e:
                        self.stats['errors'] += 1
                        print(f"Error in mesh network test: {e}")
            
        except Exception as e:
            print(f"Mesh network test failed: {e}")
            self.stats['errors'] += 1

    def run_detection_test(self):
        """Test detection processing under load"""
        try:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                for _ in range(100):  # Process 100 frames
                    futures.append(
                        executor.submit(self._detection_processing_task)
                    )
                
                for future in as_completed(futures):
                    try:
                        stats = future.result()
                        self._update_stats(stats)
                    except Exception as e:
                        self.stats['errors'] += 1
                        print(f"Error in detection test: {e}")
            
        except Exception as e:
            print(f"Detection test failed: {e}")
            self.stats['errors'] += 1

    def run_database_test(self):
        """Test database operations under load"""
        try:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                
                # Write operations
                for _ in range(1000):
                    futures.append(
                        executor.submit(self._database_operation_task)
                    )
                
                # Read operations
                for _ in range(500):
                    futures.append(
                        executor.submit(self._database_query_task)
                    )
                
                for future in as_completed(futures):
                    try:
                        stats = future.result()
                        self._update_stats(stats)
                    except Exception as e:
                        self.stats['errors'] += 1
                        print(f"Error in database test: {e}")
            
        except Exception as e:
            print(f"Database test failed: {e}")
            self.stats['errors'] += 1

    def run_cache_test(self):
        """Test cache operations under load"""
        try:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                
                # Cache operations
                for _ in range(1000):
                    futures.append(
                        executor.submit(self._cache_operation_task)
                    )
                
                for future in as_completed(futures):
                    try:
                        stats = future.result()
                        self._update_stats(stats)
                    except Exception as e:
                        self.stats['errors'] += 1
                        print(f"Error in cache test: {e}")
            
        except Exception as e:
            print(f"Cache test failed: {e}")
            self.stats['errors'] += 1

    def _node_communication_task(self, node: MeshNetworkManager, target_id: str) -> Dict:
        """Simulate node communication"""
        stats = {'messages_sent': 0, 'messages_received': 0, 'errors': 0}
        
        start_time = time.time()
        while time.time() - start_time < self.duration:
            try:
                # Send message
                message = f"test_message_{time.time()}"
                node.send_message(target_id, message)
                stats['messages_sent'] += 1
                
                # Receive message
                received = node.lora.receive_message(timeout=1.0)
                if received:
                    stats['messages_received'] += 1
                
                time.sleep(random.uniform(0.1, 0.5))
                
            except Exception as e:
                stats['errors'] += 1
                print(f"Error in node communication: {e}")
        
        return stats

    def _detection_processing_task(self) -> Dict:
        """Simulate detection processing"""
        stats = {'detections_processed': 0, 'errors': 0}
        
        try:
            # Get frame and process detection
            frame = self.simulation.get_frame()
            if frame is not None:
                detection = self.simulation.get_detection()
                if detection:
                    # Cache detection result
                    self.cache.set_detection_result(
                        f"det_{time.time()}",
                        detection
                    )
                    stats['detections_processed'] += 1
            
        except Exception as e:
            stats['errors'] += 1
            print(f"Error in detection processing: {e}")
        
        return stats

    def _database_operation_task(self) -> Dict:
        """Simulate database operations"""
        stats = {'db_operations': 0, 'errors': 0}
        
        try:
            # Insert test data
            self.db.insert(
                metric_name="test_metric",
                value=random.random(),
                tags={'test': 'load'},
                data={'timestamp': time.time()}
            )
            stats['db_operations'] += 1
            
        except Exception as e:
            stats['errors'] += 1
            print(f"Error in database operation: {e}")
        
        return stats

    def _database_query_task(self) -> Dict:
        """Simulate database queries"""
        stats = {'db_operations': 0, 'errors': 0}
        
        try:
            # Query test data
            end_time = time.time()
            start_time = end_time - 3600
            
            self.db.query(
                metric_name="test_metric",
                start_time=start_time,
                end_time=end_time
            )
            stats['db_operations'] += 1
            
        except Exception as e:
            stats['errors'] += 1
            print(f"Error in database query: {e}")
        
        return stats

    def _cache_operation_task(self) -> Dict:
        """Simulate cache operations"""
        stats = {'cache_operations': 0, 'errors': 0}
        
        try:
            # Set and get cache data
            key = f"test_key_{random.randint(1, 100)}"
            data = {
                'value': random.random(),
                'timestamp': time.time()
            }
            
            self.cache.set_detection_result(key, data)
            self.cache.get_detection_result(key)
            stats['cache_operations'] += 2
            
        except Exception as e:
            stats['errors'] += 1
            print(f"Error in cache operation: {e}")
        
        return stats

    def _update_stats(self, new_stats: Dict):
        """Update global statistics"""
        for key, value in new_stats.items():
            if key in self.stats:
                self.stats[key] += value

    def cleanup(self):
        """Cleanup test environment"""
        self.simulation.stop()
        for node in self.nodes:
            node.stop()
        self.db.close()
        self.cache.close()

def test_system_load():
    """Main load test"""
    # Initialize load test
    load_test = LoadTest(num_nodes=10, duration=60)
    
    try:
        # Run tests
        print("\nRunning mesh network test...")
        load_test.run_mesh_network_test()
        
        print("\nRunning detection test...")
        load_test.run_detection_test()
        
        print("\nRunning database test...")
        load_test.run_database_test()
        
        print("\nRunning cache test...")
        load_test.run_cache_test()
        
        # Print results
        print("\nLoad Test Results:")
        print("-" * 40)
        for key, value in load_test.stats.items():
            print(f"{key}: {value}")
        
        # Assert test conditions
        assert load_test.stats['errors'] == 0, "Load test encountered errors"
        assert load_test.stats['messages_sent'] > 0, "No messages were sent"
        assert load_test.stats['detections_processed'] > 0, "No detections were processed"
        assert load_test.stats['db_operations'] > 0, "No database operations performed"
        assert load_test.stats['cache_operations'] > 0, "No cache operations performed"
        
    finally:
        load_test.cleanup()

if __name__ == '__main__':
    test_system_load() 