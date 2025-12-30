"""
GPU telemetry collection using NVML (pynvml) with nvidia-smi fallback.
"""

import subprocess
import json
from typing import Dict, Optional, Any
from dataclasses import dataclass
import psutil

# Try to import pynvml
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None


@dataclass
class GPUMetrics:
    """GPU performance metrics."""
    gpu_name: str
    driver_version: str
    gpu_utilization_pct: Optional[float]
    memory_utilization_pct: Optional[float]
    memory_used_gb: Optional[float]
    memory_total_gb: Optional[float]
    memory_free_gb: Optional[float]
    temperature_c: Optional[float]
    power_draw_w: Optional[float]
    power_limit_w: Optional[float]
    available: bool = True


class GPUTelemetry:
    """Collect GPU metrics using NVML or nvidia-smi fallback."""
    
    def __init__(self, gpu_index: int = 0):
        self.gpu_index = gpu_index
        self.use_pynvml = PYNVML_AVAILABLE
        self.nvml_initialized = False
        
        if self.use_pynvml:
            try:
                pynvml.nvmlInit()
                self.nvml_initialized = True
                self.handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            except Exception as e:
                print(f"NVML initialization failed: {e}. Falling back to nvidia-smi.")
                self.use_pynvml = False
    
    def get_metrics(self) -> GPUMetrics:
        """Get current GPU metrics."""
        if self.use_pynvml and self.nvml_initialized:
            return self._get_metrics_nvml()
        else:
            return self._get_metrics_nvidia_smi()
    
    def _get_metrics_nvml(self) -> GPUMetrics:
        """Get metrics using pynvml (fast)."""
        try:
            name = pynvml.nvmlDeviceGetName(self.handle)
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            
            driver_version = pynvml.nvmlSystemGetDriverVersion()
            if isinstance(driver_version, bytes):
                driver_version = driver_version.decode('utf-8')
            
            # Utilization
            util = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
            gpu_util = float(util.gpu)
            mem_util = float(util.memory)
            
            # Memory
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
            mem_used_gb = mem_info.used / (1024**3)
            mem_total_gb = mem_info.total / (1024**3)
            mem_free_gb = mem_info.free / (1024**3)
            
            # Temperature
            temp_c = float(pynvml.nvmlDeviceGetTemperature(self.handle, pynvml.NVML_TEMPERATURE_GPU))
            
            # Power
            try:
                power_draw_w = pynvml.nvmlDeviceGetPowerUsage(self.handle) / 1000.0  # mW to W
                power_limit_w = pynvml.nvmlDeviceGetPowerManagementLimit(self.handle) / 1000.0
            except:
                power_draw_w = None
                power_limit_w = None
            
            return GPUMetrics(
                gpu_name=name,
                driver_version=driver_version,
                gpu_utilization_pct=gpu_util,
                memory_utilization_pct=mem_util,
                memory_used_gb=mem_used_gb,
                memory_total_gb=mem_total_gb,
                memory_free_gb=mem_free_gb,
                temperature_c=temp_c,
                power_draw_w=power_draw_w,
                power_limit_w=power_limit_w,
                available=True,
            )
        except Exception as e:
            print(f"Error getting NVML metrics: {e}")
            return self._get_unavailable_metrics()
    
    def _get_metrics_nvidia_smi(self) -> GPUMetrics:
        """Get metrics using nvidia-smi command (slower fallback)."""
        try:
            result = subprocess.run(
                [
                    'nvidia-smi',
                    '--query-gpu=name,driver_version,utilization.gpu,utilization.memory,'
                    'memory.used,memory.total,memory.free,temperature.gpu,power.draw,power.limit',
                    '--format=csv,noheader,nounits',
                    f'--id={self.gpu_index}'
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            
            if result.returncode != 0:
                return self._get_unavailable_metrics()
            
            fields = [f.strip() for f in result.stdout.strip().split(',')]
            
            return GPUMetrics(
                gpu_name=fields[0],
                driver_version=fields[1],
                gpu_utilization_pct=float(fields[2]) if fields[2] not in ['N/A', ''] else None,
                memory_utilization_pct=float(fields[3]) if fields[3] not in ['N/A', ''] else None,
                memory_used_gb=float(fields[4]) / 1024.0 if fields[4] not in ['N/A', ''] else None,
                memory_total_gb=float(fields[5]) / 1024.0 if fields[5] not in ['N/A', ''] else None,
                memory_free_gb=float(fields[6]) / 1024.0 if fields[6] not in ['N/A', ''] else None,
                temperature_c=float(fields[7]) if fields[7] not in ['N/A', ''] else None,
                power_draw_w=float(fields[8]) if fields[8] not in ['N/A', ''] else None,
                power_limit_w=float(fields[9]) if fields[9] not in ['N/A', ''] else None,
                available=True,
            )
        except Exception as e:
            print(f"Error getting nvidia-smi metrics: {e}")
            return self._get_unavailable_metrics()
    
    def _get_unavailable_metrics(self) -> GPUMetrics:
        """Return placeholder metrics when GPU is not available."""
        return GPUMetrics(
            gpu_name="N/A",
            driver_version="N/A",
            gpu_utilization_pct=None,
            memory_utilization_pct=None,
            memory_used_gb=None,
            memory_total_gb=None,
            memory_free_gb=None,
            temperature_c=None,
            power_draw_w=None,
            power_limit_w=None,
            available=False,
        )
    
    def get_process_metrics(self) -> Dict[str, Any]:
        """Get Python process metrics (CPU, threads, memory)."""
        try:
            proc = psutil.Process()
            return {
                'cpu_percent': proc.cpu_percent(interval=0.1),
                'num_threads': proc.num_threads(),
                'memory_rss_mb': proc.memory_info().rss / (1024**2),
                'num_fds': proc.num_fds() if hasattr(proc, 'num_fds') else None,
            }
        except Exception as e:
            print(f"Error getting process metrics: {e}")
            return {
                'cpu_percent': None,
                'num_threads': None,
                'memory_rss_mb': None,
                'num_fds': None,
            }
    
    def __del__(self):
        """Cleanup NVML."""
        if self.use_pynvml and self.nvml_initialized:
            try:
                pynvml.nvmlShutdown()
            except:
                pass

