"""
Microbenchmarks for DSP pipeline components.
"""

import time
import cupy as cp
import numpy as np
from typing import Dict

from common import load_config
from ingest import SyntheticIQSource
from dsp import create_pipeline_from_config


def benchmark_fft(fft_size: int, num_iterations: int = 1000) -> Dict[str, float]:
    """
    Benchmark FFT performance.
    
    Args:
        fft_size: FFT size
        num_iterations: Number of iterations
        
    Returns:
        Dictionary with timing results
    """
    # Generate data
    data = cp.random.randn(fft_size).astype(cp.complex64)
    
    # Warmup
    for _ in range(10):
        cp.fft.fft(data)
    cp.cuda.Stream.null.synchronize()
    
    # Benchmark
    start = time.perf_counter()
    for _ in range(num_iterations):
        cp.fft.fft(data)
    cp.cuda.Stream.null.synchronize()
    end = time.perf_counter()
    
    elapsed_ms = (end - start) * 1000
    
    return {
        'total_ms': elapsed_ms,
        'per_fft_ms': elapsed_ms / num_iterations,
        'throughput_ffts_per_sec': num_iterations / (end - start),
    }


def benchmark_dsp_pipeline(num_frames: int = 100) -> Dict[str, any]:
    """
    Benchmark full DSP pipeline.
    
    Args:
        num_frames: Number of frames to process
        
    Returns:
        Dictionary with timing results
    """
    # Load config
    config = load_config('config/default.yaml')
    
    # Create IQ source
    iq_source = SyntheticIQSource(
        center_freq_hz=config.rf.center_freq_hz,
        sample_rate_sps=config.rf.sample_rate_sps,
        fft_size=config.rf.fft_size,
        num_carriers=5,
        carrier_bw_hz=10e6,
        carrier_power_db=-30,
        noise_floor_db=-80,
    )
    iq_source.start()
    
    # Create DSP pipeline
    pipeline = create_pipeline_from_config(config)
    
    # Warmup
    for _ in range(10):
        frame = iq_source.get_frame()
        pipeline.process_frame(frame)
    
    # Benchmark
    start = time.perf_counter()
    for _ in range(num_frames):
        frame = iq_source.get_frame()
        features = pipeline.process_frame(frame)
    cp.cuda.Stream.null.synchronize()
    end = time.perf_counter()
    
    elapsed_ms = (end - start) * 1000
    
    iq_source.stop()
    
    return {
        'total_ms': elapsed_ms,
        'per_frame_ms': elapsed_ms / num_frames,
        'throughput_fps': num_frames / (end - start),
    }


def run_all_benchmarks() -> None:
    """Run all benchmarks and print results."""
    print("\n" + "="*60)
    print("GPU DSP Pipeline Benchmarks")
    print("="*60 + "\n")
    
    # FFT benchmark
    print("FFT Benchmark (4096-point):")
    fft_results = benchmark_fft(fft_size=4096, num_iterations=1000)
    print(f"  Per FFT:     {fft_results['per_fft_ms']:.3f} ms")
    print(f"  Throughput:  {fft_results['throughput_ffts_per_sec']:.0f} FFTs/sec")
    print()
    
    # DSP pipeline benchmark
    print("Full DSP Pipeline Benchmark (100 frames):")
    pipeline_results = benchmark_dsp_pipeline(num_frames=100)
    print(f"  Per Frame:   {pipeline_results['per_frame_ms']:.3f} ms")
    print(f"  Throughput:  {pipeline_results['throughput_fps']:.1f} FPS")
    print()
    
    print("="*60 + "\n")


if __name__ == '__main__':
    run_all_benchmarks()

