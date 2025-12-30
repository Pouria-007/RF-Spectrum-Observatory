"""
Smoothing: Exponential Moving Average (EMA) and Welch's method.
"""

import cupy as cp
from typing import Optional


class EMAFilter:
    """
    Exponential Moving Average filter for PSD smoothing.
    
    Maintains state across frames (GPU array).
    """
    
    def __init__(self, alpha: float, size: int):
        """
        Initialize EMA filter.
        
        Args:
            alpha: Smoothing factor (0=full smoothing, 1=no smoothing)
            size: Filter size (number of bins)
        """
        self.alpha = alpha
        self.size = size
        self._state: Optional[cp.ndarray] = None
    
    def update(self, new_value: cp.ndarray) -> cp.ndarray:
        """
        Update EMA with new value.
        
        Args:
            new_value: New PSD value (GPU, float32)
            
        Returns:
            Smoothed PSD (GPU, float32)
        """
        if self._state is None:
            # Initialize with first value
            self._state = new_value.copy()
            return self._state
        
        # EMA update: state = alpha * new + (1 - alpha) * state
        self._state = self.alpha * new_value + (1 - self.alpha) * self._state
        return self._state
    
    def reset(self) -> None:
        """Reset filter state."""
        self._state = None
    
    def get_state(self) -> Optional[cp.ndarray]:
        """Get current state."""
        return self._state


def welch_psd(
    signals: cp.ndarray,
    window: cp.ndarray,
    sample_rate_sps: float,
    num_segments: int
) -> cp.ndarray:
    """
    Welch's method: average PSD over overlapping segments.
    
    Args:
        signals: 2D array of signals (GPU, complex64), shape: (num_frames, fft_size)
        window: Window function (GPU, float32)
        sample_rate_sps: Sample rate
        num_segments: Number of segments to average
        
    Returns:
        Averaged PSD (GPU, float32)
    """
    # For simplicity, just average PSDs from multiple frames
    # (True Welch would use overlapping segments within a single long capture)
    
    from .fft_psd import compute_fft, compute_psd
    
    psd_accumulator = None
    
    for i in range(min(num_segments, signals.shape[0])):
        windowed = signals[i] * window
        fft_result = compute_fft(windowed)
        _, psd_linear = compute_psd(fft_result, sample_rate_sps)
        
        if psd_accumulator is None:
            psd_accumulator = psd_linear
        else:
            psd_accumulator += psd_linear
    
    return psd_accumulator / num_segments

