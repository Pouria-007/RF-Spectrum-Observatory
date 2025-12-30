"""
System status utilities: GPU detection, memory stats, pipeline health.
"""

import cupy as cp
from typing import Dict, Tuple, Optional
import time


def get_gpu_status() -> Dict[str, any]:
    """
    Get GPU system status.
    
    Returns:
        Dictionary with GPU info:
            - gpu_available: bool
            - gpu_count: int
            - gpu_name: str (if available)
            - gpu_memory_total_gb: float
            - gpu_memory_used_gb: float
            - gpu_memory_free_gb: float
    """
    status = {
        'gpu_available': False,
        'gpu_count': 0,
        'gpu_name': 'N/A',
        'gpu_memory_total_gb': 0.0,
        'gpu_memory_used_gb': 0.0,
        'gpu_memory_free_gb': 0.0,
    }
    
    try:
        # Check GPU availability
        gpu_count = cp.cuda.runtime.getDeviceCount()
        status['gpu_available'] = gpu_count > 0
        status['gpu_count'] = gpu_count
        
        if gpu_count > 0:
            # Get device properties
            device = cp.cuda.Device(0)
            props = cp.cuda.runtime.getDeviceProperties(0)
            status['gpu_name'] = props['name'].decode('utf-8')
            
            # Get memory info
            mempool = cp.get_default_memory_pool()
            used_bytes = mempool.used_bytes()
            total_bytes = mempool.total_bytes()
            
            # Also get device memory
            free_mem, total_mem = cp.cuda.runtime.memGetInfo()
            
            status['gpu_memory_total_gb'] = total_mem / 1024**3
            status['gpu_memory_used_gb'] = (total_mem - free_mem) / 1024**3
            status['gpu_memory_free_gb'] = free_mem / 1024**3
    
    except Exception as e:
        status['error'] = str(e)
    
    return status


def get_rmm_status() -> Dict[str, any]:
    """
    Get RMM pool status.
    
    Returns:
        Dictionary with RMM info
    """
    try:
        from perf import get_rmm_stats, RMM_AVAILABLE
        
        if not RMM_AVAILABLE:
            return {'enabled': False, 'reason': 'RMM not available'}
        
        stats = get_rmm_stats()
        if 'error' in stats:
            return {'enabled': True, 'reason': f'Stats unavailable: {stats["error"]}'}
        
        return {
            'enabled': True,
            'allocated_gb': stats.get('allocated_gb', 0),
            'free_gb': stats.get('free_gb', 0),
        }
    except Exception as e:
        return {'enabled': False, 'reason': str(e)}


class PipelineHealthMonitor:
    """
    Monitor pipeline health across modules.
    
    Tracks last update times and status per module.
    """
    
    def __init__(self):
        self.last_frame_time = None
        self.last_gps_time = None
        self.last_dsp_time = None
        self.last_tile_time = None
        self.last_ui_time = None
        
        self.frame_count_last = 0
        self.tile_count_last = 0
    
    def update_iq_source(self, frame_count: int):
        """Update IQ source status."""
        self.last_frame_time = time.time()
        self.frame_count_last = frame_count
    
    def update_gps_source(self, has_valid_fix: bool):
        """Update GPS source status."""
        if has_valid_fix:
            self.last_gps_time = time.time()
    
    def update_dsp(self, has_features: bool):
        """Update DSP status."""
        if has_features:
            self.last_dsp_time = time.time()
    
    def update_geo(self, tile_count: int):
        """Update geo aggregation status."""
        if tile_count > 0:
            self.last_tile_time = time.time()
            self.tile_count_last = tile_count
    
    def update_ui(self):
        """Update UI render status."""
        self.last_ui_time = time.time()
    
    def get_health_status(self) -> Dict[str, Tuple[str, str]]:
        """
        Get health status for all modules.
        
        Returns:
            Dict mapping module name to (status, message)
            where status is 'green', 'yellow', or 'red'
        """
        now = time.time()
        timeout = 5.0  # seconds
        
        health = {}
        
        # IQ Source
        if self.last_frame_time is None:
            health['IQ Source'] = ('red', 'Not started')
        elif now - self.last_frame_time > timeout:
            health['IQ Source'] = ('yellow', 'Stalled')
        else:
            health['IQ Source'] = ('green', f'{self.frame_count_last} frames')
        
        # GPS Source
        if self.last_gps_time is None:
            health['GPS Source'] = ('yellow', 'No fix yet')
        elif now - self.last_gps_time > timeout:
            health['GPS Source'] = ('yellow', 'Fix stale')
        else:
            health['GPS Source'] = ('green', 'Valid fixes')
        
        # DSP
        if self.last_dsp_time is None:
            health['DSP Pipeline'] = ('red', 'Not processing')
        elif now - self.last_dsp_time > timeout:
            health['DSP Pipeline'] = ('yellow', 'Stalled')
        else:
            health['DSP Pipeline'] = ('green', 'PSD computed')
        
        # Geo Aggregation
        if self.last_tile_time is None:
            health['Geo Aggregation'] = ('yellow', 'Buffering...')
        elif self.tile_count_last == 0:
            health['Geo Aggregation'] = ('yellow', 'No tiles yet')
        else:
            health['Geo Aggregation'] = ('green', f'{self.tile_count_last} tiles')
        
        # UI
        if self.last_ui_time is None:
            health['UI Rendering'] = ('red', 'Not rendering')
        elif now - self.last_ui_time > timeout:
            health['UI Rendering'] = ('yellow', 'Refresh slow')
        else:
            health['UI Rendering'] = ('green', 'Active')
        
        return health

