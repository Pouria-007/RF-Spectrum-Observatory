"""
Performance metrics: FPS, latency, GPU memory usage.
"""

import time
import cupy as cp
from typing import Dict, List, Optional
from collections import deque


class PerformanceMonitor:
    """
    Monitor pipeline performance metrics.
    
    Tracks:
    - Frame rate (FPS)
    - Latency per frame (ms)
    - GPU memory usage
    - Dropped frames
    """
    
    def __init__(self, window_size: int = 100):
        """
        Initialize performance monitor.
        
        Args:
            window_size: Number of frames to average over
        """
        self.window_size = window_size
        self.frame_times = deque(maxlen=window_size)
        self.latencies = deque(maxlen=window_size)
        self.dropped_frames = 0
        self.total_frames = 0
        self._last_time = None
    
    def start_frame(self) -> None:
        """Mark start of frame processing."""
        self._last_time = time.perf_counter()
    
    def end_frame(self) -> None:
        """Mark end of frame processing."""
        if self._last_time is None:
            return
        
        now = time.perf_counter()
        latency_ms = (now - self._last_time) * 1000
        
        self.latencies.append(latency_ms)
        self.frame_times.append(now)
        self.total_frames += 1
        
        self._last_time = None
    
    def get_fps(self) -> float:
        """
        Get current frame rate (FPS).
        
        Returns:
            FPS (frames per second)
        """
        if len(self.frame_times) < 2:
            return 0.0
        
        elapsed = self.frame_times[-1] - self.frame_times[0]
        if elapsed == 0:
            return 0.0
        
        return (len(self.frame_times) - 1) / elapsed
    
    def get_latency_ms(self) -> Dict[str, float]:
        """
        Get latency statistics.
        
        Returns:
            Dictionary with mean, min, max latency (ms)
        """
        if len(self.latencies) == 0:
            return {'mean': 0.0, 'min': 0.0, 'max': 0.0}
        
        import numpy as np
        latencies_array = np.array(self.latencies)
        
        return {
            'mean': float(np.mean(latencies_array)),
            'min': float(np.min(latencies_array)),
            'max': float(np.max(latencies_array)),
        }
    
    def get_gpu_memory_mb(self) -> Dict[str, float]:
        """
        Get GPU memory usage.
        
        Returns:
            Dictionary with allocated, free memory (MB)
        """
        mempool = cp.get_default_memory_pool()
        
        return {
            'used_mb': mempool.used_bytes() / 1024**2,
            'total_mb': mempool.total_bytes() / 1024**2,
        }
    
    def get_summary(self) -> Dict[str, any]:
        """
        Get performance summary.
        
        Returns:
            Dictionary with all metrics
        """
        return {
            'fps': self.get_fps(),
            'latency_ms': self.get_latency_ms(),
            'gpu_memory_mb': self.get_gpu_memory_mb(),
            'total_frames': self.total_frames,
            'dropped_frames': self.dropped_frames,
        }
    
    def print_summary(self) -> None:
        """Print performance summary to console."""
        summary = self.get_summary()
        
        print("\n" + "="*60)
        print("Performance Summary")
        print("="*60)
        print(f"FPS:              {summary['fps']:.2f}")
        print(f"Latency (ms):     mean={summary['latency_ms']['mean']:.2f}, "
              f"min={summary['latency_ms']['min']:.2f}, "
              f"max={summary['latency_ms']['max']:.2f}")
        print(f"GPU Memory (MB):  used={summary['gpu_memory_mb']['used_mb']:.2f}, "
              f"total={summary['gpu_memory_mb']['total_mb']:.2f}")
        print(f"Total Frames:     {summary['total_frames']}")
        print(f"Dropped Frames:   {summary['dropped_frames']}")
        print("="*60 + "\n")

