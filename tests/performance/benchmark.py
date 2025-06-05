import time
import json
import psutil
import numpy as np
import pandas as pd
from typing import Dict, List, Callable
from pathlib import Path
from datetime import datetime

from simulation import SimulationEnvironment, SimulatedLoRaHandler
from mesh_network import MeshNetworkManager
from data_storage import TimeSeriesDB
from cache_manager import CacheManager
from detection_service import DetectionService

class Benchmark:
    def __init__(self, output_dir: str = "benchmark_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.simulation = SimulationEnvironment()
        self.db = TimeSeriesDB(db_path=":memory:")
        self.cache = CacheManager()
        self.detection = DetectionService()
        
        # Create test nodes
        self.nodes = [
            MeshNetworkManager(f"node_{i}", is_gateway=(i == 0))
            for i in range(5)
        ]
        
        # Replace with simulated components
        for node in self.nodes:
            node.lora = SimulatedLoRaHandler()
        
        # Start components
        self.simulation.start()
        for node in self.nodes:
            node.start()
        
        # Results storage
        self.results = {
            'message_latency': [],
            'detection_time': [],
            'database_write_time': [],
            'database_query_time': [],
            'cache_operation_time': [],
            'memory_usage': [],
            'cpu_usage': []
        }

    def benchmark_message_latency(self, num_messages: int = 1000):
        """Benchmark message transmission latency"""
        print("\nBenchmarking message latency...")
        latencies = []
        
        for _ in range(num_messages):
            start_time = time.time()
            
            # Send message through mesh network
            source_node = self.nodes[0]
            dest_node = self.nodes[-1]
            message = f"test_message_{time.time()}"
            
            source_node.send_message(dest_node.node_id, message)
            
            # Wait for message to arrive
            while True:
                received = dest_node.lora.receive_message(timeout=1.0)
                if received == message:
                    break
            
            latency = time.time() - start_time
            latencies.append(latency)
            
            # Add system metrics
            self._record_system_metrics()
        
        self.results['message_latency'] = latencies
        
        # Print summary
        print(f"Average latency: {np.mean(latencies):.3f} seconds")
        print(f"95th percentile: {np.percentile(latencies, 95):.3f} seconds")

    def benchmark_detection_performance(self, num_frames: int = 100):
        """Benchmark object detection performance"""
        print("\nBenchmarking detection performance...")
        processing_times = []
        
        for _ in range(num_frames):
            # Get frame from simulation
            frame = self.simulation.get_frame()
            if frame is not None:
                start_time = time.time()
                
                # Process detection
                self.detection.process_frame(frame)
                
                processing_time = time.time() - start_time
                processing_times.append(processing_time)
                
                # Add system metrics
                self._record_system_metrics()
        
        self.results['detection_time'] = processing_times
        
        # Print summary
        print(f"Average processing time: {np.mean(processing_times):.3f} seconds")
        print(f"FPS: {1.0 / np.mean(processing_times):.1f}")

    def benchmark_database_performance(self, num_operations: int = 10000):
        """Benchmark database performance"""
        print("\nBenchmarking database performance...")
        write_times = []
        query_times = []
        
        # Write operations
        for i in range(num_operations):
            start_time = time.time()
            
            self.db.insert(
                metric_name="benchmark_metric",
                value=i,
                tags={'test': 'benchmark'},
                data={'timestamp': time.time()}
            )
            
            write_times.append(time.time() - start_time)
            
            # Add system metrics every 100 operations
            if i % 100 == 0:
                self._record_system_metrics()
        
        # Query operations
        for _ in range(num_operations // 10):  # Fewer queries than writes
            start_time = time.time()
            
            end_time = time.time()
            start_time_query = end_time - 3600
            
            self.db.query(
                metric_name="benchmark_metric",
                start_time=start_time_query,
                end_time=end_time
            )
            
            query_times.append(time.time() - start_time)
        
        self.results['database_write_time'] = write_times
        self.results['database_query_time'] = query_times
        
        # Print summary
        print(f"Average write time: {np.mean(write_times):.6f} seconds")
        print(f"Average query time: {np.mean(query_times):.6f} seconds")
        print(f"Write operations per second: {1.0 / np.mean(write_times):.1f}")

    def benchmark_cache_performance(self, num_operations: int = 10000):
        """Benchmark cache performance"""
        print("\nBenchmarking cache performance...")
        operation_times = []
        
        for i in range(num_operations):
            start_time = time.time()
            
            # Set and get operations
            key = f"benchmark_key_{i}"
            data = {
                'value': i,
                'timestamp': time.time()
            }
            
            self.cache.set_detection_result(key, data)
            self.cache.get_detection_result(key)
            
            operation_times.append(time.time() - start_time)
            
            # Add system metrics every 100 operations
            if i % 100 == 0:
                self._record_system_metrics()
        
        self.results['cache_operation_time'] = operation_times
        
        # Print summary
        print(f"Average operation time: {np.mean(operation_times):.6f} seconds")
        print(f"Operations per second: {1.0 / np.mean(operation_times):.1f}")

    def _record_system_metrics(self):
        """Record system resource usage"""
        self.results['cpu_usage'].append(psutil.cpu_percent())
        self.results['memory_usage'].append(psutil.Process().memory_info().rss / 1024 / 1024)  # MB

    def run_all_benchmarks(self):
        """Run all benchmarks"""
        try:
            self.benchmark_message_latency()
            self.benchmark_detection_performance()
            self.benchmark_database_performance()
            self.benchmark_cache_performance()
            
            # Save results
            self.save_results()
            
        finally:
            self.cleanup()

    def save_results(self):
        """Save benchmark results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.output_dir / f"benchmark_results_{timestamp}.json"
        
        # Convert results to serializable format
        serializable_results = {
            key: list(map(float, values))
            for key, values in self.results.items()
        }
        
        # Calculate statistics
        stats = {
            'message_latency': {
                'mean': float(np.mean(self.results['message_latency'])),
                'p95': float(np.percentile(self.results['message_latency'], 95)),
                'max': float(np.max(self.results['message_latency']))
            },
            'detection_time': {
                'mean': float(np.mean(self.results['detection_time'])),
                'fps': float(1.0 / np.mean(self.results['detection_time'])),
                'p95': float(np.percentile(self.results['detection_time'], 95))
            },
            'database_performance': {
                'write_time_mean': float(np.mean(self.results['database_write_time'])),
                'query_time_mean': float(np.mean(self.results['database_query_time'])),
                'writes_per_second': float(1.0 / np.mean(self.results['database_write_time']))
            },
            'cache_performance': {
                'operation_time_mean': float(np.mean(self.results['cache_operation_time'])),
                'operations_per_second': float(1.0 / np.mean(self.results['cache_operation_time']))
            },
            'system_metrics': {
                'cpu_usage_mean': float(np.mean(self.results['cpu_usage'])),
                'memory_usage_mean': float(np.mean(self.results['memory_usage']))
            }
        }
        
        # Save results and stats
        with open(results_file, 'w') as f:
            json.dump({
                'results': serializable_results,
                'statistics': stats
            }, f, indent=2)
        
        print(f"\nResults saved to: {results_file}")
        
        # Generate plots
        self._generate_plots(timestamp)

    def _generate_plots(self, timestamp: str):
        """Generate performance plots"""
        try:
            import matplotlib.pyplot as plt
            
            # Create plots directory
            plots_dir = self.output_dir / "plots"
            plots_dir.mkdir(exist_ok=True)
            
            # Message latency distribution
            plt.figure(figsize=(10, 6))
            plt.hist(self.results['message_latency'], bins=50)
            plt.title('Message Latency Distribution')
            plt.xlabel('Latency (seconds)')
            plt.ylabel('Count')
            plt.savefig(plots_dir / f"message_latency_{timestamp}.png")
            plt.close()
            
            # Detection time series
            plt.figure(figsize=(10, 6))
            plt.plot(self.results['detection_time'])
            plt.title('Detection Processing Time')
            plt.xlabel('Frame Number')
            plt.ylabel('Processing Time (seconds)')
            plt.savefig(plots_dir / f"detection_time_{timestamp}.png")
            plt.close()
            
            # System metrics
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))
            
            ax1.plot(self.results['cpu_usage'])
            ax1.set_title('CPU Usage')
            ax1.set_ylabel('Percentage')
            
            ax2.plot(self.results['memory_usage'])
            ax2.set_title('Memory Usage')
            ax2.set_ylabel('MB')
            
            plt.tight_layout()
            plt.savefig(plots_dir / f"system_metrics_{timestamp}.png")
            plt.close()
            
        except ImportError:
            print("matplotlib not installed, skipping plot generation")

    def cleanup(self):
        """Cleanup benchmark environment"""
        self.simulation.stop()
        for node in self.nodes:
            node.stop()
        self.db.close()
        self.cache.close()

if __name__ == '__main__':
    benchmark = Benchmark()
    benchmark.run_all_benchmarks() 