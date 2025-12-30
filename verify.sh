#!/bin/bash
# Verification script for RF Spectrum Observatory

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "========================================"
echo "RF Spectrum Observatory - Verification"
echo "========================================"
echo ""

# Activate environment (assumes conda is already initialized in your shell)
# If conda is not initialized, run: conda init bash
conda activate rapids 2>/dev/null || {
    echo "Error: Could not activate 'rapids' conda environment"
    echo "Please ensure conda is initialized and the 'rapids' environment exists"
    exit 1
}

# Check 1: Environment
echo "✓ Checking environment..."
python -c "import cudf, cupy, cusignal, streamlit; print(f'  cuDF: {cudf.__version__}'); print(f'  CuPy: {cupy.__version__}'); print(f'  cuSignal: {cusignal.__version__}'); print(f'  Streamlit: {streamlit.__version__}')"

# Check 2: Config
echo ""
echo "✓ Checking configuration..."
python -c "from src.common import load_config; config = load_config('config/default.yaml'); print(f'  RF: {config.rf.center_freq_hz/1e9:.2f} GHz @ {config.rf.sample_rate_sps/1e6:.2f} MS/s')"

# Check 3: Synthetic assets
echo ""
echo "✓ Checking synthetic assets..."
if [ -f "assets/maps/city_block.geojson" ]; then
    echo "  ✓ city_block.geojson exists"
else
    echo "  ✗ city_block.geojson missing (will be generated on first run)"
fi

if [ -f "assets/routes/route.csv" ]; then
    echo "  ✓ route.csv exists"
else
    echo "  ✗ route.csv missing (will be generated on first run)"
fi

# Check 4: Modules
echo ""
echo "✓ Checking modules..."
cd src
python -c "
from common import load_config, IQFrame, GPSFix
from ingest import SyntheticIQSource, SyntheticGPSSource
from dsp import create_pipeline_from_config
from geo import TileGrid, TileAggregator
from ui import create_spectrum_figure, create_deck
from perf import PerformanceMonitor
print('  ✓ All modules importable')
"
cd ..

# Check 5: Synthetic data generation
echo ""
echo "✓ Testing synthetic IQ source..."
cd src
python -c "
from common import load_config
from ingest import SyntheticIQSource

config = load_config('../config/default.yaml')
source = SyntheticIQSource(
    center_freq_hz=config.rf.center_freq_hz,
    sample_rate_sps=config.rf.sample_rate_sps,
    fft_size=config.rf.fft_size,
    num_carriers=5,
    carrier_bw_hz=10e6,
    carrier_power_db=-30,
    noise_floor_db=-80,
)
source.start()
frame = source.get_frame()
print(f'  ✓ IQ frame: {frame.frame_id}, shape={frame.iq.shape}, dtype={frame.iq.dtype}')
source.stop()
"
cd ..

# Check 6: DSP pipeline
echo ""
echo "✓ Testing DSP pipeline..."
cd src
python -c "
from common import load_config
from ingest import SyntheticIQSource
from dsp import create_pipeline_from_config

config = load_config('../config/default.yaml')
source = SyntheticIQSource(
    center_freq_hz=config.rf.center_freq_hz,
    sample_rate_sps=config.rf.sample_rate_sps,
    fft_size=config.rf.fft_size,
    num_carriers=5,
    carrier_bw_hz=10e6,
    carrier_power_db=-30,
    noise_floor_db=-80,
)
source.start()
pipeline = create_pipeline_from_config(config)
frame = source.get_frame()
features = pipeline.process_frame(frame)
print(f'  ✓ Features: frame_id={features.frame_id}, noise_floor={features.noise_floor_db:.1f} dB')
source.stop()
"
cd ..

# Check 7: Benchmarks
echo ""
echo "✓ Running quick benchmark..."
cd src
python -c "
from perf import benchmark_fft
result = benchmark_fft(fft_size=4096, num_iterations=100)
print(f'  ✓ FFT performance: {result[\"per_fft_ms\"]:.3f} ms/FFT')
"
cd ..

# Check 8: Export
echo ""
echo "✓ Testing export..."
cd src
python -c "
from common import load_config
from ingest import SyntheticIQSource, SyntheticGPSSource
from dsp import create_pipeline_from_config
from geo import TileGrid, TileAggregator, export_all

config = load_config('../config/default.yaml')
iq_source = SyntheticIQSource(
    center_freq_hz=config.rf.center_freq_hz,
    sample_rate_sps=config.rf.sample_rate_sps,
    fft_size=config.rf.fft_size,
    num_carriers=5,
    carrier_bw_hz=10e6,
    carrier_power_db=-30,
    noise_floor_db=-80,
)
iq_source.start()

gps_source = SyntheticGPSSource(
    route_csv='../assets/routes/route.csv',
    update_rate_hz=5.0,
    speed_mps=5.0,
)
gps_source.start()

pipeline = create_pipeline_from_config(config)
tile_grid = TileGrid(
    center_lat=config.geo.map_center_lat,
    center_lon=config.geo.map_center_lon,
    tile_size_meters=config.geo.tile_size_meters,
    grid_extent_meters=config.geo.grid_extent_meters,
)
aggregator = TileAggregator(tile_grid, 10, len(config.dsp.bands))

features_list = []
for i in range(15):
    frame = iq_source.get_frame()
    gps_fix = gps_source.get_fix()
    if gps_fix:
        pipeline.add_gps_fix(gps_fix)
    features = pipeline.process_frame(frame)
    features_list.append(features)
    aggregator.add_frame(features)

tiles = aggregator.aggregate()
export_all(features_list, tiles, '../outputs')
print(f'  ✓ Exported {len(features_list)} frames and {len(tiles)} tiles')

iq_source.stop()
gps_source.stop()
"
cd ..

# Summary
echo ""
echo "========================================"
echo "✅ All checks passed!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Review documentation in docs/"
echo "  2. Run dashboard: streamlit run src/streamlit_app.py"
echo "  3. Open browser: http://localhost:8501"
echo ""

