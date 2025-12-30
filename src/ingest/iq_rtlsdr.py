"""
Hardware IQ source: RTL-SDR integration.

Requires: pyrtlsdr (pip install pyrtlsdr)
"""

import numpy as np
import cupy as cp
from typing import Optional
from dataclasses import dataclass

from common.types import IQFrame
from common.timebase import now_ns
from ingest.iq_base import IQSourceBase

try:
    from rtlsdr import RtlSdr
    RTLSDR_AVAILABLE = True
except ImportError:
    RTLSDR_AVAILABLE = False
    RtlSdr = None


@dataclass
class RTLSDRConfig:
    """RTL-SDR configuration."""
    device_index: int = 0
    center_freq_hz: float = 3.55e9  # Note: RTL-SDR typically 24-1766 MHz
    sample_rate_sps: float = 2.4e6  # RTL-SDR max ~3.2 MS/s
    gain: str = 'auto'  # 'auto' or dB value (0-49.6)
    ppm_error: int = 0  # Frequency correction in PPM


class RTLSDRSource(IQSourceBase):
    """
    Hardware IQ source using RTL-SDR.
    
    RTL-SDR is a low-cost USB SDR (24-1766 MHz typically).
    Popular for <1 GHz work, not suitable for 5G (too high frequency).
    """
    
    def __init__(self, config: RTLSDRConfig, frame_size: int = 2048):
        """
        Initialize RTL-SDR source.
        
        Args:
            config: RTL-SDR configuration
            frame_size: Number of samples per frame
        """
        if not RTLSDR_AVAILABLE:
            raise RuntimeError("RTL-SDR not available. Install with: pip install pyrtlsdr")
        
        self.config = config
        self.frame_size = frame_size
        self.sdr: Optional[RtlSdr] = None
        self.frame_count = 0
        
        # Initialize device
        self._init_device()
    
    def _init_device(self):
        """Initialize RTL-SDR device."""
        try:
            self.sdr = RtlSdr(device_index=self.config.device_index)
            
            # Configure
            self.sdr.sample_rate = self.config.sample_rate_sps
            self.sdr.center_freq = self.config.center_freq_hz
            self.sdr.freq_correction = self.config.ppm_error
            
            # Set gain
            if self.config.gain == 'auto':
                self.sdr.gain = 'auto'
            else:
                self.sdr.gain = float(self.config.gain)
            
            print(f"✓ RTL-SDR initialized: {self.config.center_freq_hz/1e6:.2f} MHz @ {self.config.sample_rate_sps/1e6:.2f} MS/s")
        
        except Exception as e:
            raise RuntimeError(f"Failed to initialize RTL-SDR: {e}")
    
    def get_frame(self) -> IQFrame:
        """
        Read IQ frame from RTL-SDR.
        
        Returns:
            IQFrame with samples on GPU
        """
        if self.sdr is None:
            raise RuntimeError("RTL-SDR not initialized")
        
        # Read samples (returns complex64)
        samples = self.sdr.read_samples(self.frame_size)
        
        # Transfer to GPU
        samples_gpu = cp.asarray(samples, dtype=cp.complex64)
        
        # Create frame
        frame = IQFrame(
            timestamp_ns=now_ns(),
            center_freq_hz=self.config.center_freq_hz,
            sample_rate_sps=self.config.sample_rate_sps,
            samples=samples_gpu,
            frame_id=self.frame_count,
        )
        
        self.frame_count += 1
        return frame
    
    def close(self):
        """Close RTL-SDR device."""
        if self.sdr is not None:
            self.sdr.close()
            self.sdr = None
            print("✓ RTL-SDR closed")
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()


def detect_rtlsdr_devices() -> list:
    """
    Detect available RTL-SDR devices.
    
    Returns:
        List of device info dicts
    """
    if not RTLSDR_AVAILABLE:
        return []
    
    devices = []
    for idx in range(10):  # Check first 10 indices
        try:
            sdr = RtlSdr(device_index=idx)
            devices.append({
                'index': idx,
                'name': f"RTL-SDR #{idx}",
                'type': 'rtlsdr',
            })
            sdr.close()
        except:
            break  # No more devices
    
    return devices



