"""
Core data types for RF Spectrum Observatory.

All types use dataclasses for clarity and are GPU-aware (CuPy arrays).
"""

from dataclasses import dataclass, field
from typing import Optional, List
import cupy as cp
import numpy as np


@dataclass
class IQFrame:
    """
    A single IQ sample frame from the SDR (or synthetic source).
    
    Attributes:
        frame_id: Unique frame identifier (monotonically increasing)
        timestamp_ns: Nanosecond-precision timestamp
        center_freq_hz: RF center frequency
        sample_rate_sps: Samples per second
        gain_db: Receiver gain (None if not applicable)
        iq: Complex IQ samples (GPU array, complex64)
    """
    frame_id: int
    timestamp_ns: int
    center_freq_hz: float
    sample_rate_sps: float
    gain_db: Optional[float]
    iq: cp.ndarray  # shape: (N,), dtype: complex64
    
    def __post_init__(self):
        """Validate IQ array."""
        assert self.iq.dtype == cp.complex64, f"IQ must be complex64, got {self.iq.dtype}"
        assert self.iq.ndim == 1, f"IQ must be 1D, got shape {self.iq.shape}"


@dataclass
class GPSFix:
    """
    A GPS position fix.
    
    Attributes:
        gps_timestamp_ns: GPS timestamp (nanoseconds)
        lat_deg: Latitude in decimal degrees
        lon_deg: Longitude in decimal degrees
        alt_m: Altitude in meters (None if unavailable)
        heading_deg: Heading in degrees (0=North, 90=East, None if unavailable)
        speed_mps: Speed in meters per second (None if unavailable)
    """
    gps_timestamp_ns: int
    lat_deg: float
    lon_deg: float
    alt_m: Optional[float] = None
    heading_deg: Optional[float] = None
    speed_mps: Optional[float] = None
    
    def __post_init__(self):
        """Validate coordinates."""
        assert -90 <= self.lat_deg <= 90, f"Invalid latitude: {self.lat_deg}"
        assert -180 <= self.lon_deg <= 180, f"Invalid longitude: {self.lon_deg}"


@dataclass
class FrameFeatures:
    """
    DSP features extracted from a single IQ frame.
    
    Attributes:
        frame_id: Corresponding IQFrame.frame_id
        timestamp_ns: Frame timestamp
        lat_deg: GPS latitude (if aligned)
        lon_deg: GPS longitude (if aligned)
        
        # Spectral features
        freq_bins_hz: Frequency bins (GPU array, float32)
        psd_db: Power spectral density in dB (GPU array, float32)
        psd_smoothed_db: EMA-smoothed PSD (GPU array, float32)
        noise_floor_db: Estimated noise floor (scalar)
        
        # Band metrics
        bandpower_db: List of bandpower values per band (host list of floats)
        occupancy_pct: List of occupancy percentages per band (host list of floats)
        
        # Anomaly (optional)
        anomaly_score: Optional anomaly score (0-1, higher = more anomalous)
    """
    frame_id: int
    timestamp_ns: int
    lat_deg: Optional[float]
    lon_deg: Optional[float]
    
    freq_bins_hz: cp.ndarray  # shape: (fft_size//2,), dtype: float32
    psd_db: cp.ndarray        # shape: (fft_size//2,), dtype: float32
    psd_smoothed_db: cp.ndarray  # shape: (fft_size//2,), dtype: float32
    noise_floor_db: float
    
    bandpower_db: List[float] = field(default_factory=list)
    occupancy_pct: List[float] = field(default_factory=list)
    
    anomaly_score: Optional[float] = None
    
    def to_host(self) -> dict:
        """Convert GPU arrays to host for export."""
        return {
            'frame_id': self.frame_id,
            'timestamp_ns': self.timestamp_ns,
            'lat_deg': self.lat_deg,
            'lon_deg': self.lon_deg,
            'freq_bins_hz': cp.asnumpy(self.freq_bins_hz),
            'psd_db': cp.asnumpy(self.psd_db),
            'psd_smoothed_db': cp.asnumpy(self.psd_smoothed_db),
            'noise_floor_db': self.noise_floor_db,
            'bandpower_db': self.bandpower_db,
            'occupancy_pct': self.occupancy_pct,
            'anomaly_score': self.anomaly_score,
        }


@dataclass
class TileMetrics:
    """
    Aggregated metrics for a spatial tile.
    
    Attributes:
        tile_id: Unique tile identifier (e.g., "tile_x10_y20")
        tile_x: Tile grid X coordinate
        tile_y: Tile grid Y coordinate
        
        # Geospatial bounds
        lat_min: Minimum latitude
        lat_max: Maximum latitude
        lon_min: Minimum longitude
        lon_max: Maximum longitude
        
        # Aggregated metrics
        frame_count: Number of frames contributing to this tile
        timestamp_min_ns: Earliest timestamp
        timestamp_max_ns: Latest timestamp
        
        bandpower_mean_db: Mean bandpower (list per band)
        bandpower_max_db: Max bandpower (list per band)
        occupancy_mean_pct: Mean occupancy (list per band)
        
        anomaly_score_max: Max anomaly score (optional)
    """
    tile_id: str
    tile_x: int
    tile_y: int
    
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    
    frame_count: int
    timestamp_min_ns: int
    timestamp_max_ns: int
    
    bandpower_mean_db: List[float] = field(default_factory=list)
    bandpower_max_db: List[float] = field(default_factory=list)
    occupancy_mean_pct: List[float] = field(default_factory=list)
    
    anomaly_score_max: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame export."""
        return {
            'tile_id': self.tile_id,
            'tile_x': self.tile_x,
            'tile_y': self.tile_y,
            'lat_min': self.lat_min,
            'lat_max': self.lat_max,
            'lon_min': self.lon_min,
            'lon_max': self.lon_max,
            'frame_count': self.frame_count,
            'timestamp_min_ns': self.timestamp_min_ns,
            'timestamp_max_ns': self.timestamp_max_ns,
            'bandpower_mean_db': self.bandpower_mean_db,
            'bandpower_max_db': self.bandpower_max_db,
            'occupancy_mean_pct': self.occupancy_mean_pct,
            'anomaly_score_max': self.anomaly_score_max,
        }


@dataclass
class Band:
    """Frequency band definition."""
    name: str
    start_hz: float
    end_hz: float
    
    def contains(self, freq_hz: float) -> bool:
        """Check if frequency is in band."""
        return self.start_hz <= freq_hz <= self.end_hz
    
    def __post_init__(self):
        """Validate band."""
        assert self.start_hz < self.end_hz, f"Invalid band: {self.start_hz} >= {self.end_hz}"

