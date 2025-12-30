# Module Interfaces

This document defines the contracts for all major interfaces in the system.

## IQ Sources

### `BaseIQSource` (Abstract)

**Purpose:** Abstract interface for IQ sample sources (synthetic, hardware)

**Methods:**

```python
def start(self) -> None:
    """Initialize and start the source."""
    
def stop(self) -> None:
    """Stop the source and release resources."""
    
def get_frame(self) -> IQFrame:
    """
    Get a single IQ frame (blocking).
    
    Returns:
        IQFrame with complex64 samples (GPU array)
    """
```

**Implementations:**
- `SyntheticIQSource`: Deterministic synthetic signals
- `HardwareIQSource` (stub): Real SDR (SoapySDR, UHD)

---

## GPS Sources

### `BaseGPSSource` (Abstract)

**Purpose:** Abstract interface for GPS fix sources (synthetic, hardware)

**Methods:**

```python
def start(self) -> None:
    """Initialize and start the source."""
    
def stop(self) -> None:
    """Stop the source and release resources."""
    
def get_fix(self) -> Optional[GPSFix]:
    """
    Get a single GPS fix (non-blocking).
    
    Returns:
        GPSFix or None if no fix available
    """
```

**Implementations:**
- `SyntheticGPSSource`: Route playback from CSV
- `HardwareGPSSource` (stub): Real GPS (NMEA, serial)

---

## Data Types

### `IQFrame`

**Purpose:** Single IQ sample frame from SDR

**Fields:**
```python
@dataclass
class IQFrame:
    frame_id: int                # Monotonic frame counter
    timestamp_ns: int            # Nanosecond timestamp
    center_freq_hz: float        # RF center frequency
    sample_rate_sps: float       # Samples per second
    gain_db: Optional[float]     # Receiver gain (None if N/A)
    iq: cp.ndarray               # Complex64 samples (GPU)
```

**Constraints:**
- `iq` must be 1D complex64 CuPy array
- `frame_id` must be monotonically increasing

---

### `GPSFix`

**Purpose:** Single GPS position fix

**Fields:**
```python
@dataclass
class GPSFix:
    gps_timestamp_ns: int         # GPS timestamp (ns)
    lat_deg: float                # Latitude (-90 to 90)
    lon_deg: float                # Longitude (-180 to 180)
    alt_m: Optional[float]        # Altitude (meters)
    heading_deg: Optional[float]  # Heading (0=N, 90=E)
    speed_mps: Optional[float]    # Speed (m/s)
```

**Constraints:**
- `lat_deg` in [-90, 90]
- `lon_deg` in [-180, 180]

---

### `FrameFeatures`

**Purpose:** DSP features extracted from IQFrame

**Fields:**
```python
@dataclass
class FrameFeatures:
    frame_id: int
    timestamp_ns: int
    lat_deg: Optional[float]
    lon_deg: Optional[float]
    
    # Spectral (GPU arrays)
    freq_bins_hz: cp.ndarray      # (fft_size//2,) float32
    psd_db: cp.ndarray            # (fft_size//2,) float32
    psd_smoothed_db: cp.ndarray   # (fft_size//2,) float32
    noise_floor_db: float         # Scalar (dB)
    
    # Band metrics (host lists)
    bandpower_db: List[float]
    occupancy_pct: List[float]
    
    anomaly_score: Optional[float]
```

**Methods:**
```python
def to_host(self) -> dict:
    """Convert GPU arrays to host (NumPy) for export."""
```

---

### `TileMetrics`

**Purpose:** Aggregated metrics for a spatial tile

**Fields:**
```python
@dataclass
class TileMetrics:
    tile_id: str
    tile_x: int
    tile_y: int
    
    # Geospatial bounds
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    
    # Aggregated metrics
    frame_count: int
    timestamp_min_ns: int
    timestamp_max_ns: int
    bandpower_mean_db: List[float]
    bandpower_max_db: List[float]
    occupancy_mean_pct: List[float]
    anomaly_score_max: Optional[float]
```

