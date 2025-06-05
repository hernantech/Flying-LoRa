import threading
import queue
import time
import logging
import numpy as np
from typing import Optional, List, Dict, Tuple
import cv2
import tensorrt as trt
import pycuda.driver as cuda
import pycuda.autoinit
from config import ConfigManager
from logging_config import LoggerSetup, PerformanceProfiler
from metrics import MetricsCollector

class DetectionService:
    def __init__(self):
        # Initialize configuration
        self.config = ConfigManager()
        
        # Setup logging
        self.log_setup = LoggerSetup()
        self.logger = self.log_setup.get_logger()
        
        # Initialize metrics
        self.metrics = MetricsCollector()
        
        # Initialize queues
        self.input_queue = queue.Queue(maxsize=30)  # Frame buffer
        self.output_queue = queue.Queue(maxsize=30)  # Detection results
        
        # Threading control
        self.running = False
        self.detection_thread: Optional[threading.Thread] = None
        self.frame_count = 0
        self.last_frame_time = time.time()
        
        # TensorRT/CUDA initialization
        self.trt_logger = trt.Logger(trt.Logger.WARNING)
        self.engine = None
        self.context = None
        self.stream = None
        self.host_inputs = None
        self.host_outputs = None
        self.device_inputs = None
        self.device_outputs = None
        
        # Initialize TensorRT engine
        self._initialize_tensorrt()
        
        # Register configuration observer
        self.config.register_observer(self._handle_config_change)

    def _initialize_tensorrt(self):
        """Initialize TensorRT engine and CUDA resources"""
        try:
            with self.PerformanceProfiler(self.logger, "tensorrt_init"):
                # Load engine
                model_path = self.config.get('detection.model_path')
                with open(model_path, 'rb') as f, trt.Runtime(self.trt_logger) as runtime:
                    self.engine = runtime.deserialize_cuda_engine(f.read())
                
                # Create execution context
                self.context = self.engine.create_execution_context()
                
                # Allocate memory
                self.stream = cuda.Stream()
                
                # Allocate host and device buffers
                self._allocate_buffers()
                
                self.logger.info("TensorRT engine initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize TensorRT: {e}")
            raise

    def _allocate_buffers(self):
        """Allocate host and device buffers"""
        self.host_inputs = []
        self.host_outputs = []
        self.device_inputs = []
        self.device_outputs = []
        
        for binding in self.engine:
            size = trt.volume(self.engine.get_binding_shape(binding))
            dtype = trt.nptype(self.engine.get_binding_dtype(binding))
            
            # Allocate host and device memory
            host_mem = cuda.pagelocked_empty(size, dtype)
            device_mem = cuda.mem_alloc(host_mem.nbytes)
            
            if self.engine.binding_is_input(binding):
                self.host_inputs.append(host_mem)
                self.device_inputs.append(device_mem)
            else:
                self.host_outputs.append(host_mem)
                self.device_outputs.append(device_mem)

    def start(self):
        """Start the detection service"""
        if not self.running:
            self.running = True
            self.detection_thread = threading.Thread(target=self._detection_loop)
            self.detection_thread.start()
            self.logger.info("Detection service started")

    def stop(self):
        """Stop the detection service"""
        if self.running:
            self.running = False
            if self.detection_thread:
                self.detection_thread.join()
            self.logger.info("Detection service stopped")

    def enqueue_frame(self, frame: np.ndarray) -> bool:
        """Enqueue a frame for detection"""
        try:
            self.input_queue.put(frame, timeout=0.1)
            return True
        except queue.Full:
            self.logger.warning("Input queue full, dropping frame")
            return False

    def get_detection(self, timeout: float = 0.1) -> Optional[Dict]:
        """Get detection results"""
        try:
            return self.output_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    @PerformanceProfiler.profile(logging.getLogger(__name__))
    def _process_frame(self, frame: np.ndarray) -> Dict:
        """Process a single frame through the detection model"""
        # Preprocess
        input_data = self._preprocess(frame)
        
        # Copy input data to device
        cuda.memcpy_htod_async(self.device_inputs[0], input_data, self.stream)
        
        # Execute inference
        self.context.execute_async_v2(
            bindings=[int(inp) for inp in self.device_inputs + self.device_outputs],
            stream_handle=self.stream.handle
        )
        
        # Copy results back to host
        cuda.memcpy_dtoh_async(self.host_outputs[0], self.device_outputs[0], self.stream)
        self.stream.synchronize()
        
        # Postprocess
        detections = self._postprocess(self.host_outputs[0])
        
        return detections

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame for inference"""
        # Implement preprocessing based on model requirements
        # This is a placeholder - adjust according to your model
        processed = cv2.resize(frame, (300, 300))
        processed = processed.transpose((2, 0, 1))  # HWC to CHW
        processed = processed.astype(np.float32) / 255.0
        return processed

    def _postprocess(self, raw_output: np.ndarray) -> Dict:
        """Postprocess detection outputs"""
        # Implement postprocessing based on model output format
        # This is a placeholder - adjust according to your model
        confidence_threshold = self.config.get('detection.confidence_threshold', 0.5)
        
        # Example output format
        return {
            'detections': [],  # List of detection boxes
            'confidence_scores': [],  # Confidence scores
            'classes': []  # Class labels
        }

    def _detection_loop(self):
        """Main detection loop"""
        while self.running:
            try:
                # Rate limiting
                max_fps = self.config.get('detection.max_frame_rate', 30)
                current_time = time.time()
                elapsed = current_time - self.last_frame_time
                
                if elapsed < 1.0/max_fps:
                    time.sleep(0.001)  # Small sleep to prevent CPU spinning
                    continue
                
                # Get frame from queue
                frame = self.input_queue.get(timeout=0.1)
                
                # Process frame
                start_time = time.time()
                result = self._process_frame(frame)
                processing_time = time.time() - start_time
                
                # Update metrics
                self.metrics.record_detection(
                    latency=processing_time,
                    confidence=np.mean(result['confidence_scores']) if result['confidence_scores'] else 0
                )
                
                # Enqueue result
                self.output_queue.put(result)
                
                # Update frame timing
                self.frame_count += 1
                self.last_frame_time = current_time
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error in detection loop: {e}")
                time.sleep(1)  # Prevent rapid error loops

    def _handle_config_change(self, new_config: Dict):
        """Handle configuration changes"""
        # Update relevant parameters based on new configuration
        pass

    def __del__(self):
        """Cleanup resources"""
        self.stop()
        if hasattr(self, 'context'):
            self.context.destroy()
        if hasattr(self, 'engine'):
            self.engine.destroy()

# Example usage
if __name__ == '__main__':
    service = DetectionService()
    service.start()
    
    # Example: Process a test frame
    test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    service.enqueue_frame(test_frame)
    
    # Get results
    result = service.get_detection()
    print("Detection result:", result)
    
    service.stop() 