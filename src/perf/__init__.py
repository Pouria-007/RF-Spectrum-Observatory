"""
Performance module: RMM, metrics, benchmarks.
"""

from .rmm import setup_rmm_pool, get_rmm_stats, RMM_AVAILABLE
from .metrics import PerformanceMonitor
from .bench import benchmark_fft, benchmark_dsp_pipeline, run_all_benchmarks

__all__ = [
    'setup_rmm_pool',
    'get_rmm_stats',
    'RMM_AVAILABLE',
    'PerformanceMonitor',
    'benchmark_fft',
    'benchmark_dsp_pipeline',
    'run_all_benchmarks',
]


