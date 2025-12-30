"""
GPU / HPC Performance Monitor Page

Live CUDA + RAPIDS performance telemetry for this session.
Graphics-only dashboard with no tables.
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import sys
import os

# Add src to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from perf.gpu_telemetry import GPUTelemetry
from perf.ring_buffer import RingBuffer

# Page config
st.set_page_config(
    page_title="GPU / HPC Monitor",
    page_icon="🖥️",
    layout="wide",
)

st.title("🖥️ GPU / HPC Monitor")
st.markdown("**Live CUDA + RAPIDS performance telemetry for this session**")

# Initialize session state
if 'gpu_telemetry' not in st.session_state:
    st.session_state.gpu_telemetry = GPUTelemetry(gpu_index=0)

if 'history_buffers' not in st.session_state:
    st.session_state.history_buffers = {
        'gpu_util': RingBuffer(max_size=300),
        'mem_used': RingBuffer(max_size=300),
        'power_draw': RingBuffer(max_size=300),
        'cpu_percent': RingBuffer(max_size=300),
        'num_threads': RingBuffer(max_size=300),
        'temperature': RingBuffer(max_size=300),
    }

if 'last_update_time' not in st.session_state:
    st.session_state.last_update_time = 0

# Sidebar controls
st.sidebar.markdown("## ⚙️ Monitor Settings")

# Enable/Disable monitoring (performance control)
if 'gpu_monitor_enabled' not in st.session_state:
    st.session_state.gpu_monitor_enabled = False

monitor_enabled = st.sidebar.checkbox(
    "🟢 Enable Live Monitoring",
    value=st.session_state.gpu_monitor_enabled,
    help="Enable real-time GPU telemetry collection and auto-refresh. Disable to improve app performance."
)
st.session_state.gpu_monitor_enabled = monitor_enabled

if not monitor_enabled:
    st.warning("⚠️ GPU monitoring is **disabled**. Check the box above to enable live telemetry and auto-refresh.")
    st.info("💡 **Tip:** Keeping monitoring disabled improves overall app performance when you're not actively viewing this page.")
    st.stop()

st.sidebar.markdown("---")

refresh_rate_hz = st.sidebar.slider("Refresh Rate (Hz)", 0.5, 5.0, 2.0, 0.5)
history_length_sec = st.sidebar.slider("History Length (seconds)", 30, 300, 120, 30)
gpu_index = st.sidebar.selectbox("GPU Index", [0, 1, 2, 3], index=0)

# Update GPU index if changed
if st.session_state.gpu_telemetry.gpu_index != gpu_index:
    st.session_state.gpu_telemetry = GPUTelemetry(gpu_index=gpu_index)

# Auto-refresh logic
current_time = time.time()
update_interval = 1.0 / refresh_rate_hz

# Check if it's time to collect new metrics
should_collect = current_time - st.session_state.last_update_time >= update_interval

if should_collect:
    st.session_state.last_update_time = current_time
    
    # Collect metrics
    gpu_metrics = st.session_state.gpu_telemetry.get_metrics()
    proc_metrics = st.session_state.gpu_telemetry.get_process_metrics()
    
    # Append to buffers
    st.session_state.history_buffers['gpu_util'].append(gpu_metrics.gpu_utilization_pct, current_time)
    st.session_state.history_buffers['mem_used'].append(gpu_metrics.memory_used_gb, current_time)
    st.session_state.history_buffers['power_draw'].append(gpu_metrics.power_draw_w, current_time)
    st.session_state.history_buffers['cpu_percent'].append(proc_metrics['cpu_percent'], current_time)
    st.session_state.history_buffers['num_threads'].append(proc_metrics['num_threads'], current_time)
    st.session_state.history_buffers['temperature'].append(gpu_metrics.temperature_c, current_time)
    
    # Store latest metrics for gauges
    st.session_state.latest_gpu_metrics = gpu_metrics
    st.session_state.latest_proc_metrics = proc_metrics

# Check if GPU is available
if not st.session_state.latest_gpu_metrics.available:
    st.error("⚠️ GPU not detected. Telemetry unavailable.")
    st.info("Ensure NVIDIA drivers and CUDA are installed, or pynvml/nvidia-smi is available.")
    st.stop()

# Get latest metrics
gpu = st.session_state.latest_gpu_metrics
proc = st.session_state.latest_proc_metrics

# Display GPU info banner
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("GPU", gpu.gpu_name)
with col2:
    st.metric("Driver", gpu.driver_version)
with col3:
    st.metric("Temperature", f"{gpu.temperature_c:.1f}°C" if gpu.temperature_c else "N/A")
with col4:
    st.metric("Power", f"{gpu.power_draw_w:.1f}W / {gpu.power_limit_w:.0f}W" if gpu.power_draw_w and gpu.power_limit_w else "N/A")

st.markdown("---")

# ============================================================================
# SECTION A: Live GPU Utilization Timeline
# ============================================================================
st.markdown("### 📈 Live GPU Utilization Timeline")

# Get history data (trim to history_length_sec)
timestamps_gpu, gpu_util_vals = st.session_state.history_buffers['gpu_util'].get_arrays()
timestamps_mem, mem_used_vals = st.session_state.history_buffers['mem_used'].get_arrays()
timestamps_pwr, power_draw_vals = st.session_state.history_buffers['power_draw'].get_arrays()

# Filter to history_length_sec
cutoff_time = current_time - history_length_sec
timestamps_gpu = [t - current_time for t in timestamps_gpu if t >= cutoff_time]
gpu_util_vals = [v for t, v in zip(st.session_state.history_buffers['gpu_util'].timestamps, gpu_util_vals) if t >= cutoff_time]

timestamps_mem = [t - current_time for t in timestamps_mem if t >= cutoff_time]
mem_used_vals = [v for t, v in zip(st.session_state.history_buffers['mem_used'].timestamps, mem_used_vals) if t >= cutoff_time]

timestamps_pwr = [t - current_time for t in timestamps_pwr if t >= cutoff_time]
power_draw_vals = [v for t, v in zip(st.session_state.history_buffers['power_draw'].timestamps, power_draw_vals) if t >= cutoff_time]

# Create subplot with 3 y-axes
fig_timeline = make_subplots(specs=[[{"secondary_y": True}]])

# GPU Utilization %
fig_timeline.add_trace(
    go.Scatter(
        x=timestamps_gpu,
        y=gpu_util_vals,
        name="GPU Utilization (%)",
        line=dict(color='#00ff00', width=2),
        mode='lines',
    ),
    secondary_y=False,
)

# VRAM Used (GB)
fig_timeline.add_trace(
    go.Scatter(
        x=timestamps_mem,
        y=mem_used_vals,
        name="VRAM Used (GB)",
        line=dict(color='#ffaa00', width=2),
        mode='lines',
    ),
    secondary_y=True,
)

# Power Draw (W) - if available
if any(v is not None for v in power_draw_vals):
    fig_timeline.add_trace(
        go.Scatter(
            x=timestamps_pwr,
            y=power_draw_vals,
            name="Power Draw (W)",
            line=dict(color='#ff0000', width=2, dash='dash'),
            mode='lines',
        ),
        secondary_y=True,
    )

fig_timeline.update_xaxes(title_text="Time (seconds ago)", range=[min(timestamps_gpu) if timestamps_gpu else -history_length_sec, 0])
fig_timeline.update_yaxes(title_text="GPU Utilization (%)", secondary_y=False, range=[0, 100])
fig_timeline.update_yaxes(title_text="VRAM (GB) / Power (W)", secondary_y=True)

fig_timeline.update_layout(
    height=400,
    template='plotly_dark',
    hovermode='x unified',
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)

st.plotly_chart(fig_timeline, use_container_width=True)

st.markdown("---")

# ============================================================================
# SECTION B: Memory Breakdown (Donut + Gauge)
# ============================================================================
st.markdown("### 💾 Memory Breakdown")

col1, col2 = st.columns(2)

with col1:
    # Donut chart: VRAM breakdown
    if gpu.memory_total_gb and gpu.memory_used_gb and gpu.memory_free_gb:
        fig_donut = go.Figure(data=[go.Pie(
            labels=['Used', 'Free'],
            values=[gpu.memory_used_gb, gpu.memory_free_gb],
            hole=0.6,
            marker=dict(colors=['#ff6b6b', '#51cf66']),
            textinfo='label+percent',
        )])
        fig_donut.update_layout(
            title_text=f"VRAM: {gpu.memory_used_gb:.2f} / {gpu.memory_total_gb:.2f} GB",
            height=350,
            template='plotly_dark',
            showlegend=True,
        )
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.info("VRAM data unavailable.")

with col2:
    # Gauge: VRAM Pressure
    if gpu.memory_total_gb and gpu.memory_used_gb:
        vram_pressure = (gpu.memory_used_gb / gpu.memory_total_gb) * 100
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=vram_pressure,
            title={'text': "VRAM Pressure (%)"},
            delta={'reference': 80},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': "#1f77b4"},
                'steps': [
                    {'range': [0, 50], 'color': "#51cf66"},
                    {'range': [50, 80], 'color': "#ffd43b"},
                    {'range': [80, 100], 'color': "#ff6b6b"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        fig_gauge.update_layout(height=350, template='plotly_dark')
        st.plotly_chart(fig_gauge, use_container_width=True)
    else:
        st.info("VRAM pressure unavailable.")

st.markdown("---")

# ============================================================================
# SECTION C: Throughput + Batching Visualization
# ============================================================================
st.markdown("### ⚡ Throughput + Batching")

col1, col2, col3 = st.columns(3)

# Get pipeline stats from main session state (read-only)
# Try to get from dsp_stats first, then fall back to old attributes
dsp_stats = getattr(st.session_state, 'dsp_stats', {})
frames_per_sec = dsp_stats.get('fps_current', getattr(st.session_state, 'frames_per_sec', None))
windows_per_sec = dsp_stats.get('wps_current', getattr(st.session_state, 'windows_per_sec_current', None))

with col1:
    # Frames/sec gauge
    if frames_per_sec is not None:
        fig_fps = go.Figure(go.Indicator(
            mode="gauge+number",
            value=frames_per_sec,
            title={'text': "Frames/sec"},
            gauge={
                'axis': {'range': [0, 50]},
                'bar': {'color': "#00d4ff"},
                'steps': [
                    {'range': [0, 10], 'color': "#ff6b6b"},
                    {'range': [10, 30], 'color': "#ffd43b"},
                    {'range': [30, 50], 'color': "#51cf66"}
                ],
            }
        ))
        fig_fps.update_layout(height=300, template='plotly_dark')
        st.plotly_chart(fig_fps, use_container_width=True)
    else:
        st.metric("Frames/sec", "N/A")

with col2:
    # Windows/sec gauge
    if windows_per_sec is not None:
        fig_wps = go.Figure(go.Indicator(
            mode="gauge+number",
            value=windows_per_sec,
            title={'text': "Windows/sec"},
            gauge={
                'axis': {'range': [0, 50]},
                'bar': {'color': "#ff6b6b"},
                'steps': [
                    {'range': [0, 10], 'color': "#ff6b6b"},
                    {'range': [10, 30], 'color': "#ffd43b"},
                    {'range': [30, 50], 'color': "#51cf66"}
                ],
            }
        ))
        fig_wps.update_layout(height=300, template='plotly_dark')
        st.plotly_chart(fig_wps, use_container_width=True)
    else:
        st.metric("Windows/sec", "N/A")

with col3:
    # Batch size indicator (inferred as 1 if not implemented)
    batch_size = getattr(st.session_state, 'frames_per_refresh', 1)
    fig_batch = go.Figure(go.Bar(
        x=['Batch Size'],
        y=[batch_size],
        marker=dict(color='#845ef7'),
        text=[batch_size],
        textposition='auto',
    ))
    fig_batch.update_layout(
        title_text="Frames per UI Refresh",
        height=300,
        template='plotly_dark',
        yaxis=dict(range=[0, 20]),
        showlegend=False,
    )
    st.plotly_chart(fig_batch, use_container_width=True)

st.markdown("---")

# ============================================================================
# SECTION D: Concurrency / Threading Indicators
# ============================================================================
st.markdown("### 🔀 Concurrency / Threading")

col1, col2 = st.columns(2)

with col1:
    # CPU usage timeline
    timestamps_cpu, cpu_vals = st.session_state.history_buffers['cpu_percent'].get_arrays()
    timestamps_cpu = [t - current_time for t in timestamps_cpu if t >= cutoff_time]
    cpu_vals = [v for t, v in zip(st.session_state.history_buffers['cpu_percent'].timestamps, cpu_vals) if t >= cutoff_time]
    
    fig_cpu = go.Figure()
    fig_cpu.add_trace(go.Scatter(
        x=timestamps_cpu,
        y=cpu_vals,
        name="CPU Usage (%)",
        line=dict(color='#845ef7', width=2),
        mode='lines+markers',
        fill='tozeroy',
    ))
    fig_cpu.update_xaxes(title_text="Time (seconds ago)", range=[min(timestamps_cpu) if timestamps_cpu else -history_length_sec, 0])
    fig_cpu.update_yaxes(title_text="CPU Usage (%)", range=[0, 100])
    fig_cpu.update_layout(
        title_text="Python Process CPU Usage",
        height=300,
        template='plotly_dark',
        hovermode='x unified',
    )
    st.plotly_chart(fig_cpu, use_container_width=True)

with col2:
    # Thread count timeline
    timestamps_threads, thread_vals = st.session_state.history_buffers['num_threads'].get_arrays()
    timestamps_threads = [t - current_time for t in timestamps_threads if t >= cutoff_time]
    thread_vals = [v for t, v in zip(st.session_state.history_buffers['num_threads'].timestamps, thread_vals) if t >= cutoff_time]
    
    fig_threads = go.Figure()
    fig_threads.add_trace(go.Scatter(
        x=timestamps_threads,
        y=thread_vals,
        name="Thread Count",
        line=dict(color='#20c997', width=2),
        mode='lines+markers',
        fill='tozeroy',
    ))
    fig_threads.update_xaxes(title_text="Time (seconds ago)", range=[min(timestamps_threads) if timestamps_threads else -history_length_sec, 0])
    fig_threads.update_yaxes(title_text="Thread Count")
    fig_threads.update_layout(
        title_text="Python Process Thread Count",
        height=300,
        template='plotly_dark',
        hovermode='x unified',
    )
    st.plotly_chart(fig_threads, use_container_width=True)

st.markdown("---")

# Temperature timeline (bonus)
st.markdown("### 🌡️ GPU Temperature")
timestamps_temp, temp_vals = st.session_state.history_buffers['temperature'].get_arrays()
timestamps_temp = [t - current_time for t in timestamps_temp if t >= cutoff_time]
temp_vals = [v for t, v in zip(st.session_state.history_buffers['temperature'].timestamps, temp_vals) if t >= cutoff_time]

fig_temp = go.Figure()
fig_temp.add_trace(go.Scatter(
    x=timestamps_temp,
    y=temp_vals,
    name="Temperature (°C)",
    line=dict(color='#ff8787', width=2),
    mode='lines',
    fill='tozeroy',
))
fig_temp.update_xaxes(title_text="Time (seconds ago)", range=[min(timestamps_temp) if timestamps_temp else -history_length_sec, 0])
fig_temp.update_yaxes(title_text="Temperature (°C)")
fig_temp.update_layout(
    height=300,
    template='plotly_dark',
    hovermode='x unified',
)
st.plotly_chart(fig_temp, use_container_width=True)

# Footer
st.markdown("---")
st.caption("🖥️ GPU/HPC telemetry updated at " + f"{refresh_rate_hz:.1f} Hz" + " | Data retained for " + f"{history_length_sec}s")

# Auto-refresh: Only rerun if monitoring is enabled
if st.session_state.gpu_monitor_enabled:
    time.sleep(update_interval)
    st.rerun()

