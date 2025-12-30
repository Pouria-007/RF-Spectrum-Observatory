#!/usr/bin/env python
"""
Diagnostic script to debug tile aggregation issue.

Tests the full pipeline in isolation to identify why Tiles = 0.
"""

import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from common import load_config
from ingest import SyntheticIQSource, SyntheticGPSSource
from dsp import create_pipeline_from_config
from geo import TileGrid, TileAggregator

print("="*60)
print("Tile Aggregation Diagnostic")
print("="*60)

# Load config
config = load_config('config/default.yaml')

# Create sources
iq_source = SyntheticIQSource(
    center_freq_hz=config.rf.center_freq_hz,
    sample_rate_sps=config.rf.sample_rate_sps,
    fft_size=config.rf.fft_size,
    num_carriers=config.synthetic.iq['num_carriers'],
    carrier_bw_hz=config.synthetic.iq['carrier_bw_hz'],
    carrier_power_db=config.synthetic.iq['carrier_power_db'],
    noise_floor_db=config.synthetic.iq['noise_floor_db'],
    interference_config=config.synthetic.iq['interference'],
)
iq_source.start()

gps_source = SyntheticGPSSource(
    route_csv=config.synthetic.gps['route_csv'],
    update_rate_hz=config.synthetic.gps['update_rate_hz'],
    speed_mps=config.synthetic.gps['speed_mps'],
)
gps_source.start()

# Create pipeline
pipeline = create_pipeline_from_config(config)

# Create tile grid
tile_grid = TileGrid(
    center_lat=config.geo.map_center_lat,
    center_lon=config.geo.map_center_lon,
    tile_size_meters=config.geo.tile_size_meters,
    grid_extent_meters=config.geo.grid_extent_meters,
)
print(f"\nTile Grid: {tile_grid.num_tiles_x} x {tile_grid.num_tiles_y} = {len(tile_grid.tiles)} tiles")
print(f"Grid bounds: lat=[{tile_grid.lat_min:.6f}, {tile_grid.lat_max:.6f}], lon=[{tile_grid.lon_min:.6f}, {tile_grid.lon_max:.6f}]")

# Create aggregator
aggregator = TileAggregator(
    tile_grid=tile_grid,
    aggregate_window_frames=config.geo.aggregate_window_frames,
    num_bands=len(config.dsp.bands),
)
print(f"Aggregation window: {config.geo.aggregate_window_frames} frames")

# Process frames
print("\n" + "="*60)
print("Processing frames...")
print("="*60)

gps_count = 0
aligned_count = 0
in_bounds_count = 0

for i in range(150):  # Process more than the aggregation window
    # Get IQ frame
    frame = iq_source.get_frame()
    
    # Get GPS fix
    gps_fix = gps_source.get_fix()
    if gps_fix:
        gps_count += 1
        pipeline.add_gps_fix(gps_fix)
    
    # Process frame
    features = pipeline.process_frame(frame)
    
    # Check if GPS aligned
    if features.lat_deg is not None and features.lon_deg is not None:
        aligned_count += 1
        
        # Check if in grid bounds
        tile_x, tile_y, tile_id = tile_grid.get_tile(features.lat_deg, features.lon_deg)
        if tile_id != "out_of_bounds":
            in_bounds_count += 1
            if i < 10:  # Show first 10
                print(f"Frame {i}: GPS ({features.lat_deg:.6f}, {features.lon_deg:.6f}) → {tile_id}")
        else:
            if i < 10:
                print(f"Frame {i}: GPS ({features.lat_deg:.6f}, {features.lon_deg:.6f}) → OUT OF BOUNDS")
    else:
        if i < 10:
            print(f"Frame {i}: NO GPS ALIGNMENT")
    
    # Add to aggregator
    aggregator.add_frame(features)
    
    # Check buffer status
    if (i + 1) % 10 == 0:
        buffer_size = len(aggregator.frame_buffer)
        print(f"  [{i+1} frames] Buffer: {buffer_size}/{config.geo.aggregate_window_frames}")
    
    # Aggregate if ready
    if aggregator.should_aggregate():
        tiles = aggregator.aggregate()
        print(f"\n✓ AGGREGATION at frame {i+1}: {len(tiles)} tiles produced")
        if tiles:
            for tile in tiles[:3]:  # Show first 3
                print(f"  - {tile.tile_id}: {tile.frame_count} frames, bandpower={tile.bandpower_mean_db}")

# Final flush
print("\n" + "="*60)
print("Final flush...")
tiles = aggregator.flush()
print(f"Final tiles: {len(tiles)}")

iq_source.stop()
gps_source.stop()

# Summary
print("\n" + "="*60)
print("SUMMARY")
print("="*60)
print(f"GPS fixes received: {gps_count} / 150")
print(f"GPS aligned frames: {aligned_count} / 150")
print(f"Frames in grid bounds: {in_bounds_count} / 150")
print(f"Final tiles produced: {len(tiles)}")

if len(tiles) == 0:
    print("\n❌ PROBLEM IDENTIFIED:")
    if gps_count == 0:
        print("  → GPS source not producing fixes")
    elif aligned_count == 0:
        print("  → GPS/IQ alignment failing (timestamp mismatch)")
    elif in_bounds_count == 0:
        print("  → GPS coordinates outside tile grid bounds")
    else:
        print("  → Aggregation logic issue (frames not being converted to tiles)")
else:
    print(f"\n✅ SUCCESS: {len(tiles)} tiles generated")
    print("\nTile details:")
    for tile in tiles[:5]:
        print(f"  {tile.tile_id}: count={tile.frame_count}, lat=[{tile.lat_min:.6f}, {tile.lat_max:.6f}], lon=[{tile.lon_min:.6f}, {tile.lon_max:.6f}]")

