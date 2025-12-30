# User Interface Guide

## Overview

The RF Spectrum Observatory provides a live dashboard with four main visualizations:

1. **2D Spectrum (Multi-Trace):** Line plot of power vs frequency
2. **2D Waterfall/Spectrogram:** Time-frequency heatmap
3. **2D Tile Heatmap Map:** Geospatial grid with color-coded metrics
4. **3D Extruded Map:** 3D columns showing metric intensity

## Launching the Dashboard

```bash
# From the project root directory
conda activate rapids
streamlit run src/streamlit_app.py
```

**Default URL:** `http://localhost:8501`

---

## Dashboard Layout

### Header

- **Title:** RF Spectrum Observatory
- **RF Parameters:** Center frequency, sample rate
- **Status Metrics:**
  - Frames Processed
  - Tiles (aggregated)
  - Pipeline Status (Running/Stopped)

### Main Area

**Row 1: Spectral Visualizations**

- **Left:** 2D Spectrum (Plotly line plot)
  - **Traces:**
    - Current PSD (green)
    - Smoothed PSD (orange)
    - Noise Floor (red, dashed)
  - **Axes:**
    - X: Frequency (MHz)
    - Y: Power (dB)
  - **Hover:** Shows exact frequency and power

- **Right:** 2D Waterfall/Spectrogram (Plotly heatmap)
  - **Axes:**
    - X: Frequency (MHz)
    - Y: Time (frame number)
    - Color: Power (dB)
  - **Colorscale:** Viridis (configurable)

**Row 2: Geospatial Map**

- **Map Type:**
  - 2D Heatmap (default)
  - 3D Extrusion (toggle in sidebar)

- **Layers:**
  - Base polygons (city block, house)
  - Tile layer (color/height = metric)

- **Interaction:**
  - Pan/zoom
  - Click tile for details
  - Rotate (3D mode)

---

## Sidebar Controls

### Pipeline

- **Run Pipeline:** Checkbox to start/stop data processing
  - When **ON:** Continuously generates IQ frames, processes DSP, updates UI
  - When **OFF:** Pipeline paused (displays last frame)

- **Update Rate (Hz):** Slider (1-30 Hz)
  - Controls UI refresh rate
  - Higher = more responsive, higher CPU load

- **Max Frames:** Number input (10-1000)
  - Maximum frames to buffer (rolling window)
  - Older frames discarded when limit reached

### Map Settings

- **3D Extrusion:** Checkbox
  - If **ON:** 3D column map (pitch = 45°)
  - If **OFF:** 2D heatmap (pitch = 0°)

- **Metric:** Dropdown
  - `bandpower_mean`: Average power in band
  - `bandpower_max`: Peak power in band
  - `occupancy_mean`: Average occupancy (%)

- **Band Index:** Number input (0-10)
  - Which frequency band to visualize
  - Band 0: CBRS Band 48 (3.55-3.7 GHz)
  - Band 1: 5G n77 subset (3.5-3.6 GHz)

- **3D Height Scale:** Slider (1-50)
  - Extrusion multiplier (3D mode only)
  - Higher = taller columns

- **Zoom:** Slider (10-18)
  - Map zoom level
  - 15 = street-level view

- **Pitch:** Slider (0-60)
  - 3D viewing angle
  - 0° = top-down (2D)
  - 45° = oblique (3D)

### Export

- **Export Data:** Button
  - Exports current session data to:
    - `outputs/frames.parquet` (frame features)
    - `outputs/tiles.parquet` (tile metrics)
    - `outputs/tiles.geojson` (tile geometries)

### Reset

- **Reset Pipeline:** Button
  - Clears all buffers (frames, tiles, waterfall)
  - Restarts IQ/GPS sources
  - Resets DSP pipeline state (EMA filter)

---

## Typical Workflow

### 1. Initial Setup

1. Launch dashboard: `streamlit run src/streamlit_app.py`
2. Wait for browser to open (auto-refresh after 2-3 seconds)
3. Verify config loaded (check header for RF parameters)

### 2. Start Pipeline

1. In sidebar, check **"Run Pipeline"**
2. Observe status change to **"Running"**
3. Watch frame counter increment
4. Spectrum plot updates in real-time

### 3. Observe Spectrum

- **Green trace (Current PSD):** Raw spectrum, noisy
- **Orange trace (Smoothed PSD):** EMA-filtered, cleaner
- **Red dashed (Noise Floor):** Estimated baseline

**What to look for:**
- **Peaks:** Simulated carriers (~5 visible)
- **Interference:** Burst jammer (periodic spikes)
- **Noise floor:** ~-80 dB (configurable)

