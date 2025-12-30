"""
Hardware detection and unified interface.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class HardwareDevice:
    """Detected hardware device."""
    device_type: str  # 'rtlsdr', 'usrp', 'synthetic'
    name: str
    index: Optional[int] = None
    args: Optional[str] = None
    max_sample_rate: Optional[float] = None
    freq_range: Optional[tuple] = None  # (min_hz, max_hz)


def detect_all_hardware() -> List[HardwareDevice]:
    """
    Detect all available RF hardware.
    
    Returns:
        List of HardwareDevice objects
    """
    devices = []
    
    # Always available: Synthetic
    devices.append(HardwareDevice(
        device_type='synthetic',
        name='Synthetic IQ Generator (5G-like)',
        max_sample_rate=100e6,
        freq_range=(0, 10e9),
    ))
    
    # Try RTL-SDR
    try:
        from ingest.iq_rtlsdr import detect_rtlsdr_devices, RTLSDR_AVAILABLE
        if RTLSDR_AVAILABLE:
            rtl_devices = detect_rtlsdr_devices()
            for rtl in rtl_devices:
                devices.append(HardwareDevice(
                    device_type='rtlsdr',
                    name=rtl['name'],
                    index=rtl['index'],
                    max_sample_rate=3.2e6,
                    freq_range=(24e6, 1766e6),
                ))
    except Exception as e:
        pass  # RTL-SDR not available
    
    # Try USRP
    try:
        from ingest.iq_usrp import detect_usrp_devices, USRP_AVAILABLE
        if USRP_AVAILABLE:
            usrp_devices = detect_usrp_devices()
            for usrp in usrp_devices:
                devices.append(HardwareDevice(
                    device_type='usrp',
                    name=usrp['name'],
                    args=usrp['args'],
                    max_sample_rate=100e6,
                    freq_range=(0, 6e9),
                ))
    except Exception as e:
        pass  # USRP not available
    
    return devices


def create_iq_source(device: HardwareDevice, center_freq_hz: float, sample_rate_sps: float, frame_size: int = None):
    """
    Create IQ source from hardware device.
    
    Args:
        device: HardwareDevice object
        center_freq_hz: Center frequency
        sample_rate_sps: Sample rate
        frame_size: Samples per frame (optional, uses default if None)
        
    Returns:
        IQ source instance
    """
    if frame_size is None:
        frame_size = 2048  # Default frame size
    
    if device.device_type == 'synthetic':
        from ingest.iq_synthetic import SyntheticIQSource
        return SyntheticIQSource(
            center_freq_hz=center_freq_hz,
            sample_rate_sps=sample_rate_sps,
            fft_size=frame_size
        )
    
    elif device.device_type == 'rtlsdr':
        from ingest.iq_rtlsdr import RTLSDRSource, RTLSDRConfig
        config = RTLSDRConfig(
            device_index=device.index,
            center_freq_hz=center_freq_hz,
            sample_rate_sps=sample_rate_sps,
        )
        return RTLSDRSource(config, frame_size)
    
    elif device.device_type == 'usrp':
        from ingest.iq_usrp import USRPSource, USRPConfig
        config = USRPConfig(
            device_args=device.args or "",
            center_freq_hz=center_freq_hz,
            sample_rate_sps=sample_rate_sps,
        )
        return USRPSource(config, frame_size)
    
    else:
        raise ValueError(f"Unknown device type: {device.device_type}")


