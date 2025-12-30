"""
GPU FFT and PSD computation using CuPy.
"""

import cupy as cp
from typing import Tuple

from common.types import IQFrame


def compute_fft(signal: cp.ndarray) -> cp.ndarray:
    """
    Compute FFT of complex signal.
    
    Args:
        signal: Complex signal (GPU, complex64)
        
    Returns:
        FFT result (GPU, complex64)
    """
    return cp.fft.fft(signal)


def compute_psd(
    fft_result: cp.ndarray,
    sample_rate_sps: float,
    window_power_correction: float = 1.0
) -> Tuple[cp.ndarray, cp.ndarray]:
    """
    Compute power spectral density from FFT.
    
    Args:
        fft_result: FFT output (GPU, complex64)
        sample_rate_sps: Sample rate (samples/sec)
        window_power_correction: Power correction factor for window (e.g., sum(window**2))
        
    Returns:
        Tuple of:
            - freq_bins: Frequency bins (GPU, float32), Hz
            - psd_linear: PSD in linear scale (GPU, float32), W/Hz
    """
    N = len(fft_result)
    
    # Compute power (magnitude squared)
    power = cp.abs(fft_result) ** 2
    
    # Normalize by FFT size and sample rate
    psd_linear = power / (N * sample_rate_sps * window_power_correction)
    
    # Frequency bins (centered around 0)
    freq_bins = cp.fft.fftfreq(N, d=1.0/sample_rate_sps).astype(cp.float32)
    
    # Shift to center DC at 0
    psd_linear = cp.fft.fftshift(psd_linear)
    freq_bins = cp.fft.fftshift(freq_bins)
    
    return freq_bins, psd_linear


def linear_to_db(linear: cp.ndarray, floor_db: float = -120) -> cp.ndarray:
    """
    Convert linear power to dB scale with floor.
    
    Args:
        linear: Linear power (GPU, float32)
        floor_db: Minimum dB value (floor for log)
        
    Returns:
        Power in dB (GPU, float32)
    """
    floor_linear = 10 ** (floor_db / 10)
    linear_clipped = cp.maximum(linear, floor_linear)
    return 10 * cp.log10(linear_clipped)


def compute_fft_psd(
    frame: IQFrame,
    window: cp.ndarray,
    window_power_correction: float
) -> Tuple[cp.ndarray, cp.ndarray, cp.ndarray]:
    """
    End-to-end: window → FFT → PSD (dB).
    
    Args:
        frame: IQFrame with complex samples
        window: Window function (GPU, float32)
        window_power_correction: Window power correction factor
        
    Returns:
        Tuple of:
            - freq_bins: Frequency bins (GPU, float32), Hz (relative to baseband)
            - psd_db: PSD in dB (GPU, float32)
            - psd_linear: PSD in linear scale (GPU, float32)
    """
    # Apply window
    windowed = frame.iq * window
    
    # FFT
    fft_result = compute_fft(windowed)
    
    # PSD
    freq_bins, psd_linear = compute_psd(fft_result, frame.sample_rate_sps, window_power_correction)
    psd_db = linear_to_db(psd_linear)
    
    return freq_bins, psd_db, psd_linear

