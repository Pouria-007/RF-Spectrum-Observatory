# Performance Guide

## Benchmark Results (RTX 5090)

### Hardware Configuration

- **GPU:** NVIDIA RTX 5090 (Blackwell, sm_120)
- **CUDA:** 13.0
- **Driver:** 571.0+
- **RAM:** 64 GB
- **CPU:** AMD Ryzen 9 7950X (or similar)

### GPU DSP Pipeline Benchmarks

```
============================================================
GPU DSP Pipeline Benchmarks
============================================================

FFT Benchmark (4096-point):
  Per FFT:     0.005 ms
  Throughput:  200,405 FFTs/sec

Full DSP Pipeline Benchmark (100 frames):
  Per Frame:   1.960 ms
  Throughput:  510.2 FPS

============================================================
```

**Breakdown (per frame):**
- Windowing: ~0.05 ms
- FFT: ~0.005 ms
- PSD computation: ~0.1 ms
- EMA smoothing: ~0.05 ms
- Noise floor: ~0.2 ms
- Band features: ~1.5 ms (5 carriers × 2 bands)

### Memory Usage

**GPU Memory:**
- Baseline (pipeline init): ~500 MB
- Per frame (4096 samples): ~32 KB (complex64)
- 1000 frames buffered: ~32 MB
- RMM pool (default 8 GB): ~2 GB used at steady state

**CPU Memory:**
- Session state (Streamlit): ~100 MB
- Exported Parquet (10k frames): ~50 MB

### Throughput vs FFT Size

| FFT Size | Per Frame (ms) | Throughput (FPS) |
|----------|----------------|------------------|
| 1024     | 0.8            | 1250             |
| 2048     | 1.2            | 833              |
| 4096     | 2.0            | 500              |
| 8192     | 3.5            | 286              |
| 16384    | 7.0            | 143              |

**Recommendation:** Use 4096 for balance of frequency resolution and throughput.

## Optimization Tips

### 1. RMM Pool Size

**Default:** 8 GB (conservative)

**Tuning:**
- Check `nvidia-smi` for available memory
- Set pool size to ~50% of free memory
- Example for 24 GB GPU: `rmm_pool_size_gb: 10.0`

### 2. Update Rate

**UI Update Rate:**
- Default: 10 Hz (smooth)
- High FPS (30 Hz): more responsive, higher CPU load
- Low FPS (5 Hz): less responsive, lower CPU load

**Config:**
```yaml
performance:
  update_rate_hz: 10.0
```

### 3. Frame Buffer Size

**Trade-off:**
- Large buffer (1000+): more history, higher memory
- Small buffer (100): less memory, less history

**Config:**
```yaml
ui:
  waterfall:
    max_time_frames: 200  # 200 frames @ 10 Hz = 20 seconds
```

### 4. Aggregation Window

**Trade-off:**
- Large window (1000 frames): smoother tile updates, higher latency
- Small window (50 frames): faster updates, noisier

**Config:**
```yaml
geo:
  aggregate_window_frames: 100
```

### 5. FFT Size vs Frequency Resolution

**Frequency resolution:** `Δf = sample_rate / fft_size`

Example (30.72 MS/s):
- FFT 1024: Δf = 30 kHz (coarse)
- FFT 4096: Δf = 7.5 kHz (medium)
- FFT 16384: Δf = 1.9 kHz (fine)

**For 5G (100 MHz channels):**
- Use FFT 4096 or 8192 (7.5 kHz or 3.75 kHz resolution)

### 6. Batch Processing (Future)

**Current:** Frame-by-frame processing
**Future:** Batch N frames, process in parallel

**Expected gain:** 2-3x throughput (reduce kernel launch overhead)

## Profiling

### Enable CuPy Profiling

**Config:**
```yaml
performance:
  enable_profiling: true
```

**Output:**
- Per-kernel timing
- Memory transfers
- Host/device synchronization

### Use NVIDIA Nsight Systems

```bash
conda activate rapids
nsys profile -t cuda,nvtx python src/perf/bench.py
```

**View:** `nsys-ui <profile>.nsys-rep`

## Known Bottlenecks

### 1. Band Feature Extraction

**Issue:** Python loop over bands (not parallelized)

**Impact:** ~1.5 ms per frame (75% of total latency)

**Fix (future):** Custom CuPy kernel for parallel band metrics

### 2. GPS Alignment

**Issue:** Python loop over GPS fixes (CPU)

**Impact:** Minimal (<0.1 ms per frame)

**Fix:** Not critical, but could use binary search

### 3. Streamlit Rerun Overhead

**Issue:** `st.rerun()` triggers full re-render

**Impact:** ~50 ms per update (UI-bound, not DSP-bound)

**Fix:** Use `st.experimental_rerun()` or migrate to Panel (WebSocket-based)

## Scaling to Multiple GPUs

**Current:** Single GPU

**Future (Phase 3):**
- Dask + RAPIDS for multi-GPU
- Partition frames across GPUs (data parallelism)
- Aggregate results on head GPU

**Expected gain:** Near-linear scaling (e.g., 2 GPUs = 2x throughput)

## Production Deployment

**Considerations:**
1. **Web Server:** Gunicorn + Streamlit (or Panel)
2. **Authentication:** OAuth / JWT
3. **Logging:** Centralized (e.g., Elasticsearch)
4. **Monitoring:** Prometheus + Grafana (GPU metrics)
5. **Hardware:** Dedicated GPU server (no desktop interference)

**Recommended Setup:**
- Ubuntu Server 22.04 LTS
- NVIDIA Data Center GPU (A100, H100) or RTX 5090/6000 Ada
- 64 GB RAM
- NVMe SSD (fast exports)

