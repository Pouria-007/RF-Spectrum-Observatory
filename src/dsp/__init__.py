"""
DSP module: GPU-accelerated spectral analysis.
"""

from .windows import get_window, apply_window
from .fft_psd import compute_fft, compute_psd, compute_fft_psd, linear_to_db
from .smoothing import EMAFilter, welch_psd
from .features import estimate_noise_floor, compute_bandpower, compute_occupancy, extract_band_features
from .pipeline import DSPPipeline, create_pipeline_from_config

__all__ = [
    'get_window',
    'apply_window',
    'compute_fft',
    'compute_psd',
    'compute_fft_psd',
    'linear_to_db',
    'EMAFilter',
    'welch_psd',
    'estimate_noise_floor',
    'compute_bandpower',
    'compute_occupancy',
    'extract_band_features',
    'DSPPipeline',
    'create_pipeline_from_config',
]

