"""
Streamlit UI components: spectrum plot builder.
"""

import plotly.graph_objects as go
import numpy as np
from typing import List, Dict, Any

from common.types import FrameFeatures


def create_spectrum_figure(
    features: FrameFeatures,
    center_freq_hz: float,
    trace_config: List[Dict[str, Any]]
) -> go.Figure:
    """
    Create 2D spectrum plot with multiple traces.
    
    Args:
        features: FrameFeatures with PSD data
        center_freq_hz: RF center frequency
        trace_config: List of trace configurations
        
    Returns:
        Plotly Figure
    """
    import cupy as cp
    
    # Convert to host
    freq_bins_baseband = cp.asnumpy(features.freq_bins_hz)
    psd_db = cp.asnumpy(features.psd_db)
    psd_smoothed_db = cp.asnumpy(features.psd_smoothed_db)
    
    # Convert to absolute frequencies (MHz for display)
    freq_mhz = (center_freq_hz + freq_bins_baseband) / 1e6
    
    fig = go.Figure()
    
    # Add traces based on config
    for trace_cfg in trace_config:
        name = trace_cfg.get('name', 'Trace')
        color = trace_cfg.get('color', '#00ff00')
        line_width = trace_cfg.get('line_width', 2)
        dash = trace_cfg.get('dash', None)
        
        if 'Current' in name:
            data = psd_db
        elif 'Smoothed' in name:
            data = psd_smoothed_db
        elif 'Noise Floor' in name:
            # Horizontal line at noise floor
            data = np.full_like(psd_db, features.noise_floor_db)
        else:
            data = psd_db
        
        fig.add_trace(go.Scatter(
            x=freq_mhz,
            y=data,
            mode='lines',
            name=name,
            line=dict(color=color, width=line_width, dash=dash),
        ))
    
    fig.update_layout(
        title="RF Spectrum (2D Multi-Trace)",
        xaxis_title="Frequency (MHz)",
        yaxis_title="Power (dB)",
        template="plotly_dark",
        hovermode="x unified",
        height=400,
    )
    
    return fig

