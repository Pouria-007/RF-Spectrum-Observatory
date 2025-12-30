"""
Raw Data Stream Page - Real-time IQ samples, GPS, and DSP features
"""

import streamlit as st
import sys
import os
import time
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common.config import load_config
from ui.state import (
    init_session_state,
    get_or_create_iq_source,
    get_or_create_gps_source,
    get_or_create_dsp_pipeline,
)

# Page config
st.set_page_config(
    page_title="Raw Data Stream",
    page_icon="📊",
    layout="wide",
)

# Load config
config = load_config(os.path.join(os.path.dirname(__file__), '../..', 'config/default.yaml'))

# Initialize session state
init_session_state(config)

# Header
st.title("📊 Raw Data Stream")
st.markdown("**Real-time inspection of IQ samples, GPS fixes, and DSP features**")

# Sidebar controls
st.sidebar.markdown("## ⚙️ Stream Settings")

# Enable/Disable streaming (performance control)
if 'raw_data_stream_enabled' not in st.session_state:
    st.session_state.raw_data_stream_enabled = False

stream_enabled = st.sidebar.checkbox(
    "🟢 Enable Live Streaming",
    value=st.session_state.raw_data_stream_enabled,
    help="Enable real-time raw data display and auto-refresh. Disable to improve app performance."
)
st.session_state.raw_data_stream_enabled = stream_enabled

if not stream_enabled:
    st.warning("⚠️ Raw data streaming is **disabled**. Check the box above to enable live data inspection and auto-refresh.")
    st.info("💡 **Tip:** Keeping streaming disabled improves overall app performance when you're not actively viewing this page.")
    st.stop()

st.sidebar.markdown("---")
update_rate = st.sidebar.slider("Update Rate (Hz)", 1, 20, 5, help="How often to refresh data")
max_samples_display = st.sidebar.slider("Max Samples to Display", 100, 2000, 500, help="Number of IQ samples to show")

st.sidebar.markdown("---")
st.sidebar.markdown("**Note:** This page runs independently from the main dashboard.")

