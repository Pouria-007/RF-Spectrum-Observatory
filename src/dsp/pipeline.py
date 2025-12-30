"""
GPU DSP pipeline: FFT, PSD, smoothing, features.
"""

import cupy as cp
from typing import Optional, List

from common.types import IQFrame, FrameFeatures, Band, GPSFix
from common.timebase import align_gps_to_iq
from dsp.windows import get_window
from dsp.fft_psd import compute_fft_psd
from dsp.smoothing import EMAFilter
from dsp.features import estimate_noise_floor, extract_band_features


class DSPPipeline:
    """
    GPU-accelerated DSP pipeline.
    
    Processes IQFrame → FrameFeatures:
    1. Window IQ samples
    2. Compute FFT
    3. Compute PSD (linear + dB)
    4. Smooth PSD (EMA)
    5. Estimate noise floor
    6. Extract band features (bandpower, occupancy)
    7. Align GPS fix (if available)
    """
    
    def __init__(
        self,
        fft_size: int,
        window_type: str,
        smoothing_factor: float,
        noise_floor_percentile: float,
        bands: List[Band],
    ):
        """
        Initialize DSP pipeline.
        
        Args:
            fft_size: FFT size
            window_type: Window function type
            smoothing_factor: EMA alpha
            noise_floor_percentile: Percentile for noise floor estimate
            bands: List of frequency bands
        """
        self.fft_size = fft_size
        self.window_type = window_type
        self.smoothing_factor = smoothing_factor
        self.noise_floor_percentile = noise_floor_percentile
        self.bands = bands
        
        # Precompute window
        self.window = get_window(window_type, fft_size)
        self.window_power_correction = float(cp.sum(self.window ** 2))
        
        # EMA filter for smoothing
        self.ema_filter = EMAFilter(smoothing_factor, fft_size)
        
        # GPS fixes buffer (for alignment)
        self.gps_fixes: List[GPSFix] = []
    
    def add_gps_fix(self, fix: GPSFix) -> None:
        """
        Add a GPS fix to the buffer (for IQ/GPS alignment).
        
        Args:
            fix: GPS fix
        """
        self.gps_fixes.append(fix)
        
        # Keep buffer size manageable (last 100 fixes)
        if len(self.gps_fixes) > 100:
            self.gps_fixes = self.gps_fixes[-100:]
    
    def process_frame(self, frame: IQFrame) -> FrameFeatures:
        """
        Process a single IQ frame through the DSP pipeline.
        
        Args:
            frame: IQFrame with IQ samples (GPU)
            
        Returns:
            FrameFeatures with spectral features (GPU arrays + host scalars)
        """
        # 1. Compute FFT and PSD
        freq_bins, psd_db, psd_linear = compute_fft_psd(
            frame, self.window, self.window_power_correction
        )
        
        # 2. Smooth PSD (EMA)
        psd_smoothed_db = self.ema_filter.update(psd_db)
        
        # 3. Estimate noise floor
        noise_floor_db = estimate_noise_floor(psd_smoothed_db, self.noise_floor_percentile)
        
        # 4. Extract band features
        bandpower_db, occupancy_pct = extract_band_features(
            freq_bins, psd_db, psd_linear, self.bands, frame.center_freq_hz, noise_floor_db
        )
        
        # 5. Align GPS fix (if available)
        # For synthetic/fast processing, just use the most recent GPS fix
        # (timestamp alignment doesn't work when frames are generated instantly)
        lat_deg, lon_deg = None, None
        if self.gps_fixes:
            gps_fix = self.gps_fixes[-1]  # Most recent fix
            lat_deg = gps_fix.lat_deg
            lon_deg = gps_fix.lon_deg
        
        # 6. Create FrameFeatures
        features = FrameFeatures(
            frame_id=frame.frame_id,
            timestamp_ns=frame.timestamp_ns,
            lat_deg=lat_deg,
            lon_deg=lon_deg,
            freq_bins_hz=freq_bins,
            psd_db=psd_db,
            psd_smoothed_db=psd_smoothed_db,
            noise_floor_db=noise_floor_db,
            bandpower_db=bandpower_db,
            occupancy_pct=occupancy_pct,
        )
        
        return features
    
    def reset(self) -> None:
        """Reset pipeline state (EMA filter, GPS buffer)."""
        self.ema_filter.reset()
        self.gps_fixes = []


def create_pipeline_from_config(config) -> DSPPipeline:
    """
    Create DSP pipeline from configuration.
    
    Args:
        config: Config object
        
    Returns:
        Initialized DSPPipeline
    """
    return DSPPipeline(
        fft_size=config.rf.fft_size,
        window_type=config.rf.window_type,
        smoothing_factor=config.dsp.smoothing_factor,
        noise_floor_percentile=config.dsp.noise_floor_percentile,
        bands=config.dsp.bands,
    )

