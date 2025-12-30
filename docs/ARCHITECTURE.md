# Architecture: GPU-Accelerated Sub-6 Spectrum Observatory

## Overview

This document describes the system architecture, data flow, and design decisions for the RF Spectrum Observatory.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Data Sources                             │
├─────────────────────────────────────────────────────────────────┤
│  [Synthetic IQ Source]          [Synthetic GPS Source]          │
│  (GPU generation)                (Route playback)                │
└────────────┬────────────────────────────┬─────────────────────────┘
             │                            │
             ▼                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Ingest & Buffering                          │
├─────────────────────────────────────────────────────────────────┤
│  • IQFrame (GPU complex64)                                       │
│  • GPSFix (timestamp, lat/lon)                                   │
│  • Ring buffers (pinned memory)                                  │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GPU DSP Pipeline                              │
├─────────────────────────────────────────────────────────────────┤
│  1. Window (Hann/Hamming)         [GPU: CuPy]                   │
│  2. FFT                            [GPU: cuFFT]                  │
│  3. PSD (linear → dB)              [GPU: CuPy]                   │
│  4. EMA Smoothing                  [GPU: CuPy]                   │
│  5. Noise Floor Estimation         [GPU: percentile]             │
│  6. Band Features (power, occ.)    [GPU: CuPy]                   │
│  7. GPS Alignment                  [CPU: timestamp match]        │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Geospatial Aggregation                           │
├─────────────────────────────────────────────────────────────────┤
│  • Tile Grid (deterministic)       [CPU: geometry]               │
│  • cuDF Aggregation (groupby)      [GPU: RAPIDS cuDF]            │
│  • Tile Metrics (mean, max, count) [GPU → CPU]                   │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ├────────────────┬──────────────────┬─────────────────┐
             ▼                ▼                  ▼                 ▼
┌────────────────────┬──────────────────┬──────────────────┬──────────────────┐
│   Spectrum Plot    │   Waterfall      │  2D Tile Map     │  3D Tile Map     │
│   (Plotly)         │   (Plotly)       │  (PyDeck)        │  (PyDeck)        │
├────────────────────┴──────────────────┴──────────────────┴──────────────────┤
│                          Streamlit Dashboard                                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. IQ Frame Generation

**Synthetic Source:**
- Generates complex64 samples on GPU (CuPy)
- 5 OFDM-like carriers (random subcarrier phases)
- Gaussian noise floor
- Optional interference (burst jammer, swept tone)
- Frame rate: limited by config `update_rate_hz`

**Future Hardware Source:**
- SoapySDR/UHD integration (stub provided)
- Host → GPU transfer via pinned memory
- Zero-copy where possible

### 2. GPS Alignment

**Timestamp-based matching:**
- IQ frames have `timestamp_ns` (system clock)
- GPS fixes have `gps_timestamp_ns` (GPS time)
- Alignment: find closest GPS fix within ±1 second
- Falls back to None if no GPS available

### 3. GPU DSP Pipeline

**Per-frame processing:**
1. Apply window function (pre-computed on GPU)
2. Compute FFT (cuFFT via CuPy)
3. Compute PSD: `|FFT|^2 / (N * fs * window_correction)`
4. FFTshift to center DC
5. Convert to dB with floor (-120 dB)
6. EMA smoothing: `state = alpha * new + (1-alpha) * state`
7. Estimate noise floor (10th percentile of smoothed PSD)
8. Extract band features:
   - **Bandpower:** integrate PSD over band (linear scale, then dB)
   - **Occupancy:** % of bins > (noise_floor + 6 dB)

**Performance:**
- ~2 ms per frame (4096-point FFT)
- ~500 FPS sustained (RTX 5090)

### 4. Geospatial Aggregation

**Tile Grid:**
- Deterministic grid (not dynamic clustering)
- Square tiles (default 50m x 50m)
- Covering 1km x 1km extent
- Grid alignment: lat/lon → tile_x, tile_y

**cuDF Aggregation:**
- Buffer frames (default: 100 frames)
- Convert to cuDF DataFrame (GPU)
- GroupBy `tile_id`
- Aggregate:
  - `bandpower`: mean, max
  - `occupancy`: mean
  - `timestamp`: min, max
  - `frame_id`: count

**Output:**
- TileMetrics objects (host memory)
- Ready for export or visualization

### 5. Visualization

**Plotly (2D charts):**
- **Spectrum:** Multi-trace line plot (current, smoothed, noise floor)
- **Waterfall:** Heatmap (time × frequency)
- Rendered in Streamlit (browser canvas)