# Main content (only runs if streaming is enabled via st.stop() above)
if stream_enabled:
    # Get sources
    iq_source = get_or_create_iq_source(config)
    gps_source = get_or_create_gps_source(config)
    dsp_pipeline = get_or_create_dsp_pipeline(config)
    
    # Get latest frame
    try:
        frame = iq_source.get_frame()
        gps_fix = gps_source.get_fix()
        
        if gps_fix:
            dsp_pipeline.add_gps_fix(gps_fix)
        
        features = dsp_pipeline.process_frame(frame)
        
        # IQ Data Section
        with st.expander("🌊 **IQ Samples (Raw RF Data)**", expanded=False):
            st.markdown(f"**Frame ID:** `{frame.frame_id}`")
            st.markdown(f"**Timestamp:** `{frame.timestamp_ns}` ns")
            st.markdown(f"**Center Frequency:** `{frame.center_freq_hz / 1e9:.3f}` GHz")
            st.markdown(f"**Sample Rate:** `{frame.sample_rate_sps / 1e6:.2f}` MS/s")
            st.markdown(f"**Total Samples:** `{len(frame.iq)}`")
            
            st.markdown("---")
            
            # Convert to host for display
            iq_full = frame.iq.get()  # Full array
            total_samples = len(iq_full)
            iq_host = iq_full[:max_samples_display]  # Slice for display
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**I (In-phase)**")
                i_samples = np.real(iq_host)
                st.code(f"First 10 of {total_samples}: {i_samples[:10]}\n...\nLast 10 of {total_samples}: {i_samples[-10:]}", language="python")
                st.markdown(f"- Total in frame: `{total_samples}` samples")
                if len(i_samples) < total_samples:
                    st.markdown(f"- Displaying: `{len(i_samples)}` samples (limited by slider)")
                st.markdown(f"- Min: `{i_samples.min():.6f}`")
                st.markdown(f"- Max: `{i_samples.max():.6f}`")
                st.markdown(f"- Mean: `{i_samples.mean():.6f}`")
                st.markdown(f"- Std: `{i_samples.std():.6f}`")
            
            with col2:
                st.markdown("**Q (Quadrature)**")
                q_samples = np.imag(iq_host)
                st.code(f"First 10 of {total_samples}: {q_samples[:10]}\n...\nLast 10 of {total_samples}: {q_samples[-10:]}", language="python")
                st.markdown(f"- Total in frame: `{total_samples}` samples")
                if len(q_samples) < total_samples:
                    st.markdown(f"- Displaying: `{len(q_samples)}` samples (limited by slider)")
                st.markdown(f"- Min: `{q_samples.min():.6f}`")
                st.markdown(f"- Max: `{q_samples.max():.6f}`")
                st.markdown(f"- Mean: `{q_samples.mean():.6f}`")
                st.markdown(f"- Std: `{q_samples.std():.6f}`")
            
            st.markdown("---")
            st.markdown("**Complex Magnitude (First 20 samples)**")
            magnitude = np.abs(iq_host[:20])
            st.code(str(magnitude), language="python")
        
        # GPS Data Section
        with st.expander("🛰️ **GPS Fix (Position Data)**", expanded=False):
            if gps_fix:
                st.markdown(f"**GPS Timestamp:** `{gps_fix.gps_timestamp_ns}` ns")
                st.markdown(f"**Latitude:** `{gps_fix.lat_deg:.8f}°`")
                st.markdown(f"**Longitude:** `{gps_fix.lon_deg:.8f}°`")
                st.markdown(f"**Altitude:** `{gps_fix.alt_m if gps_fix.alt_m else 'N/A'}` m")
                st.markdown(f"**Heading:** `{gps_fix.heading_deg if gps_fix.heading_deg else 'N/A'}°`")
                st.markdown(f"**Speed:** `{gps_fix.speed_mps if gps_fix.speed_mps else 'N/A'}` m/s")
                
                st.markdown("---")
                st.json({
                    "gps_timestamp_ns": gps_fix.gps_timestamp_ns,
                    "lat_deg": gps_fix.lat_deg,
                    "lon_deg": gps_fix.lon_deg,
                    "alt_m": gps_fix.alt_m,
                    "heading_deg": gps_fix.heading_deg,
                    "speed_mps": gps_fix.speed_mps,
                })
            else:
                st.warning("No GPS fix available")
        
        # DSP Features Section
        with st.expander("🔬 **DSP Features (Processed RF Metrics)**", expanded=False):
            st.markdown(f"**Frame ID:** `{features.frame_id}`")
            st.markdown(f"**Timestamp:** `{features.timestamp_ns}` ns")
            st.markdown(f"**Noise Floor:** `{features.noise_floor_db:.2f}` dB")
            
            if features.lat_deg and features.lon_deg:
                st.markdown(f"**GPS:** `({features.lat_deg:.8f}, {features.lon_deg:.8f})`")
            else:
                st.markdown("**GPS:** Not available")
            
            st.markdown("---")
            
            # Frequency bins (first/last 10)
            freq_bins_host = features.freq_bins_hz.get()
            total_freq_bins = len(freq_bins_host)
            st.markdown("**Frequency Bins (Hz)**")
            st.code(f"First 10 of {total_freq_bins}: {freq_bins_host[:10]}\n...\nLast 10 of {total_freq_bins}: {freq_bins_host[-10:]}", language="python")
            
            # PSD (first/last 10)
            psd_host = features.psd_db.get()
            total_psd = len(psd_host)
            st.markdown("**PSD (dB)**")
            st.code(f"First 10 of {total_psd}: {psd_host[:10]}\n...\nLast 10 of {total_psd}: {psd_host[-10:]}", language="python")
            st.markdown(f"- Total: `{total_psd}` bins")
            st.markdown(f"- Min: `{psd_host.min():.2f}` dB")
            st.markdown(f"- Max: `{psd_host.max():.2f}` dB")
            st.markdown(f"- Mean: `{psd_host.mean():.2f}` dB")
            
            # Smoothed PSD (first/last 10)
            psd_smoothed_host = features.psd_smoothed_db.get()
            total_psd_smoothed = len(psd_smoothed_host)
            st.markdown("**PSD Smoothed (dB)**")
            st.code(f"First 10 of {total_psd_smoothed}: {psd_smoothed_host[:10]}\n...\nLast 10 of {total_psd_smoothed}: {psd_smoothed_host[-10:]}", language="python")
            
            # Band features
            st.markdown("---")
            st.markdown("**Band Features**")
            
            band_data = []
            for i, (bp, occ) in enumerate(zip(features.bandpower_db, features.occupancy_pct)):
                band_data.append({
                    "Band": i,
                    "Bandpower (dB)": f"{bp:.2f}",
                    "Occupancy (%)": f"{occ:.2f}",
                })
            
            st.table(band_data)
            
            # Anomaly score
            if features.anomaly_score is not None:
                st.markdown(f"**Anomaly Score:** `{features.anomaly_score:.4f}`")
        
        # Live Counters
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Frames Processed", st.session_state.frame_count)
        
        with col2:
            st.metric("IQ Samples/Frame", len(frame.iq))
        
        with col3:
            st.metric("Update Rate", f"{update_rate} Hz")
        
        with col4:
            if st.session_state.latest_features:
                noise = st.session_state.latest_features.noise_floor_db
                st.metric("Noise Floor", f"{noise:.1f} dB")
        
        # Auto-refresh: Only rerun if streaming is enabled
        if st.session_state.raw_data_stream_enabled:
            time.sleep(1.0 / update_rate)
            st.rerun()
        
    except Exception as e:
        st.error(f"Error reading data: {e}")
        import traceback
        st.code(traceback.format_exc())
    st.markdown("### What This Page Shows")
    st.markdown("""
    This page provides a raw, unfiltered view of the data flowing through the RF Intelligence pipeline:
    
    1. **🌊 IQ Samples**: Raw complex RF samples (I/Q data) from the SDR
       - Real (I) and Imaginary (Q) components
       - First/last samples preview
       - Statistical summary (min, max, mean, std)
    
    2. **🛰️ GPS Fix**: Position data from GPS source
       - Latitude, longitude, altitude
       - Heading and speed
       - Timestamp
    
    3. **🔬 DSP Features**: Processed RF metrics
       - Frequency bins and PSD values
       - Noise floor estimation
       - Band-specific features (bandpower, occupancy)
       - Anomaly scores
    
    **Performance Note**: This page updates independently from the main dashboard. Enable streaming only when you need to inspect raw data.
    """)

