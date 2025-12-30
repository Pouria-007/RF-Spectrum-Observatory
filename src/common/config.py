"""
Configuration loader and validator.
"""

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from .types import Band


@dataclass
class RFConfig:
    """RF parameters."""
    center_freq_hz: float
    sample_rate_sps: float
    bandwidth_hz: float
    gain_db: float
    fft_size: int
    window_type: str


@dataclass
class DSPConfig:
    """DSP pipeline parameters."""
    frames_per_batch: int
    smoothing_factor: float
    welch_segments: int
    noise_floor_percentile: float
    bands: List[Band]


@dataclass
class GeoConfig:
    """Geospatial parameters."""
    map_center_lat: float
    map_center_lon: float
    tile_size_meters: float
    grid_extent_meters: float
    aggregate_window_frames: int


@dataclass
class SyntheticConfig:
    """Synthetic data generation parameters."""
    iq: Dict[str, Any]
    gps: Dict[str, Any]
    maps: Dict[str, Any]


@dataclass
class PerformanceConfig:
    """Performance/GPU settings."""
    rmm_pool_size_gb: Optional[float]
    update_rate_hz: float
    max_frames_buffer: int
    enable_profiling: bool
    frames_per_refresh: int = 5  # Default: process 5 frames per UI refresh


@dataclass
class UIConfig:
    """UI settings."""
    streamlit_port: int
    theme: str
    spectrum: Dict[str, Any]
    waterfall: Dict[str, Any]
    map: Dict[str, Any]


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str
    format: str
    log_file: str


@dataclass
class Config:
    """
    Top-level configuration object.
    
    Loaded from YAML and validated on instantiation.
    """
    project: Dict[str, Any]
    rf: RFConfig
    dsp: DSPConfig
    geo: GeoConfig
    synthetic: SyntheticConfig
    performance: PerformanceConfig
    ui: UIConfig
    logging: LoggingConfig
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> "Config":
        """
        Load configuration from YAML file.
        
        Args:
            yaml_path: Path to YAML config file
            
        Returns:
            Config object
        """
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {yaml_path}")
        
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Parse bands
        bands = [Band(**b) for b in data['dsp']['bands']]
        
        return cls(
            project=data['project'],
            rf=RFConfig(**data['rf']),
            dsp=DSPConfig(
                frames_per_batch=data['dsp']['frames_per_batch'],
                smoothing_factor=data['dsp']['smoothing_factor'],
                welch_segments=data['dsp']['welch_segments'],
                noise_floor_percentile=data['dsp']['noise_floor_percentile'],
                bands=bands,
            ),
            geo=GeoConfig(**data['geo']),
            synthetic=SyntheticConfig(**data['synthetic']),
            performance=PerformanceConfig(**data['performance']),
            ui=UIConfig(**data['ui']),
            logging=LoggingConfig(**data['logging']),
        )
    
    def validate(self) -> None:
        """
        Validate configuration constraints.
        
        Raises:
            ValueError: If configuration is invalid
        """
        # RF validation
        if self.rf.fft_size & (self.rf.fft_size - 1) != 0:
            raise ValueError(f"fft_size must be power of 2, got {self.rf.fft_size}")
        
        if self.rf.window_type not in ['hann', 'hamming', 'blackman']:
            raise ValueError(f"Invalid window_type: {self.rf.window_type}")
        
        # DSP validation
        if not 0 < self.dsp.smoothing_factor <= 1:
            raise ValueError(f"smoothing_factor must be in (0, 1], got {self.dsp.smoothing_factor}")
        
        # Geo validation
        if self.geo.tile_size_meters <= 0:
            raise ValueError(f"tile_size_meters must be positive, got {self.geo.tile_size_meters}")
        
        # Performance validation
        if self.performance.update_rate_hz <= 0:
            raise ValueError(f"update_rate_hz must be positive, got {self.performance.update_rate_hz}")


def load_config(yaml_path: str = "config/default.yaml") -> Config:
    """
    Load and validate configuration.
    
    Args:
        yaml_path: Path to YAML config file
        
    Returns:
        Validated Config object
    """
    config = Config.from_yaml(yaml_path)
    config.validate()
    return config