**Methods:**
```python
def to_dict(self) -> dict:
    """Convert to dictionary for export."""
```

---

## DSP Pipeline

### `DSPPipeline`

**Purpose:** GPU-accelerated DSP pipeline (IQFrame → FrameFeatures)

**Constructor:**
```python
def __init__(
    self,
    fft_size: int,
    window_type: str,
    smoothing_factor: float,
    noise_floor_percentile: float,
    bands: List[Band],
):
```

**Methods:**

```python
def add_gps_fix(self, fix: GPSFix) -> None:
    """Add GPS fix to buffer for alignment."""

def process_frame(self, frame: IQFrame) -> FrameFeatures:
    """
    Process IQ frame → features.
    
    Args:
        frame: IQFrame with IQ samples (GPU)
        
    Returns:
        FrameFeatures with spectral features
    """

def reset(self) -> None:
    """Reset pipeline state (EMA, GPS buffer)."""
```

---

## Geospatial

### `TileGrid`

**Purpose:** Deterministic spatial tile grid

**Constructor:**
```python
def __init__(
    self,
    center_lat: float,
    center_lon: float,
    tile_size_meters: float,
    grid_extent_meters: float,
):
```

**Methods:**

```python
def get_tile(self, lat: float, lon: float) -> Tuple[int, int, str]:
    """
    Find tile containing (lat, lon).
    
    Returns:
        (tile_x, tile_y, tile_id)
    """

def get_tile_center(self, tile_id: str) -> Tuple[float, float]:
    """
    Get center (lat, lon) of tile.
    """
```

---

### `TileAggregator`

**Purpose:** Aggregate frames into tiles using cuDF

**Constructor:**
```python
def __init__(
    self,
    tile_grid: TileGrid,
    aggregate_window_frames: int,
    num_bands: int,
):
```

**Methods:**

```python
def add_frame(self, features: FrameFeatures) -> None:
    """Add frame to buffer (skips frames without GPS)."""

def should_aggregate(self) -> bool:
    """Check if buffer is full."""

def aggregate(self) -> List[TileMetrics]:
    """
    Aggregate buffered frames into tile metrics (GPU groupby).
    
    Returns:
        List of TileMetrics
    """

def flush(self) -> List[TileMetrics]:
    """Force aggregation (called at end of run)."""
```

---

## Configuration

### `Config`

**Purpose:** Top-level configuration object (loaded from YAML)

**Attributes:**
```python
@dataclass
class Config:
    project: Dict[str, Any]
    rf: RFConfig
    dsp: DSPConfig
    geo: GeoConfig
    synthetic: SyntheticConfig
    performance: PerformanceConfig
    ui: UIConfig
    logging: LoggingConfig
```

**Loading:**
```python
config = load_config('config/default.yaml')
config.validate()
```

---

## Export

### `export_all`

**Purpose:** Export frames + tiles to Parquet + GeoJSON

**Signature:**
```python
def export_all(
    frame_features: List[FrameFeatures],
    tile_metrics: List[TileMetrics],
    output_dir: str
) -> None:
    """
    Export all data.
    
    Outputs:
        - {output_dir}/frames.parquet
        - {output_dir}/tiles.parquet
        - {output_dir}/tiles.geojson
    """
```

---

## Testing Interface

**Deterministic Synthetic Sources:**

All synthetic sources use fixed random seeds (default: 42) for repeatability.

**Truth Labels:**
```python
iq_source.get_truth_labels() -> Dict[str, Any]:
    """
    Returns:
        {
            'carrier_freqs_hz': List[float],
            'num_carriers': int,
            'interference_enabled': bool,
            ...
        }
    """
```

**Use Case:**
- Unit tests verify peaks at expected frequencies
- Interference tests verify ON/OFF periods

