"""
DSP Processing Summary UI component.

Displays key DSP metrics and throughput statistics in a compact table.
"""

import streamlit as st
import time
from typing import Dict, Any
from collections import deque


def init_dsp_stats():
    """Initialize DSP statistics tracking in session state."""
    if 'dsp_stats' not in st.session_state:
        st.session_state.dsp_stats = {
            'total_iq_samples': 0,
            'total_windows': 0,
            'last_update_samples': 0,
            'last_update_windows': 0,
            'frame_timestamps': deque(maxlen=30),  # Last 30 frames for FPS calculation
            'window_timestamps': deque(maxlen=30),  # Last 30 windows for WPS calculation
            'session_start_time': time.time(),
        }


def update_dsp_stats(samples_processed: int, windows_processed: int = 1):
    """
    Update DSP statistics after processing.
    
    Args:
        samples_processed: Number of IQ samples processed
        windows_processed: Number of windows processed (default 1 per frame)
    """
    init_dsp_stats()
    
    stats = st.session_state.dsp_stats
    stats['total_iq_samples'] += samples_processed
    stats['total_windows'] += windows_processed
    stats['last_update_samples'] = samples_processed
    stats['last_update_windows'] = windows_processed
    
    # Record timestamp for FPS/WPS calculation
    now = time.time()
    stats['frame_timestamps'].append(now)
    stats['window_timestamps'].append(now)
    
    # Calculate and store current FPS/WPS for GPU monitor
    stats['fps_current'] = calculate_fps(window_seconds=2.0)
    stats['wps_current'] = calculate_wps(window_seconds=2.0)


def calculate_fps(window_seconds: float = 2.0) -> float:
    """
    Calculate frames per second from recent timestamps.
    
    Args:
        window_seconds: Time window for FPS calculation
        
    Returns:
        FPS (0 if insufficient data)
    """
    init_dsp_stats()
    stats = st.session_state.dsp_stats
    
    if len(stats['frame_timestamps']) < 2:
        return 0.0
    
    timestamps = list(stats['frame_timestamps'])
    if len(timestamps) < 2:
        return 0.0
    
    # Calculate FPS from last N timestamps within window
    now = time.time()
    recent = [t for t in timestamps if now - t <= window_seconds]
    
    if len(recent) < 2:
        return 0.0
    
    time_span = recent[-1] - recent[0]
    if time_span <= 0:
        return 0.0
    
    return (len(recent) - 1) / time_span


def calculate_wps(window_seconds: float = 2.0) -> float:
    """
    Calculate windows per second from recent timestamps.
    
    Args:
        window_seconds: Time window for WPS calculation
        
    Returns:
        WPS (0 if insufficient data)
    """
    init_dsp_stats()
    stats = st.session_state.dsp_stats
    
    if len(stats['window_timestamps']) < 2:
        return 0.0
    
    timestamps = list(stats['window_timestamps'])
    if len(timestamps) < 2:
        return 0.0
    
    # Calculate WPS from last N timestamps within window
    now = time.time()
    recent = [t for t in timestamps if now - t <= window_seconds]
    
    if len(recent) < 2:
        return 0.0
    
    time_span = recent[-1] - recent[0]
    if time_span <= 0:
        return 0.0
    
    return (len(recent) - 1) / time_span


def calculate_avg_fps() -> float:
    """Calculate average FPS since session start."""
    init_dsp_stats()
    stats = st.session_state.dsp_stats
    
    elapsed = time.time() - stats['session_start_time']
    if elapsed <= 0:
        return 0.0
    
    # Use frame_count from session state
    frame_count = st.session_state.get('frame_count', 0)
    return frame_count / elapsed if frame_count > 0 else 0.0


def calculate_avg_wps() -> float:
    """Calculate average windows per second since session start."""
    init_dsp_stats()
    stats = st.session_state.dsp_stats
    
    elapsed = time.time() - stats['session_start_time']
    if elapsed <= 0:
        return 0.0
    
    return stats['total_windows'] / elapsed if stats['total_windows'] > 0 else 0.0


