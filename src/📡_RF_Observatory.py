"""
Streamlit app: GPU-Accelerated Sub-6 Spectrum Observatory

Main dashboard with:
- 2D Spectrum (multi-trace)
- 2D Waterfall/Spectrogram
- 2D Tile Heatmap Map
- 3D Extruded Tiles Map (PyDeck)
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import streamlit as st
import time
import traceback

from common import load_config, setup_logging, get_gpu_status, get_rmm_status, PipelineHealthMonitor
from ingest import detect_all_hardware, create_iq_source
from ui import (
    init_session_state,
    render_sidebar_controls,
    get_or_create_iq_source,
    get_or_create_gps_source,
    get_or_create_dsp_pipeline,
    get_or_create_tile_grid,
    get_or_create_tile_aggregator,
    get_or_create_waterfall_buffer,
    reset_pipeline,
    create_spectrum_figure,
    create_spectrogram_figure,
    create_deck,
    render_dsp_summary_table,
    update_dsp_stats,
)
from geo import export_all

# Page config
st.set_page_config(
    page_title="RF-Spectrum-Observatory",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load config
config = load_config('config/default.yaml')

# Initialize RMM pool (GPU memory management)
from perf import setup_rmm_pool
if config.performance.rmm_pool_size_gb:
    try:
        setup_rmm_pool(config.performance.rmm_pool_size_gb)
    except Exception as e:
        st.warning(f"RMM initialization failed: {e}. Using default CuPy allocator.")

# Initialize session state
init_session_state(config)

# Detect available hardware (cached)
if 'available_hardware' not in st.session_state:
    with st.spinner("🔍 Detecting RF hardware..."):
        st.session_state.available_hardware = detect_all_hardware()

# Render sidebar
controls = render_sidebar_controls(st.session_state.available_hardware)

# Handle reset
if controls['reset_button']:
    reset_pipeline()
    st.success("Pipeline reset!")
    st.rerun()

# Handle export
if controls['export_button']:
    if st.session_state.frame_features and st.session_state.tile_metrics:
        export_all(
            st.session_state.frame_features,
            st.session_state.tile_metrics,
            config.project['output_dir']
        )
        st.success(f"Exported data to {config.project['output_dir']}")
    else:
        st.warning("No data to export. Run the pipeline first.")

# Main UI
st.title("📡 RF-Spectrum-Observatory")
st.markdown("[![GitHub](https://img.shields.io/badge/GitHub-RF--Spectrum--Observatory-blue?logo=github)](https://github.com/Pouria-007/RF-Spectrum-Observatory)")
st.markdown("[![GitHub](https://img.shields.io/badge/GitHub-RF--Spectrum--Observatory-blue)](https://github.com/Pouria-007/RF-Spectrum-Observatory)")
st.markdown(f"**Center Frequency:** {config.rf.center_freq_hz/1e9:.3f} GHz | **Sample Rate:** {config.rf.sample_rate_sps/1e6:.2f} MS/s")

# Top row: Status metrics + GPU/System info + Pipeline Health
top_col1, top_col2, top_col3 = st.columns([2, 2, 2])

with top_col1:
    st.markdown("#### 📊 Pipeline Metrics")
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    with metric_col1:
        st.metric("Frames", st.session_state.frame_count)
    with metric_col2:
        st.metric("Tiles", len(st.session_state.tile_metrics))
    with metric_col3:
        st.metric("Status", "🟢 Running" if controls['run_pipeline'] else "⚪ Stopped")
    
    # Show current hardware source
    if st.session_state.get('last_hardware'):
        hw_name = st.session_state.last_hardware
        if 'Synthetic' in hw_name:
            st.caption("📡 Source: Synthetic (software)")
        else:
            st.caption(f"📡 Source: {hw_name}")
    
    # Show current hardware source
    if st.session_state.get('last_hardware'):
        hw_name = st.session_state.last_hardware
        if 'Synthetic' in hw_name:
            st.caption("📡 Source: Synthetic (software)")
        else:
            st.caption(f"📡 Source: {hw_name}")

with top_col2:
    st.markdown("#### 🖥️ GPU Status")
    gpu_status = get_gpu_status()
    if gpu_status['gpu_available']:
        st.success(f"✅ GPU: {gpu_status['gpu_name'][:30]}")
        st.caption(f"Memory: {gpu_status['gpu_memory_used_gb']:.1f} / {gpu_status['gpu_memory_total_gb']:.1f} GB used")
    else:
        st.error("❌ No GPU detected")
    
    # RMM status
    rmm_status = get_rmm_status()
    if rmm_status['enabled']:
        st.info(f"RMM Pool: {rmm_status['allocated_gb']:.2f} GB allocated")
    else:
        st.caption("RMM: Disabled (using default CuPy allocator)")

with top_col3:
    st.markdown("#### 🏥 Pipeline Health")
    if hasattr(st.session_state, 'health_monitor'):
        health = st.session_state.health_monitor.get_health_status()
        for module, (status, msg) in health.items():
            if status == 'green':
                st.success(f"✅ {module}: {msg}")
            elif status == 'yellow':
                st.warning(f"⚠️ {module}: {msg}")
            else:
                st.error(f"❌ {module}: {msg}")
    else:
        st.caption("Health monitoring initializing...")

st.markdown("---")

# Main layout
if controls['run_pipeline']:
    # Get hardware selection from controls
    hardware_device = controls.get('hardware_selection')
    
    # Get/create components
    iq_source = get_or_create_iq_source(config, hardware_device)
    gps_source = get_or_create_gps_source(config)
    dsp_pipeline = get_or_create_dsp_pipeline(config)
    tile_grid = get_or_create_tile_grid(config)
    tile_aggregator = get_or_create_tile_aggregator(config, tile_grid)
    waterfall_buffer = get_or_create_waterfall_buffer(config)
    
    # Process multiple frames per refresh (batch processing)
    frames_per_refresh = config.performance.frames_per_refresh  # Use config value
    
    # Store in session state for GPU monitor
    st.session_state.frames_per_refresh = frames_per_refresh
    
    for batch_idx in range(frames_per_refresh):
        try:
            # Get IQ frame
            frame = iq_source.get_frame()
            
            # Get GPS fix
            gps_fix = gps_source.get_fix()
            if gps_fix:
                dsp_pipeline.add_gps_fix(gps_fix)
            
            # Process frame
            features = dsp_pipeline.process_frame(frame)
            
            # Update DSP stats
            samples_in_frame = len(frame.iq)
            update_dsp_stats(samples_in_frame, windows_processed=1)
            
            # Update buffers
            st.session_state.latest_features = features  # Keep last frame for display
            st.session_state.frame_features.append(features)
            st.session_state.frame_count += 1
            
            # Trim frame buffer
            if len(st.session_state.frame_features) > controls['max_frames']:
                st.session_state.frame_features = st.session_state.frame_features[-controls['max_frames']:]
            
            # Add to waterfall (add every frame for smoother updates)
            waterfall_buffer.add_frame(features, config.rf.center_freq_hz)
            
            # Add to tile aggregator
            tile_aggregator.add_frame(features)
            
            # Aggregate tiles if ready (check every frame, but only aggregate when window is full)
            if tile_aggregator.should_aggregate():
                new_tiles = tile_aggregator.aggregate()
                if new_tiles:  # Only extend if we got tiles
                    # Just append all new tiles (no merging - each aggregation is independent)
                    st.session_state.tile_metrics.extend(new_tiles)
                    
                    # Keep last 100 tiles to show GPS trail
                    if len(st.session_state.tile_metrics) > 100:
                        st.session_state.tile_metrics = st.session_state.tile_metrics[-100:]
            # Update health monitor
            if hasattr(st.session_state, 'health_monitor'):
                st.session_state.health_monitor.update_iq_source(st.session_state.frame_count)
                st.session_state.health_monitor.update_gps_source(gps_fix is not None)
                st.session_state.health_monitor.update_dsp(features is not None)
                st.session_state.health_monitor.update_geo(len(st.session_state.tile_metrics))
        
        except Exception as e:
            # Show error but don't gray out UI - just skip this frame
            st.session_state.last_error = str(e)
            st.session_state.last_error_traceback = traceback.format_exc()
            # Skip this frame and continue
            pass
    
    # Update UI health
    if hasattr(st.session_state, 'health_monitor'):
        st.session_state.health_monitor.update_ui()
    
    # Debug: Show aggregation status in sidebar
    buffer_size = len(tile_aggregator.frame_buffer)
    window_size = tile_aggregator.aggregate_window_frames
    st.sidebar.text(f"Aggregation buffer: {buffer_size}/{window_size}")
    if st.session_state.latest_features:
        feat = st.session_state.latest_features
        if feat.lat_deg and feat.lon_deg:
            st.sidebar.text(f"GPS: ({feat.lat_deg:.5f}, {feat.lon_deg:.5f})")
    
    # Update rate throttle
    time.sleep(1.0 / controls['update_rate'])
    
    # Show any errors at the top (but don't stop execution)
    if hasattr(st.session_state, 'last_error') and st.session_state.last_error:
        with st.expander("⚠️ Latest Pipeline Warning", expanded=False):
            st.warning(st.session_state.last_error)
            if hasattr(st.session_state, 'last_error_traceback'):
                st.code(st.session_state.last_error_traceback)

# Display charts
if st.session_state.latest_features is not None:
    # Row 1: Spectrum + Waterfall
    st.markdown("### 📊 Spectral Visualizations")
    st.markdown("Real-time frequency domain analysis showing power distribution and time evolution.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**2D Spectrum (Multi-Trace)**")
        st.caption("🟢 Current PSD | 🟠 Smoothed PSD | 🔴 Noise Floor")
        spectrum_fig = create_spectrum_figure(
            st.session_state.latest_features,
            config.rf.center_freq_hz,
            config.ui.spectrum['traces']
        )
        st.plotly_chart(spectrum_fig, width='stretch', use_container_width=True)
    
    with col2:
        st.markdown("**2D Waterfall/Spectrogram**")
        st.caption("Time-frequency heatmap showing power evolution (newest at top)")
        # Get fresh waterfall buffer to ensure updates
        waterfall_buffer = get_or_create_waterfall_buffer(config)
        spectrogram_fig = create_spectrogram_figure(
            waterfall_buffer,
            config.ui.waterfall['colorscale'],
            center_freq_hz=config.rf.center_freq_hz,
            sample_rate_sps=config.rf.sample_rate_sps
        )
        st.plotly_chart(spectrogram_fig, width='stretch', use_container_width=True)
    
    # DSP Summary Table (between charts and map)
    st.markdown("---")
    render_dsp_summary_table(config)
    
    # Row 2: Map (2D or 3D)
    st.markdown("---")
    st.markdown("### 🗺️ Geospatial RF Map (Drone Flight Path)")
    st.caption("🚁 Green marker shows current drone position | Tiles show RF signal measurements along flight path")
    
    # Live statistics above map
    if st.session_state.tile_metrics:
        all_tiles = st.session_state.tile_metrics
        unique_tile_ids = len(set(t.tile_id for t in all_tiles))
        
        # Calculate statistics
        if controls['metric_name'] == 'bandpower_mean':
            metric_values = [t.bandpower_mean_db[controls['band_idx']] if controls['band_idx'] < len(t.bandpower_mean_db) else -100 for t in all_tiles]
        elif controls['metric_name'] == 'bandpower_max':
            metric_values = [t.bandpower_max_db[controls['band_idx']] if controls['band_idx'] < len(t.bandpower_max_db) else -100 for t in all_tiles]
        elif controls['metric_name'] == 'occupancy_mean':
            metric_values = [t.occupancy_mean_pct[controls['band_idx']] if controls['band_idx'] < len(t.occupancy_mean_pct) else 0 for t in all_tiles]
        else:
            metric_values = [0] * len(all_tiles)
        
        if metric_values:
            min_val = min(metric_values)
            max_val = max(metric_values)
            avg_val = sum(metric_values) / len(metric_values)
        else:
            min_val = max_val = avg_val = 0
        
        # Determine metric name and unit
        metric_display_name = controls['metric_name'].replace('_', ' ').title()
        if 'bandpower' in controls['metric_name']:
            unit = "dB"
            metric_full_name = f"{metric_display_name} ({unit})"
        elif 'occupancy' in controls['metric_name']:
            unit = "%"
            metric_full_name = f"{metric_display_name} ({unit})"
        else:
            unit = ""
            metric_full_name = metric_display_name
        
        # Display live stats with clear labels
        stat_col1, stat_col2, stat_col3, stat_col4, stat_col5 = st.columns(5)
        with stat_col1:
            st.metric("📍 Active Tiles", unique_tile_ids, delta=None, help="Number of unique tile locations with data")
        with stat_col2:
            st.metric("📊 Total Tiles", len(all_tiles), delta=None, help="Total number of tile aggregations (may include duplicates)")
        with stat_col3:
            st.metric(f"📈 Max {metric_display_name}", f"{max_val:.1f} {unit}", delta=None, help=f"Maximum {metric_display_name.lower()} value across all tiles")
        with stat_col4:
            st.metric(f"📉 Min {metric_display_name}", f"{min_val:.1f} {unit}", delta=None, help=f"Minimum {metric_display_name.lower()} value across all tiles")
        with stat_col5:
            st.metric(f"📊 Avg {metric_display_name}", f"{avg_val:.1f} {unit}", delta=None, help=f"Average {metric_display_name.lower()} value across all tiles")
    
    # Map explanation
    col_explain1, col_explain2 = st.columns([3, 1])
    
    with col_explain1:
        if controls['show_3d']:
            st.markdown(f"**3D Extruded Map** - Height represents {controls['metric_name'].replace('_', ' ').title()}")
            st.caption(f"Visualizing Band {controls['band_idx']} | Extrusion scale: {controls['extrusion_scale']}x | Aggregation window: {config.geo.aggregate_window_frames} frames (rolling)")
        else:
            st.markdown(f"**2D Tile Heatmap** - Color represents {controls['metric_name'].replace('_', ' ').title()}")
            st.caption(f"Visualizing Band {controls['band_idx']} | {len(st.session_state.tile_metrics)} tiles aggregated | Window: {config.geo.aggregate_window_frames} frames (rolling)")
    
    with col_explain2:
        st.markdown("**Color Scale**")
        st.markdown("🟣 **Purple** = High power")
        st.markdown("🔵 **Blue** = Medium power")
        st.markdown("⚫ **Dark** = Low power")
    
    st.info(
        f"💡 **Map Explanation:** An imaginary drone 🚁 flies through the city collecting RF spectrum data. "
        f"Each tile represents a geographic area (grid cell) along the flight path. "
        f"The color/height indicates the RF signal strength measured in that location. "
        f"The green marker shows the drone's current position. "
        f"Each tile aggregates measurements from {config.geo.aggregate_window_frames} IQ frames captured in that area.")
    
    # Get ALL tiles (not just recent) to show multiple locations
    all_tiles = st.session_state.tile_metrics if st.session_state.tile_metrics else []
    
    # Get current GPS position for drone marker
    current_gps_lat = None
    current_gps_lon = None
    if st.session_state.latest_features:
        feat = st.session_state.latest_features
        if feat.lat_deg and feat.lon_deg:
            current_gps_lat = feat.lat_deg
            current_gps_lon = feat.lon_deg
    
    # Always render map (even with no tiles, shows base map)
    try:
        deck = create_deck(
            tile_metrics=all_tiles,
            map_center_lat=config.geo.map_center_lat,
            map_center_lon=config.geo.map_center_lon,
            zoom=controls['zoom'],
            pitch=controls['pitch'],
            show_3d=controls['show_3d'],
            metric_name=controls['metric_name'],
            band_idx=controls['band_idx'],
            extrusion_scale=controls['extrusion_scale'],
            city_block_geojson=config.synthetic.maps['city_block_geojson'],
            house_geojson=config.synthetic.maps['house_geojson'],
            current_gps_lat=current_gps_lat,
            current_gps_lon=current_gps_lon,
        )
        
        st.pydeck_chart(deck, use_container_width=True)
        
        if not all_tiles:
            st.info("🔄 Aggregating tiles... Buffer filling up. Tiles will appear shortly.")
            st.caption(f"Tip: Tiles generate every {config.geo.aggregate_window_frames} frames. Current buffer shown in sidebar.")
    except Exception as e:
        st.error(f"Map rendering error: {e}")
        import traceback
        with st.expander("🔍 Map Error Details"):
            st.code(traceback.format_exc())
        st.info("Map will appear once tiles are generated.")
        
        # Map interaction guide
        with st.expander("🎯 Map Controls & Legend Guide"):
            col_guide1, col_guide2 = st.columns(2)
            
            with col_guide1:
                st.markdown("""
                **Map Navigation:**
                - **Pan:** Click and drag
                - **Zoom:** Scroll wheel / pinch
                - **Rotate (3D):** Ctrl/Cmd + drag
                - **Tilt (3D):** Shift + drag up/down
                
                **Tiles:**
                - **Click:** Shows tile ID + metric
                - **Color:** Intensity = power level
                - **Height (3D):** Taller = higher value
                """)
            
            with col_guide2:
                st.markdown("""
                **Sidebar Controls Explained:**
                - **Update Rate (Hz):** UI refresh speed
                - **Max Frames Buffer:** Memory size
                - **3D Extrusion:** Toggle 2D/3D view
                - **Metric:** What to visualize
                - **Band Index:** Which frequency
                - **Height Scale:** 3D exaggeration
                - **Zoom/Pitch:** View angle
                
                **Base Map:** Free Carto tiles (OpenStreetMap)
                """)
    
else:
    st.info("👈 Enable 'Run Pipeline' in the sidebar to start processing.")
    st.markdown("""
    ### Getting Started
    
    1. **Check 'Run Pipeline'** in the sidebar to start data ingestion
    2. **Watch the metrics** update in real-time (Frames, Tiles, Status)
    3. **Explore the visualizations**:
       - **Spectrum**: See frequency peaks and power levels
       - **Waterfall**: Observe time evolution of signals
       - **Map**: View RF coverage across geographical tiles
    4. **Adjust settings** in the sidebar (update rate, map mode, metric selection)
    5. **Export data** when ready using the Export button
    """)

# Auto-refresh
if controls['run_pipeline']:
    time.sleep(0.1)
    st.rerun()

