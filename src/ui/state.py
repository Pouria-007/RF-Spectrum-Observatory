"""
Streamlit UI components: session state management.
"""

import streamlit as st
from typing import Optional, List

from common.types import FrameFeatures, TileMetrics
from ingest import SyntheticIQSource, SyntheticGPSSource
from dsp import DSPPipeline
from geo import TileGrid, TileAggregator
from ui.spectrogram import WaterfallBuffer


def init_session_state(config):
    """
    Initialize Streamlit session state.
    
    Args:
        config: Config object
    """
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        st.session_state.iq_source = None
        st.session_state.gps_source = None
        st.session_state.dsp_pipeline = None
        st.session_state.tile_grid = None
        st.session_state.tile_aggregator = None
        st.session_state.waterfall_buffer = None
        st.session_state.frame_features = []
        st.session_state.tile_metrics = []
        st.session_state.latest_features = None
        st.session_state.frame_count = 0
        
        # Add health monitor
        from common.system_status import PipelineHealthMonitor
        st.session_state.health_monitor = PipelineHealthMonitor()
        
        # Initialize DSP stats
        from ui.dsp_summary import init_dsp_stats
        init_dsp_stats()


def get_or_create_iq_source(config, hardware_device=None):
    """
    Get or create IQ source from session state.
    
    Args:
        config: System configuration
        hardware_device: Optional HardwareDevice to use instead of synthetic
    """
    if st.session_state.iq_source is None or (hardware_device and st.session_state.get('last_hardware') != hardware_device.name):
        # Close existing if needed
        if st.session_state.iq_source is not None:
            if hasattr(st.session_state.iq_source, 'stop'):
                st.session_state.iq_source.stop()
            if hasattr(st.session_state.iq_source, 'close'):
                st.session_state.iq_source.close()
        
        # Create new source
        if hardware_device:
            from ingest import create_iq_source
            st.session_state.iq_source = create_iq_source(
                hardware_device,
                config.rf.center_freq_hz,
                config.rf.sample_rate_sps,
                config.rf.fft_size
            )
            st.session_state.last_hardware = hardware_device.name
        else:
            st.session_state.iq_source = SyntheticIQSource(
                center_freq_hz=config.rf.center_freq_hz,
                sample_rate_sps=config.rf.sample_rate_sps,
                fft_size=config.rf.fft_size,
                num_carriers=config.synthetic.iq['num_carriers'],
                carrier_bw_hz=config.synthetic.iq['carrier_bw_hz'],
                carrier_power_db=config.synthetic.iq['carrier_power_db'],
                noise_floor_db=config.synthetic.iq['noise_floor_db'],
                interference_config=config.synthetic.iq.get('interference', {}),
            )
            st.session_state.last_hardware = "Synthetic"
        
        # Start the source (required for synthetic sources)
        if hasattr(st.session_state.iq_source, 'start'):
            st.session_state.iq_source.start()
    
    return st.session_state.iq_source


def get_or_create_gps_source(config) -> SyntheticGPSSource:
    """Get or create GPS source."""
    if st.session_state.gps_source is None:
        st.session_state.gps_source = SyntheticGPSSource(
            route_csv=config.synthetic.gps['route_csv'],
            update_rate_hz=config.synthetic.gps['update_rate_hz'],
            speed_mps=config.synthetic.gps['speed_mps'],
        )
        st.session_state.gps_source.start()
    return st.session_state.gps_source


def get_or_create_dsp_pipeline(config) -> DSPPipeline:
    """Get or create DSP pipeline."""
    if st.session_state.dsp_pipeline is None:
        from dsp import create_pipeline_from_config
        st.session_state.dsp_pipeline = create_pipeline_from_config(config)
    return st.session_state.dsp_pipeline


def get_or_create_tile_grid(config) -> TileGrid:
    """Get or create tile grid."""
    if st.session_state.tile_grid is None:
        st.session_state.tile_grid = TileGrid(
            center_lat=config.geo.map_center_lat,
            center_lon=config.geo.map_center_lon,
            tile_size_meters=config.geo.tile_size_meters,
            grid_extent_meters=config.geo.grid_extent_meters,
        )
    return st.session_state.tile_grid


def get_or_create_tile_aggregator(config, tile_grid: TileGrid) -> TileAggregator:
    """Get or create tile aggregator."""
    if st.session_state.tile_aggregator is None:
        st.session_state.tile_aggregator = TileAggregator(
            tile_grid=tile_grid,
            aggregate_window_frames=config.geo.aggregate_window_frames,
            num_bands=len(config.dsp.bands),
        )
    return st.session_state.tile_aggregator


def get_or_create_waterfall_buffer(config) -> WaterfallBuffer:
    """Get or create waterfall buffer."""
    if st.session_state.waterfall_buffer is None:
        st.session_state.waterfall_buffer = WaterfallBuffer(
            max_frames=config.ui.waterfall['max_time_frames'],
            fft_size=config.rf.fft_size,
        )
    return st.session_state.waterfall_buffer


def reset_pipeline():
    """Reset all pipeline components."""
    if st.session_state.iq_source:
        st.session_state.iq_source.stop()
    if st.session_state.gps_source:
        st.session_state.gps_source.stop()
    
    st.session_state.iq_source = None
    st.session_state.gps_source = None
    st.session_state.dsp_pipeline = None
    st.session_state.tile_aggregator = None
    st.session_state.waterfall_buffer = None
    st.session_state.frame_features = []
    st.session_state.tile_metrics = []
    st.session_state.latest_features = None
    st.session_state.frame_count = 0
    
    # Reset DSP stats
    from ui.dsp_summary import reset_dsp_stats
    reset_dsp_stats()