### 4. Observe Waterfall

- **X-axis:** Frequency (same as spectrum)
- **Y-axis:** Time (most recent at top)
- **Colors:** Brighter = higher power

**What to look for:**
- Vertical lines (persistent carriers)
- Horizontal bands (time-varying interference)

### 5. Observe Map

#### 2D Heatmap Mode (default)

- **Tiles light up:** As GPS route progresses
- **Color:** Metric intensity (red = high, blue = low)
- **Tooltip:** Hover over tile to see:
  - Tile ID (e.g., `tile_x10_y9`)
  - Metric value (e.g., `-61.8 dB`)

#### 3D Extrusion Mode

1. Check **"3D Extrusion"** in sidebar
2. Adjust **"Pitch"** to 45° (oblique view)
3. Observe 3D columns:
   - **Height:** Metric value (scaled by "3D Height Scale")
   - **Color:** Same as 2D (metric intensity)
4. Rotate map (click + drag)

### 6. Adjust Visualization

**Change metric:**
- Dropdown: `bandpower_mean` → `occupancy_mean`
- Observe map colors/heights update

**Change band:**
- Band Index: 0 → 1
- Compare different frequency bands

**Adjust update rate:**
- Slider: 10 Hz → 30 Hz (faster updates)
- Or: 10 Hz → 5 Hz (lower CPU load)

### 7. Export Data

1. Click **"Export Data"** button
2. Check `outputs/` directory:
   - `frames.parquet`: Per-frame features (lat/lon, bandpower, occupancy)
   - `tiles.parquet`: Tile aggregations (mean/max/count)
   - `tiles.geojson`: Tile geometries (viewable in QGIS, etc.)

### 8. Reset and Re-run

1. Click **"Reset Pipeline"**
2. Observe UI clear (empty charts)
3. Check **"Run Pipeline"** again to restart

---

## Advanced Features

### Offline Analysis

**Load exported Parquet:**
```python
import pandas as pd

frames = pd.read_parquet('outputs/frames.parquet')
tiles = pd.read_parquet('outputs/tiles.parquet')

# Analyze bandpower over time
frames['bandpower_db_0'].plot()
```

**View GeoJSON in QGIS:**
1. Open QGIS
2. Drag `tiles.geojson` into map
3. Style by attribute (e.g., `bandpower_mean_db_0`)

### Custom Configuration

**Edit `config/default.yaml`:**

```yaml
# Change RF parameters
rf:
  center_freq_hz: 2_450_000_000  # 2.45 GHz (WiFi)
  sample_rate_sps: 20_000_000     # 20 MS/s
  fft_size: 8192                  # Higher resolution

# Change map center
geo:
  map_center_lat: 40.7128         # New York City
  map_center_lon: -74.0060
```

**Reload:** Restart Streamlit app

### Performance Tuning

**High FPS (low latency):**
```yaml
performance:
  update_rate_hz: 30.0
```

**Low memory (embedded systems):**
```yaml
performance:
  max_frames_buffer: 100
ui:
  waterfall:
    max_time_frames: 50
```

---

## Troubleshooting

### Dashboard Not Loading

**Symptom:** Browser shows "Please wait..."

**Fix:**
1. Check terminal for errors
2. Verify config loaded: `python -c "from src.common import load_config; load_config('config/default.yaml')"`
3. Restart Streamlit

### Pipeline Not Running

**Symptom:** Frame counter stuck at 0

**Fix:**
1. Ensure **"Run Pipeline"** is checked
2. Check terminal for errors (e.g., GPU memory full)
3. Reset pipeline and try again

### Map Not Showing Tiles

**Symptom:** Map shows only base polygons (no tiles)

**Fix:**
1. Wait for aggregation window to fill (default: 100 frames)
2. Check GPS fixes are valid (terminal logs)
3. Verify tile grid covers GPS route (check `map_center_lat/lon`)

### Slow Updates

**Symptom:** UI lags, low FPS

**Fix:**
1. Lower **"Update Rate"** (e.g., 5 Hz)
2. Reduce **"Max Frames"** (e.g., 50)
3. Close other GPU-intensive apps

---

## Keyboard Shortcuts (Streamlit)

- **R:** Rerun app (same as clicking "Rerun")
- **Ctrl+C:** Stop server (in terminal)

---

## Mobile/Tablet Support

**Responsive Design:**
- Dashboard adapts to smaller screens
- Sidebar collapses to hamburger menu
- Charts stack vertically

**Recommendations:**
- Use landscape orientation
- Desktop/laptop preferred for best experience

