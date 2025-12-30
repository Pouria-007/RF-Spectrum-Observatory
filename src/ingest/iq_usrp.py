"""
Hardware IQ source: USRP (Universal Software Radio Peripheral) integration.

Requires: uhd (USRP Hardware Driver) + Python bindings
Install: conda install -c ettus uhd (or from source)
"""

import numpy as np
import cupy as cp
from typing import Optional
from dataclasses import dataclass

from common.types import IQFrame
from common.timebase import now_ns
from ingest.iq_base import IQSourceBase

try:
    import uhd
    USRP_AVAILABLE = True
except ImportError:
    USRP_AVAILABLE = False
    uhd = None


@dataclass
class USRPConfig:
    """USRP configuration."""
    device_args: str = ""  # e.g., "addr=192.168.10.2" or "serial=12345"
    center_freq_hz: float = 3.55e9
    sample_rate_sps: float = 30.72e6
    gain: float = 30.0  # dB
    antenna: str = "RX2"  # "RX1" or "RX2"
    bandwidth_hz: Optional[float] = None  # Analog filter BW (None = auto)


class USRPSource(IQSourceBase):
    """
    Hardware IQ source using USRP.
    
    USRP is a high-end SDR platform (DC to 6 GHz depending on model).
    Suitable for 5G, wideband, and professional applications.
    """
    
    def __init__(self, config: USRPConfig, frame_size: int = 2048):
        """
        Initialize USRP source.
        
        Args:
            config: USRP configuration
            frame_size: Number of samples per frame
        """
        if not USRP_AVAILABLE:
            raise RuntimeError("USRP/UHD not available. Install with: conda install -c ettus uhd")
        
        self.config = config
        self.frame_size = frame_size
        self.usrp: Optional[uhd.usrp.MultiUSRP] = None
        self.streamer: Optional[uhd.usrp.RxStreamer] = None
        self.frame_count = 0
        
        # Initialize device
        self._init_device()
    
    def _init_device(self):
        """Initialize USRP device."""
        try:
            # Create USRP object
            self.usrp = uhd.usrp.MultiUSRP(self.config.device_args)
            
            # Configure
            self.usrp.set_rx_rate(self.config.sample_rate_sps, 0)
            self.usrp.set_rx_freq(uhd.types.TuneRequest(self.config.center_freq_hz), 0)
            self.usrp.set_rx_gain(self.config.gain, 0)
            self.usrp.set_rx_antenna(self.config.antenna, 0)
            
            if self.config.bandwidth_hz is not None:
                self.usrp.set_rx_bandwidth(self.config.bandwidth_hz, 0)
            
            # Create streamer
            stream_args = uhd.usrp.StreamArgs("fc32", "sc16")  # complex float
            stream_args.channels = [0]
            self.streamer = self.usrp.get_rx_stream(stream_args)
            
            # Start streaming
            stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
            stream_cmd.stream_now = True
            self.streamer.issue_stream_cmd(stream_cmd)
            
            print(f"✓ USRP initialized: {self.config.center_freq_hz/1e9:.3f} GHz @ {self.config.sample_rate_sps/1e6:.2f} MS/s")
        
        except Exception as e:
            raise RuntimeError(f"Failed to initialize USRP: {e}")
    
    def get_frame(self) -> IQFrame:
        """
        Read IQ frame from USRP.
        
        Returns:
            IQFrame with samples on GPU
        """
        if self.streamer is None:
            raise RuntimeError("USRP not initialized")
        
        # Allocate buffer
        buffer = np.zeros(self.frame_size, dtype=np.complex64)
        
        # Receive samples
        metadata = uhd.types.RXMetadata()
        self.streamer.recv(buffer, metadata)
        
        # Check for errors
        if metadata.error_code != uhd.types.RXMetadataErrorCode.none:
            print(f"Warning: USRP RX error: {metadata.strerror()}")
        
        # Transfer to GPU
        samples_gpu = cp.asarray(buffer, dtype=cp.complex64)
        
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
        """Close USRP device."""
        if self.streamer is not None:
            # Stop streaming
            stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont)
            self.streamer.issue_stream_cmd(stream_cmd)
            self.streamer = None
        
        self.usrp = None
        print("✓ USRP closed")
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()


def detect_usrp_devices() -> list:
    """
    Detect available USRP devices.
    
    Returns:
        List of device info dicts
    """
    if not USRP_AVAILABLE:
        return []
    
    try:
        devices_str = uhd.usrp.MultiUSRP.find("")
        devices = []
        
        for dev_str in devices_str.split('\n'):
            if dev_str.strip():
                devices.append({
                    'args': dev_str.strip(),
                    'name': f"USRP ({dev_str[:40]}...)" if len(dev_str) > 40 else f"USRP ({dev_str})",
                    'type': 'usrp',
                })
        
        return devices
    
    except Exception as e:
        print(f"Warning: USRP detection failed: {e}")
        return []



