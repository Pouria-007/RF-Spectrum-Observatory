"""
GPU window functions (Hann, Hamming, Blackman) using cuSignal.
"""

import cupy as cp
import cusignal
from typing import Literal

WindowType = Literal['hann', 'hamming', 'blackman']


def get_window(window_type: WindowType, size: int) -> cp.ndarray:
    """
    Generate window function on GPU using cuSignal.
    
    Args:
        window_type: Window type ('hann', 'hamming', 'blackman')
        size: Window length
        
    Returns:
        Window array (GPU, float32)
    """
    # Use cuSignal's get_window function (GPU-accelerated)
    if window_type == 'hann':
        window = cusignal.windows.hann(size, sym=False)
    elif window_type == 'hamming':
        window = cusignal.windows.hamming(size, sym=False)
    elif window_type == 'blackman':
        window = cusignal.windows.blackman(size, sym=False)
    else:
        raise ValueError(f"Unknown window type: {window_type}")
    
    return window.astype(cp.float32)


def apply_window(signal: cp.ndarray, window: cp.ndarray) -> cp.ndarray:
    """
    Apply window to signal (element-wise multiply).
    
    Args:
        signal: Complex signal (GPU, complex64)
        window: Window function (GPU, float32)
        
    Returns:
        Windowed signal (GPU, complex64)
    """
    return signal * window