**PyDeck (maps):**
- **2D Heatmap:** GeoJsonLayer with color-mapped tiles
- **3D Extrusion:** ColumnLayer with height = metric value
- Rendered via Deck.gl (WebGL)

## Design Decisions

### Why GPU-first??

**Rationale:**
- FFT is compute-bound (N log N)
- Large FFT sizes (4096+) amortize transfer overhead
- EMA smoothing is embarrassingly parallel
- Band feature extraction is parallel over bins

**Alternatives considered:**
- CPU-only (NumPy/SciPy): ~10x slower for large FFTs
- Hybrid CPU/GPU: overhead of transfers

**Decision:** Keep data on GPU until export/visualization.

---

### Current Architectural Limitation (Single-Process Design)

**Current Implementation:**
- Streamlit runs in a single-process loop with `st.rerun()`
- DSP + aggregation execute inline with UI refresh
- Processing cadence is coupled to UI update rate (default: 10 Hz)

**Implications:**
- ✅ **Simple:** No inter-process communication, easy to debug
- ✅ **Sufficient for demo/development:** Handles synthetic data at 10 Hz UI refresh
- ⚠️ **Limits scaling:** Cannot process faster than UI renders
- ⚠️ **Ties DSP to UI:** Processing rate = UI rate

**Future Decoupling (Phase 3):**
- Move DSP + aggregation to separate worker thread/process
- Use queue or shared memory for UI updates
- Allows DSP to run at hardware rate (500+ FPS) independent of UI (10 Hz)
- UI polls latest results asynchronously

**Why this is acceptable now:**
- Current synthetic data rate matches UI rate
- Real-time visualization is the primary goal (not batch processing)
- Single-process simplifies deployment and debugging

**When to refactor:**
- Hardware SDR input exceeds UI rate
- Need to decouple for remote/headless operation
- Batch processing requirements emerge

This design choice reflects **architectural maturity**: we understand the trade-off and can evolve when needed.

---

### Why RAPIDS cuDF for aggregation?

**Rationale:**
- Geospatial groupby is a DataFrame operation
- cuDF provides GPU-accelerated groupby (10-100x faster than pandas for large datasets)
- Future: cuSpatial for spatial joins/queries

**Alternatives considered:**
- Pandas (CPU): slower, but sufficient for small datasets
- Manual GPU kernels: overkill for groupby

**Decision:** Use cuDF for aggregation, export to host for Streamlit.

### Why Streamlit?

**Rationale:**
- Rapid prototyping (no HTML/JS/CSS)
- PyDeck integration for Deck.gl
- Session state for stateful dashboards
- Easy deployment

**Alternatives considered:**
- Flask + React: more work, better for production
- Qt/PyQt: desktop-only, no web deployment
- Panel + Datashader: RAPIDS-native, but less mature ecosystem

**Decision:** Streamlit for MVP, migrate to Panel/cuXfilter in Phase 3 if needed.

### Why Synthetic Sources?

**Rationale:**
- Deterministic testing (repeatable peaks, interference)
- No SDR hardware dependency
- Modular interface (swap in hardware later)

**Future:** Hardware sources implement same interface (`BaseIQSource`, `BaseGPSSource`).

## Memory Management

**RMM Pool Allocator:**
- Unified memory pool for CuPy + cuDF
- Reduces fragmentation
- Configurable size (default: 8 GB)

**Frame Buffers:**
- Ring buffers (max size: 1000 frames)
- Waterfall buffer (max: 200 frames)
- Tile metrics buffer (max: 1000 tiles)

**Export:**
- Convert GPU arrays to host (NumPy)
- Write Parquet (pandas) or GeoJSON (json)

## Performance Targets

| Metric                  | Target      | Achieved (RTX 5090) |
|-------------------------|-------------|---------------------|
| FFT (4096-point)        | < 0.1 ms    | 0.005 ms            |
| DSP Pipeline (per frame)| < 5 ms      | 2 ms                |
| Sustained FPS           | > 100 FPS   | 510 FPS             |
| GPU Memory              | < 8 GB      | ~2 GB               |
| UI Update Rate          | 10 Hz       | 10 Hz (configurable)|

## Extensibility

**Future Enhancements:**
1. **Hardware Sources:** SoapySDR, UHD, custom FPGA
2. **Advanced DSP:** Demodulation, channel estimation, beam forming
3. **Anomaly Detection:** Isolation Forest, Autoencoders (GPU)
4. **cuXfilter Integration:** Cross-filtering, interactive dashboards
5. **Distributed Processing:** Dask + RAPIDS for multi-GPU/multi-node

