"""
Streamlit UI components: sidebar controls.
"""

import streamlit as st


def render_sidebar_controls(available_hardware=None):
    """
    Render sidebar controls.
    
    Args:
        available_hardware: List of detected hardware devices
    
    Returns:
        Dictionary of control values
    """
    st.sidebar.title("⚙️ Controls")
    
    # Hardware selection (if provided)
    hardware_selection = None
    if available_hardware:
        st.sidebar.markdown("### 📡 Hardware Source")
        hardware_names = [dev.name for dev in available_hardware]
        hardware_idx = st.sidebar.selectbox(
            "IQ Source Device",
            range(len(hardware_names)),
            format_func=lambda i: hardware_names[i],
            help="Select RF hardware or synthetic source"
        )
        hardware_selection = available_hardware[hardware_idx]
        
        # Show device info
        if hardware_selection.device_type == 'synthetic':
            st.sidebar.success("✅ Using synthetic IQ (no hardware required)")
        else:
            st.sidebar.info(f"🔌 Hardware: {hardware_selection.device_type.upper()}")
            if hardware_selection.freq_range:
                freq_min, freq_max = hardware_selection.freq_range
                st.sidebar.caption(f"Range: {freq_min/1e6:.0f}-{freq_max/1e6:.0f} MHz")
            if hardware_selection.max_sample_rate:
                st.sidebar.caption(f"Max rate: {hardware_selection.max_sample_rate/1e6:.1f} MS/s")
        
        st.sidebar.markdown("---")
    
    # Run controls
    st.sidebar.markdown("### 🎮 Pipeline")
    
    # Initialize run_pipeline state if not exists (persist across page switches)
    if 'run_pipeline' not in st.session_state:
        st.session_state.run_pipeline = False
    
    run_pipeline = st.sidebar.checkbox("▶️ Run Pipeline", 
                                       value=st.session_state.run_pipeline,
                                       key='run_pipeline_checkbox',
                                       help="Start/stop RF data processing")
    
    # Update session state
    st.session_state.run_pipeline = run_pipeline
    
    # Update rate
    update_rate = st.sidebar.slider("Update Rate (Hz)", min_value=1, max_value=30, value=10, step=1,
                                     help="UI refresh rate (higher = smoother but more CPU)")
    
    # Max frames
    max_frames = st.sidebar.number_input("Max Frames Buffer", min_value=10, max_value=1000, value=100, step=10,
                                         help="Rolling window of frames to keep in memory")
    
    st.sidebar.markdown("---")
    
    # Map controls
    st.sidebar.markdown("### 🗺️ Map Settings")
    
    # Track 3D toggle to force immediate update
    prev_3d = st.session_state.get('prev_show_3d', False)
    show_3d = st.sidebar.checkbox("🏔️ 3D Extrusion", value=prev_3d,
                                   help="Show 3D columns (height = metric value)")
    
    # Force immediate rerun if 3D toggle changed
    if show_3d != prev_3d:
        st.session_state.prev_show_3d = show_3d
        st.rerun()
    
    metric_name = st.sidebar.selectbox(
        "Metric to Display",
        ["bandpower_mean", "bandpower_max", "occupancy_mean"],
        index=0,
        help="Which metric to visualize as color/height"
    )
    
    band_idx = st.sidebar.number_input("Band Index", min_value=0, max_value=10, value=0, step=1,
                                       help="Which frequency band to display (0 = CBRS Band 48)")
    
    if show_3d:
        extrusion_scale = st.sidebar.slider("3D Height Scale", min_value=1.0, max_value=50.0, value=10.0, step=1.0,
                                            help="Vertical exaggeration for 3D columns")
    else:
        extrusion_scale = 10.0
    
    zoom = st.sidebar.slider("Zoom Level", min_value=10, max_value=18, value=15, step=1,
                             help="Map zoom (15 = street level)")
    
    pitch = st.sidebar.slider("Pitch (3D angle)", min_value=0, max_value=60, value=45 if show_3d else 0, step=5,
                              help="Viewing angle (0° = top-down, 45° = oblique)")
    
    st.sidebar.markdown("---")
    
    # Export
    st.sidebar.markdown("### 💾 Data Export")
    export_button = st.sidebar.button("📥 Export Data", help="Save frames and tiles to Parquet/GeoJSON")
    
    # Reset
    reset_button = st.sidebar.button("🔄 Reset Pipeline", help="Clear all buffers and restart")
    
    return {
        'run_pipeline': run_pipeline,
        'update_rate': update_rate,
        'max_frames': max_frames,
        'show_3d': show_3d,
        'metric_name': metric_name,
        'band_idx': band_idx,
        'extrusion_scale': extrusion_scale,
        'zoom': zoom,
        'pitch': pitch,
        'export_button': export_button,
        'reset_button': reset_button,
        'hardware_selection': hardware_selection,
    }