def render_dsp_summary_table(config) -> None:
    """
    Render DSP Processing Summary table.
    
    Args:
        config: System configuration
    """
    init_dsp_stats()
    stats = st.session_state.dsp_stats
    
    # Get current values
    fft_size = config.rf.fft_size
    window_type = config.rf.window_type
    sample_rate = config.rf.sample_rate_sps
    overlap_pct = 0.0  # Default: no overlap (can be added to config later)
    
    # Calculate window duration
    window_duration_ms = (fft_size / sample_rate) * 1000.0
    
    # Get current/live metrics
    current_samples = stats['last_update_samples']
    current_windows = stats['last_update_windows']
    current_fps = calculate_fps()
    current_wps = calculate_wps()
    
    # Get totals
    total_samples = stats['total_iq_samples']
    total_windows = stats['total_windows']
    avg_fps = calculate_avg_fps()
    avg_wps = calculate_avg_wps()
    
    # Format values
    def fmt_samples(n: int) -> str:
        if n >= 1e6:
            return f"{n/1e6:.2f}M"
        elif n >= 1e3:
            return f"{n/1e3:.2f}K"
        return str(n)
    
    def fmt_float(v: float, decimals: int = 2) -> str:
        return f"{v:.{decimals}f}"
    
    # Create table data with tooltips
    # Note: Streamlit doesn't support native tooltips in dataframes, so we'll add descriptions in a separate section
    table_data = {
        "Metric": [
            "IQ samples processed",
            "Window type",
            "FFT size (samples)",
            "Window duration (ms)",
            "Overlap (%)",
            "Frames per second (fps)",
            "Windows processed",
            "Windows per second",
        ],
        "Current": [
            fmt_samples(current_samples) if current_samples > 0 else "—",
            window_type.title(),
            str(fft_size),
            fmt_float(window_duration_ms, 3),
            fmt_float(overlap_pct, 1),
            fmt_float(current_fps, 2) if current_fps > 0 else "—",
            str(current_windows) if current_windows > 0 else "—",
            fmt_float(current_wps, 2) if current_wps > 0 else "—",
        ],
        "Total": [
            fmt_samples(total_samples),
            window_type.title(),  # Same as current
            str(fft_size),  # Same as current
            fmt_float(window_duration_ms, 3),  # Same as current
            fmt_float(overlap_pct, 1),  # Same as current
            fmt_float(avg_fps, 2) if avg_fps > 0 else "0.00",
            str(total_windows),
            fmt_float(avg_wps, 2) if avg_wps > 0 else "0.00",
        ],
    }
    
    # Render table
    st.markdown("### 📊 DSP Processing Summary")
    
    # Add expandable help section
    with st.expander("ℹ️ What do these metrics mean?"):
        st.markdown("""
        **IQ samples processed:** Number of complex (I+jQ) signal samples processed. Each sample represents one time point of the RF signal.
        
        **Window type:** The windowing function applied before FFT to reduce spectral leakage. Hann window is most common.
        
        **FFT size:** Number of frequency bins in the FFT. Larger = better frequency resolution but slower processing.
        
        **Window duration:** Time span of each FFT window in milliseconds. Calculated as FFT_size / sample_rate.
        
        **Overlap (%):** Percentage of samples that overlap between consecutive windows. 0% = no overlap, 50% = half overlap.
        
        **Frames per second (fps):** How many IQ frames are processed per second. Higher = faster data ingestion.
        
        **Windows processed:** Total number of FFT windows computed. Each frame typically produces one window.
        
        **Windows per second:** Rate of FFT computation. Shows how fast the GPU is processing frequency transforms.
        """)
    
    st.dataframe(
        table_data,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Metric": st.column_config.TextColumn("Metric", width="medium"),
            "Current": st.column_config.TextColumn("Current", width="small"),
            "Total": st.column_config.TextColumn("Total", width="small"),
        }
    )
    
    # PSD Pipeline Summary
    st.markdown("#### PSD Computation Steps")
    st.markdown("""
    **1. Windowing (Hann)** – Reduces spectral leakage; prepares data for FFT  
    **2. FFT (CuPy/cuFFT)** – Time domain → frequency domain; complex bins  
    **3. Magnitude-squared** – P(f) = |FFT(f)|²  
    **4. Scale to dB** – PSD_dB = 10 × log₁₀(P)
    """)
    
    # DSP Throughput Relationships
    render_dsp_throughput_relationships(config)


