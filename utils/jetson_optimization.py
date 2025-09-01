#!/usr/bin/env python
"""
Jetson-specific optimizations for OWL
This module provides TensorRT optimization and GPU acceleration for ML inference on Jetson platforms
"""

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class JetsonOptimizer:
    """Handles Jetson-specific optimizations for machine learning inference"""
    
    def __init__(self):
        self.tensorrt_available = False
        self.cuda_available = False
        self._check_acceleration_support()
    
    def _check_acceleration_support(self):
        """Check what acceleration methods are available"""
        # Check for TensorRT
        try:
            import tensorrt as trt
            self.tensorrt_available = True
            logger.info("TensorRT is available for ML acceleration")
        except ImportError:
            logger.info("TensorRT not available - ML inference will use CPU")
        
        # Check for CUDA
        try:
            import pycuda.driver as cuda
            import pycuda.autoinit
            self.cuda_available = True
            logger.info("CUDA is available for GPU acceleration")
        except ImportError:
            logger.info("CUDA not available - using CPU only")
    
    def optimize_tflite_model(self, model_path: str, optimized_path: Optional[str] = None) -> str:
        """
        Optimize a TensorFlow Lite model for Jetson inference
        
        Args:
            model_path: Path to the original .tflite model
            optimized_path: Optional path for the optimized model
            
        Returns:
            Path to the optimized model
        """
        if not self.tensorrt_available:
            logger.warning("TensorRT not available, returning original model path")
            return model_path
        
        try:
            import tensorflow as tf
            
            # Set up paths
            model_path = Path(model_path)
            if optimized_path is None:
                optimized_path = model_path.parent / f"{model_path.stem}_jetson_optimized.tflite"
            
            # Load the model
            interpreter = tf.lite.Interpreter(model_path=str(model_path))
            interpreter.allocate_tensors()
            
            # Get model details
            input_details = interpreter.get_input_details()
            output_details = interpreter.get_output_details()
            
            logger.info(f"Model input shape: {input_details[0]['shape']}")
            logger.info(f"Model output shape: {output_details[0]['shape']}")
            
            # For now, return the original path as TensorRT optimization 
            # for TFLite models requires more complex conversion pipeline
            logger.info("Using original TFLite model (TensorRT optimization for TFLite requires additional setup)")
            return str(model_path)
            
        except Exception as e:
            logger.error(f"Failed to optimize model: {e}")
            return model_path
    
    def get_optimal_inference_config(self) -> dict:
        """Get optimal configuration for ML inference on this Jetson device"""
        config = {
            'use_gpu': self.cuda_available,
            'use_tensorrt': self.tensorrt_available,
            'num_threads': 4,  # Jetson Orin Nano has 6 cores, leave some for system
            'precision': 'fp16' if self.tensorrt_available else 'fp32',
        }
        
        # Jetson Orin Nano Super specific optimizations
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read().strip().lower()
                if 'orin nano' in model:
                    if 'super' in model:
                        config['num_threads'] = 6  # Orin Nano Super has more compute
                        config['batch_size'] = 2   # Can handle larger batches
                    else:
                        config['num_threads'] = 4
                        config['batch_size'] = 1
        except (FileNotFoundError, IOError):
            pass
        
        logger.info(f"Optimal inference config: {config}")
        return config
    
    def enable_jetson_clocks(self) -> bool:
        """Enable maximum performance mode on Jetson (requires sudo)"""
        try:
            import subprocess
            
            # Check if jetson_clocks is available
            result = subprocess.run(['which', 'jetson_clocks'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                # Enable maximum performance
                result = subprocess.run(['sudo', 'jetson_clocks'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info("Jetson maximum performance mode enabled")
                    return True
                else:
                    logger.warning(f"Failed to enable jetson_clocks: {result.stderr}")
            else:
                logger.info("jetson_clocks not available on this system")
                
        except Exception as e:
            logger.error(f"Error enabling Jetson performance mode: {e}")
        
        return False
    
    def get_memory_info(self) -> dict:
        """Get memory information for optimization purposes"""
        memory_info = {}
        
        try:
            # Get system memory info
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
                for line in meminfo.split('\n'):
                    if 'MemTotal:' in line:
                        memory_info['total_ram_kb'] = int(line.split()[1])
                    elif 'MemAvailable:' in line:
                        memory_info['available_ram_kb'] = int(line.split()[1])
        except (FileNotFoundError, IOError):
            pass
        
        # Get GPU memory info if CUDA is available
        if self.cuda_available:
            try:
                import pycuda.driver as cuda
                
                device = cuda.Device(0)
                context = device.make_context()
                
                free_mem, total_mem = cuda.mem_get_info()
                memory_info['gpu_free_mb'] = free_mem // (1024 * 1024)
                memory_info['gpu_total_mb'] = total_mem // (1024 * 1024)
                
                context.pop()
                
            except Exception as e:
                logger.warning(f"Could not get GPU memory info: {e}")
        
        return memory_info

def get_jetson_optimizer() -> Optional[JetsonOptimizer]:
    """Factory function to create JetsonOptimizer if on Jetson platform"""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().strip().lower()
            if 'jetson' in model:
                return JetsonOptimizer()
    except (FileNotFoundError, IOError):
        pass
    
    return None

# Example usage and testing
if __name__ == "__main__":
    optimizer = get_jetson_optimizer()
    
    if optimizer:
        print("Jetson platform detected!")
        config = optimizer.get_optimal_inference_config()
        print(f"Optimal config: {config}")
        
        memory_info = optimizer.get_memory_info()
        print(f"Memory info: {memory_info}")
        
        # Enable performance mode (requires sudo)
        # optimizer.enable_jetson_clocks()
    else:
        print("Not running on Jetson platform")