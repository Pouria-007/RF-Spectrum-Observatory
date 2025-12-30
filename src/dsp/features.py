"""
Feature extraction: bandpower, occupancy, noise floor estimation.
"""

import cupy as cp
from typing import List, Tuple

from common.types import Band


def estimate_noise_floor(psd_db: cp.ndarray, percentile: float = 10) -> float:
    """
    Estimate noise floor from PSD using percentile method.
    
    Args:
        psd_db: PSD in dB (GPU, float32)
        percentile: Percentile for noise floor (0-100)
        
    Returns:
        Noise floor in dB (scalar)
    """
    noise_floor = float(cp.percentile(psd_db, percentile))
    return noise_floor


def compute_bandpower(
    freq_bins: cp.ndarray,
    psd_linear: cp.ndarray,
    band: Band,
    center_freq_hz: float
) -> float:
    """
    Compute total power in a frequency band.
    
    Args:
        freq_bins: Frequency bins (GPU, float32), baseband Hz
        psd_linear: PSD in linear scale (GPU, float32)
        band: Band definition (absolute frequencies)
        center_freq_hz: RF center frequency
        
    Returns:
        Bandpower in dB
    """
    # Convert band to baseband frequencies
    band_start_baseband = band.start_hz - center_freq_hz
    band_end_baseband = band.end_hz - center_freq_hz
    
    # Find bins in band
    mask = (freq_bins >= band_start_baseband) & (freq_bins <= band_end_baseband)
    
    # Integrate power (sum of PSD values * bin width)
    bin_width = float(freq_bins[1] - freq_bins[0]) if len(freq_bins) > 1 else 1.0
    power_linear = float(cp.sum(psd_linear[mask])) * bin_width
    
    # Convert to dB
    power_db = 10 * cp.log10(cp.maximum(power_linear, 1e-12))
    return float(power_db)


def compute_occupancy(
    freq_bins: cp.ndarray,
    psd_db: cp.ndarray,
    band: Band,
    center_freq_hz: float,
    noise_floor_db: float,
    threshold_db: float = 6.0
) -> float:
    """
    Compute occupancy (fraction of bins above threshold) in a band.
    
    Args:
        freq_bins: Frequency bins (GPU, float32), baseband Hz
        psd_db: PSD in dB (GPU, float32)
        band: Band definition (absolute frequencies)
        center_freq_hz: RF center frequency
        noise_floor_db: Noise floor estimate (dB)
        threshold_db: Threshold above noise floor (dB)
        
    Returns:
        Occupancy percentage (0-100)
    """
    # Convert band to baseband
    band_start_baseband = band.start_hz - center_freq_hz
    band_end_baseband = band.end_hz - center_freq_hz
    
    # Find bins in band
    mask = (freq_bins >= band_start_baseband) & (freq_bins <= band_end_baseband)
    psd_in_band = psd_db[mask]
    
    if len(psd_in_band) == 0:
        return 0.0
    
    # Count bins above threshold
    occupied = cp.sum(psd_in_band > (noise_floor_db + threshold_db))
    total = len(psd_in_band)
    
    return float(occupied / total * 100)


def extract_band_features(
    freq_bins: cp.ndarray,
    psd_db: cp.ndarray,
    psd_linear: cp.ndarray,
    bands: List[Band],
    center_freq_hz: float,
    noise_floor_db: float
) -> Tuple[List[float], List[float]]:
    """
    Extract bandpower and occupancy for all bands.
    
    Args:
        freq_bins: Frequency bins (GPU, float32)
        psd_db: PSD in dB (GPU, float32)
        psd_linear: PSD in linear scale (GPU, float32)
        bands: List of band definitions
        center_freq_hz: RF center frequency
        noise_floor_db: Noise floor estimate (dB)
        
    Returns:
        Tuple of:
            - bandpower_db: List of bandpower values (dB)
            - occupancy_pct: List of occupancy percentages (0-100)
    """
    bandpower_db = []
    occupancy_pct = []
    
    for band in bands:
        bp = compute_bandpower(freq_bins, psd_linear, band, center_freq_hz)
        occ = compute_occupancy(freq_bins, psd_db, band, center_freq_hz, noise_floor_db)
        
        bandpower_db.append(bp)
        occupancy_pct.append(occ)
    
    return bandpower_db, occupancy_pct