def render_dsp_throughput_relationships(config) -> None:
    """
    Render DSP Throughput Relationships section.
    
    Shows derived mathematical relationships between sample rate, FFT size,
    hop size/overlap, frames/sec, windows/sec, and compute amplification.
    
    Args:
        config: System configuration
    """
    init_dsp_stats()
    stats = st.session_state.dsp_stats
    
    # Get inputs
    sample_rate_sps = config.rf.sample_rate_sps
    fft_size = config.rf.fft_size
    frames_processed_total = st.session_state.get('frame_count', 0)
    session_elapsed_seconds = time.time() - stats['session_start_time']
    
    # Get overlap/hop_size from config (if available)
    overlap_fraction = getattr(config.rf, 'overlap_fraction', None)
    hop_size_config = getattr(config.rf, 'hop_size', None)
    
    # Calculate hop size
    if hop_size_config is not None:
        hop_size = int(hop_size_config)
        overlap_fraction_actual = 1.0 - (hop_size / fft_size) if fft_size > 0 else 0.0
    elif overlap_fraction is not None:
        hop_size = int(fft_size * (1.0 - overlap_fraction))
        overlap_fraction_actual = overlap_fraction
    else:
        # Default: no overlap (hop_size = fft_size)
        hop_size = fft_size
        overlap_fraction_actual = 0.0
    
    # Derived calculations
    frame_duration_s = fft_size / sample_rate_sps if sample_rate_sps > 0 else 0.0
    hop_duration_s = hop_size / sample_rate_sps if sample_rate_sps > 0 else 0.0
    
    # Theoretical rates
    windows_per_sec_theoretical = sample_rate_sps / hop_size if hop_size > 0 else 0.0
    frames_per_sec_theoretical = windows_per_sec_theoretical  # Same for this pipeline
    
    # Samples processed per second (with overlap)
    samples_processed_per_sec_theoretical = frames_per_sec_theoretical * fft_size
    
    # Total IQ samples processed (cumulative)
    total_iq_samples_cumulative = frames_processed_total * fft_size
    
    # Compute multiplier (amplification due to overlap)
    compute_multiplier = fft_size / hop_size if hop_size > 0 else 1.0
    
    # Measured rates
    current_wps = calculate_wps()
    avg_wps = calculate_avg_wps()
    current_fps = calculate_fps()
    avg_fps = calculate_avg_fps()
    
    # Format helpers
    def fmt_ms(v: float) -> str:
        return f"{v * 1000:.3f}" if v > 0 else "—"
    
    def fmt_rate(v: float) -> str:
        return f"{v:.2f}" if v > 0 else "—"
    
    def fmt_multiplier(v: float) -> str:
        return f"{v:.2f}x" if v > 0 else "—"
    
    def fmt_samples(v: int) -> str:
        if v >= 1e9:
            return f"{v/1e9:.2f}B"
        elif v >= 1e6:
            return f"{v/1e6:.2f}M"
        elif v >= 1e3:
            return f"{v/1e3:.2f}K"
        return str(v)
    
    # Build table data
    relationships_data = {
        "Relationship": [
            "Hop size (samples)",
            "Frame duration (ms)",
            "Hop duration (ms)",
            "Windows/sec (theoretical)",
            "Windows/sec (measured current)",
            "Windows/sec (avg)",
            "Samples/sec processed (theoretical)",
            "Total samples processed (cumulative)",
            "Compute multiplier (overlap)",
        ],
        "Formula": [
            f"fft_size × (1 - overlap) = {hop_size}" if overlap_fraction_actual > 0 else f"fft_size = {hop_size}",
            f"fft_size / sample_rate = {frame_duration_s:.6f} s",
            f"hop_size / sample_rate = {hop_duration_s:.6f} s",
            f"sample_rate / hop_size = {windows_per_sec_theoretical:.2f}",
            "rolling timestamps (last 2s)",
            f"total_windows / elapsed = {avg_wps:.2f}",
            f"frames/sec × fft_size = {samples_processed_per_sec_theoretical:.0f}",
            f"frames_total × fft_size = {total_iq_samples_cumulative}",
            f"fft_size / hop_size = {compute_multiplier:.2f}x",
        ],
        "Value (Current)": [
            str(hop_size),
            fmt_ms(frame_duration_s),
            fmt_ms(hop_duration_s),
            fmt_rate(windows_per_sec_theoretical),
            fmt_rate(current_wps) if current_wps > 0 else "—",
            fmt_rate(avg_wps) if avg_wps > 0 else "0.00",
            fmt_samples(int(samples_processed_per_sec_theoretical)),
            fmt_samples(total_iq_samples_cumulative),
            fmt_multiplier(compute_multiplier),
        ],
        "Value (Avg/Theoretical)": [
            str(hop_size),  # Same
            fmt_ms(frame_duration_s),  # Same
            fmt_ms(hop_duration_s),  # Same
            fmt_rate(windows_per_sec_theoretical),  # Theoretical
            fmt_rate(current_wps) if current_wps > 0 else "—",  # Current measured
            fmt_rate(avg_wps) if avg_wps > 0 else "0.00",  # Average measured
            fmt_samples(int(samples_processed_per_sec_theoretical)),  # Theoretical
            fmt_samples(total_iq_samples_cumulative),  # Cumulative
            fmt_multiplier(compute_multiplier),  # Same
        ],
    }
    
    # Render section
    st.markdown("---")
    st.markdown("### 🔢 DSP Throughput Relationships (Derived)")
    st.caption("Mathematical relationships between sample rate, FFT size, hop/overlap, and processing rates")
    
    # Add expandable help section
    with st.expander("ℹ️ What are these relationships?"):
        st.markdown("""
        **Hop size:** Number of samples to advance between windows. With 50% overlap, hop = FFT_size/2.
        
        **Frame duration:** Time span of one FFT window. Determines frequency resolution.
        
        **Hop duration:** Time between consecutive windows. Smaller = more windows per second.
        
        **Windows/sec (theoretical):** Maximum processing rate based on sample rate and hop size.
        
        **Windows/sec (measured):** Actual processing rate from timestamps. Lower than theoretical due to GPU/CPU overhead.
        
        **Samples/sec processed:** Total samples processed per second (includes overlap). Higher with overlap.
        
        **Total samples processed:** Cumulative count since session start.
        
        **Compute multiplier:** How much more compute is needed vs. raw input rate. 2.0x = processing twice as many samples due to overlap.
        """)
    
    st.dataframe(
        relationships_data,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Relationship": st.column_config.TextColumn("Relationship", width="medium"),
            "Formula": st.column_config.TextColumn("Formula", width="large"),
            "Value (Current)": st.column_config.TextColumn("Current", width="small"),
            "Value (Avg/Theoretical)": st.column_config.TextColumn("Avg/Theoretical", width="small"),
        }
    )
    
    # Add explanatory note
    if overlap_fraction_actual > 0:
        st.info(f"ℹ️ **Overlap:** {overlap_fraction_actual*100:.1f}% overlap means each frame advances by {hop_size} samples "
                f"(instead of {fft_size}). This increases compute by {compute_multiplier:.2f}x vs. raw input rate.")
    else:
        st.info(f"ℹ️ **No overlap:** Each frame processes {fft_size} samples independently. "
                "Compute multiplier = 1.0x (no amplification).")


def reset_dsp_stats():
    """Reset DSP statistics (called on pipeline reset)."""
    if 'dsp_stats' in st.session_state:
        del st.session_state.dsp_stats
    init_dsp_stats()

