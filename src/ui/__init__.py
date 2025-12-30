"""
UI module: Streamlit components.
"""

from .spectrum import create_spectrum_figure
from .spectrogram import WaterfallBuffer, create_spectrogram_figure
from .map_layers import create_deck, create_tile_heatmap_layer, create_tile_3d_layer
from .controls import render_sidebar_controls
from .state import (
    init_session_state,
    get_or_create_iq_source,
    get_or_create_gps_source,
    get_or_create_dsp_pipeline,
    get_or_create_tile_grid,
    get_or_create_tile_aggregator,
    get_or_create_waterfall_buffer,
    reset_pipeline,
)
from .dsp_summary import render_dsp_summary_table, update_dsp_stats

__all__ = [
    'create_spectrum_figure',
    'WaterfallBuffer',
    'create_spectrogram_figure',
    'create_deck',
    'create_tile_heatmap_layer',
    'create_tile_3d_layer',
    'render_sidebar_controls',
    'init_session_state',
    'get_or_create_iq_source',
    'get_or_create_gps_source',
    'get_or_create_dsp_pipeline',
    'get_or_create_tile_grid',
    'get_or_create_tile_aggregator',
    'get_or_create_waterfall_buffer',
    'reset_pipeline',
    'render_dsp_summary_table',
    'update_dsp_stats',
]

