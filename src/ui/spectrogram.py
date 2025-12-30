"""
Streamlit UI components: spectrogram (waterfall) builder.
"""

import plotly.graph_objects as go
import numpy as np
from typing import List
from collections import deque

from common.types import FrameFeatures


class WaterfallBuffer:
    """
    Ring buffer for waterfall/spectrogram data.
    
    Maintains last N frames of PSD data.
    """
    
    def __init__(self, max_frames: int, fft_size: int):
        """
        Initialize waterfall buffer.
        
        Args:
            max_frames: Maximum number of frames to keep
            fft_size: FFT size (number of frequency bins)
        """
        self.max_frames = max_frames
        self.fft_size = fft_size
        self.buffer = deque(maxlen=max_frames)
        self.freq_bins_mhz = None
    
    def add_frame(self, features: FrameFeatures, center_freq_hz: float) -> None:
        """
        Add a frame to the buffer.
        
        Args:
            features: FrameFeatures with PSD data
            center_freq_hz: RF center frequency
        """
        import cupy as cp
        
        # Convert to host
        psd_db = cp.asnumpy(features.psd_db)
        
        # Store frequency bins (once)
        if self.freq_bins_mhz is None:
            freq_bins_baseband = cp.asnumpy(features.freq_bins_hz)
            self.freq_bins_mhz = (center_freq_hz + freq_bins_baseband) / 1e6
        
        # Add to buffer
        self.buffer.append(psd_db)
    
    def get_waterfall_data(self) -> np.ndarray:
        """
        Get waterfall data as 2D array.
        
        Returns:
            2D array: (time, frequency), shape (num_frames, fft_size)
        """
        if len(self.buffer) == 0:
            return np.zeros((1, self.fft_size))
        
        return np.array(self.buffer)
    
    def clear(self) -> None:
        """Clear buffer."""
        self.buffer.clear()
        self.freq_bins_mhz = None


def create_spectrogram_figure(
    waterfall_buffer: WaterfallBuffer,
    colorscale: str = "Viridis",
    center_freq_hz: float = None,
    sample_rate_sps: float = None
) -> go.Figure:
    """
    Create 2D spectrogram (waterfall) heatmap.
    
    Args:
        waterfall_buffer: WaterfallBuffer with time-series PSD data
        colorscale: Plotly colorscale name
        
    Returns:
        Plotly Figure
    """
    waterfall_data = waterfall_buffer.get_waterfall_data()
    freq_bins_mhz = waterfall_buffer.freq_bins_mhz
    
    if freq_bins_mhz is None or len(waterfall_data) == 0:
        # No data yet - create empty placeholder
        fig = go.Figure()
        fig.add_annotation(
            text="Waiting for data...",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_layout(
            title="RF Spectrogram (2D Waterfall)",
            template="plotly_dark",
            height=400,
        )
        return fig
    
    # Reverse data so newest is at top
    waterfall_data_reversed = waterfall_data[::-1]
    
    fig = go.Figure(data=go.Heatmap(
        z=waterfall_data_reversed,
        x=freq_bins_mhz,
        y=np.arange(len(waterfall_data_reversed)),
        colorscale=colorscale,
        colorbar=dict(title="Power (dB)", x=1.02),
        hovertemplate='Freq: %{x:.1f} MHz<br>Time: %{y}<br>Power: %{z:.1f} dB<extra></extra>',
    ))
    
    fig.update_layout(
        title="RF Spectrogram (2D Waterfall)",
        xaxis_title="Frequency (MHz)",
        yaxis_title="Time (frames, newest at top)",
        template="plotly_dark",
        height=400,
        xaxis=dict(
            range=[freq_bins_mhz.min(), freq_bins_mhz.max()],
            constrain='domain',
        ),
        yaxis=dict(
            autorange=True,
        ),
    )
    
    return fig

