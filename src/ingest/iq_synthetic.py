"""
Synthetic IQ sample generator.

Generates realistic 5G-like wideband OFDM signals with configurable interference.
"""

import cupy as cp
import numpy as np
from typing import Iterator, Optional, List, Dict, Any

from common.types import IQFrame
from common.timebase import now_ns, sec_to_ns
from ingest.iq_base import BaseIQSource


class SyntheticIQSource(BaseIQSource):
    """
    Deterministic synthetic IQ generator.
    
    Generates:
    - Gaussian noise floor
    - Multiple OFDM-like carriers (tones or wideband blocks)
    - Optional interference:
        - Burst jammer (periodic on/off)
        - Swept tone (chirp)
    
    All generation happens on GPU for performance.
    """
    
    def __init__(
        self,
        center_freq_hz: float,
        sample_rate_sps: float,
        fft_size: int,
        num_carriers: int = 5,
        carrier_bw_hz: float = 10e6,
        carrier_power_db: float = -30,
        noise_floor_db: float = -80,
        interference_config: Optional[Dict[str, Any]] = None,
        seed: int = 42,
    ):
        """
        Initialize synthetic IQ source.
        
        Args:
            center_freq_hz: RF center frequency
            sample_rate_sps: Sample rate
            fft_size: Number of samples per frame
            num_carriers: Number of simulated carriers
            carrier_bw_hz: Bandwidth of each carrier
            carrier_power_db: Carrier power (dB relative to full scale)
            noise_floor_db: Noise floor power (dB)
            interference_config: Optional interference settings
            seed: Random seed for reproducibility
        """
        self.center_freq_hz = center_freq_hz
        self.sample_rate_sps = sample_rate_sps
        self.fft_size = fft_size
        self.num_carriers = num_carriers
        self.carrier_bw_hz = carrier_bw_hz
        self.carrier_power_db = carrier_power_db
        self.noise_floor_db = noise_floor_db
        self.interference_config = interference_config or {}
        self.seed = seed
        
        # Internal state
        self._frame_id = 0
        self._running = False
        self._start_time_ns = 0
        
        # Convert dB to linear
        self._carrier_power_linear = 10 ** (carrier_power_db / 20)
        self._noise_power_linear = 10 ** (noise_floor_db / 20)
        
        # Generate carrier frequencies (evenly spaced across bandwidth)
        bandwidth_hz = sample_rate_sps * 0.8  # Use 80% of Nyquist
        freq_spacing = bandwidth_hz / (num_carriers + 1)
        self._carrier_freqs_hz = np.array([
            -bandwidth_hz/2 + (i+1) * freq_spacing
            for i in range(num_carriers)
        ])
        
        # Interference state
        self._burst_jammer_on = False
        self._sweep_freq_hz = 0.0
        
        # CuPy random state (GPU)
        self._rng = cp.random.RandomState(seed)
    
    def start(self) -> None:
        """Start the source."""
        self._running = True
        self._start_time_ns = now_ns()
        self._frame_id = 0
    
    def stop(self) -> None:
        """Stop the source."""
        self._running = False
    
    def __iter__(self) -> Iterator[IQFrame]:
        """Iterate over frames."""
        return self
    
    def __next__(self) -> IQFrame:
        """Get next frame (for iterator protocol)."""
        if not self._running:
            raise StopIteration
        return self.get_frame()
    
    def get_frame(self) -> IQFrame:
        """
        Generate a single synthetic IQ frame.
        
        Returns:
            IQFrame with synthetic samples (GPU array)
        """
        if not self._running:
            raise RuntimeError("Source not started. Call start() first.")
        
        # Compute frame timestamp
        frame_duration_ns = sec_to_ns(self.fft_size / self.sample_rate_sps)
        timestamp_ns = self._start_time_ns + self._frame_id * frame_duration_ns
        
        # Generate noise floor (GPU)
        noise = self._rng.randn(self.fft_size).astype(cp.float32) + \
                1j * self._rng.randn(self.fft_size).astype(cp.float32)
        noise *= self._noise_power_linear / cp.sqrt(2)  # Split power between I/Q
        
        # Generate carriers
        t = cp.arange(self.fft_size, dtype=cp.float32) / self.sample_rate_sps
        signal = noise.copy()
        
        for carrier_freq in self._carrier_freqs_hz:
            # OFDM-like block: carrier + random phase per subcarrier
            carrier_bw_bins = int(self.carrier_bw_hz / (self.sample_rate_sps / self.fft_size))
            phase = self._rng.rand() * 2 * cp.pi
            
            # Add random power variation (±15 dB) per frame for different signal strengths
            power_variation_db = (self._rng.rand() - 0.5) * 30.0  # -15 to +15 dB
            carrier_power_varied = self._carrier_power_linear * (10 ** (power_variation_db / 20))
            
            carrier = carrier_power_varied * cp.exp(
                1j * (2 * cp.pi * carrier_freq * t + phase)
            )
            
            # Add some "OFDM-ness" (random subcarrier modulation)
            subcarrier_mod = cp.ones(self.fft_size, dtype=cp.complex64)
            for i in range(0, self.fft_size, carrier_bw_bins):
                subcarrier_mod[i:i+carrier_bw_bins] *= cp.exp(
                    1j * self._rng.rand() * 2 * cp.pi
                )
            carrier *= subcarrier_mod
            
            signal += carrier
        
        # Add interference
        signal = self._apply_interference(signal, t, self._frame_id)
        
        # Create frame
        frame = IQFrame(
            frame_id=self._frame_id,
            timestamp_ns=int(timestamp_ns),
            center_freq_hz=self.center_freq_hz,
            sample_rate_sps=self.sample_rate_sps,
            gain_db=None,  # Not applicable for synthetic
            iq=signal.astype(cp.complex64),
        )
        
        self._frame_id += 1
        return frame
    
    def _apply_interference(
        self,
        signal: cp.ndarray,
        t: cp.ndarray,
        frame_id: int
    ) -> cp.ndarray:
        """
        Apply optional interference to signal.
        
        Args:
            signal: Current signal (complex64)
            t: Time vector
            frame_id: Current frame ID
            
        Returns:
            Signal with interference added
        """
        if not self.interference_config.get('enabled', False):
            return signal
        
        # Burst jammer
        burst_cfg = self.interference_config.get('burst_jammer', {})
        if burst_cfg.get('enabled', False):
            period = burst_cfg.get('period_frames', 50)
            duty_cycle = burst_cfg.get('duty_cycle', 0.1)
            on_frames = int(period * duty_cycle)
            
            if (frame_id % period) < on_frames:
                # Jammer is ON: add wideband noise
                jammer_power_db = -20  # Strong jammer
                jammer_power_linear = 10 ** (jammer_power_db / 20)
                jammer = self._rng.randn(len(signal)).astype(cp.float32) + \
                        1j * self._rng.randn(len(signal)).astype(cp.float32)
                jammer *= jammer_power_linear / cp.sqrt(2)
                signal += jammer
        
        # Swept tone (chirp)
        sweep_cfg = self.interference_config.get('swept_tone', {})
        if sweep_cfg.get('enabled', False):
            sweep_rate = sweep_cfg.get('sweep_rate_hz_per_sec', 1e6)
            frame_duration_sec = self.fft_size / self.sample_rate_sps
            
            # Update sweep frequency
            self._sweep_freq_hz += sweep_rate * frame_duration_sec
            if abs(self._sweep_freq_hz) > self.sample_rate_sps / 2:
                self._sweep_freq_hz = -self.sample_rate_sps / 2
            
            sweep_power_db = -25
            sweep_power_linear = 10 ** (sweep_power_db / 20)
            sweep = sweep_power_linear * cp.exp(1j * 2 * cp.pi * self._sweep_freq_hz * t)
            signal += sweep
        
        return signal
    
    def get_truth_labels(self) -> Dict[str, Any]:
        """
        Get ground truth labels for validation/testing.
        
        Returns:
            Dictionary with:
                - carrier_freqs_hz: List of carrier frequencies (absolute)
                - interference_enabled: bool
                - burst_jammer_enabled: bool
                - swept_tone_enabled: bool
        """
        carrier_freqs_abs = [
            self.center_freq_hz + f for f in self._carrier_freqs_hz
        ]
        
        return {
            'carrier_freqs_hz': carrier_freqs_abs.tolist() if isinstance(carrier_freqs_abs, np.ndarray) else carrier_freqs_abs,
            'num_carriers': self.num_carriers,
            'carrier_bw_hz': self.carrier_bw_hz,
            'noise_floor_db': self.noise_floor_db,
            'interference_enabled': self.interference_config.get('enabled', False),
            'burst_jammer_enabled': self.interference_config.get('burst_jammer', {}).get('enabled', False),
            'swept_tone_enabled': self.interference_config.get('swept_tone', {}).get('enabled', False),
        }

