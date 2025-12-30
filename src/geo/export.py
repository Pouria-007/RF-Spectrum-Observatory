"""
Export utilities: Parquet, GeoJSON.
"""

import pandas as pd
from pathlib import Path
from typing import List

from common.types import FrameFeatures, TileMetrics
from geo.geometry import export_tiles_geojson


def export_frames_parquet(features: List[FrameFeatures], output_path: str) -> None:
    """
    Export frame features to Parquet file.
    
    Args:
        features: List of FrameFeatures
        output_path: Output file path
    """
    # Convert to list of dicts (host arrays)
    rows = [f.to_host() for f in features]
    
    # Flatten arrays (for Parquet, we can't store arrays directly in simple format)
    # Store only scalars + GPS
    rows_flat = []
    for r in rows:
        row_flat = {
            'frame_id': r['frame_id'],
            'timestamp_ns': r['timestamp_ns'],
            'lat_deg': r['lat_deg'],
            'lon_deg': r['lon_deg'],
            'noise_floor_db': r['noise_floor_db'],
            'anomaly_score': r['anomaly_score'],
        }
        
        # Add band features (flattened)
        for i, (bp, occ) in enumerate(zip(r['bandpower_db'], r['occupancy_pct'])):
            row_flat[f'bandpower_db_{i}'] = bp
            row_flat[f'occupancy_pct_{i}'] = occ
        
        rows_flat.append(row_flat)
    
    # Create DataFrame
    df = pd.DataFrame(rows_flat)
    
    # Write to Parquet
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)


def export_tiles_parquet(tile_metrics: List[TileMetrics], output_path: str) -> None:
    """
    Export tile metrics to Parquet file.
    
    Args:
        tile_metrics: List of TileMetrics
        output_path: Output file path
    """
    # Convert to list of dicts
    rows = [tm.to_dict() for tm in tile_metrics]
    
    # Flatten lists (similar to frames)
    rows_flat = []
    for r in rows:
        row_flat = {
            'tile_id': r['tile_id'],
            'tile_x': r['tile_x'],
            'tile_y': r['tile_y'],
            'lat_min': r['lat_min'],
            'lat_max': r['lat_max'],
            'lon_min': r['lon_min'],
            'lon_max': r['lon_max'],
            'frame_count': r['frame_count'],
            'timestamp_min_ns': r['timestamp_min_ns'],
            'timestamp_max_ns': r['timestamp_max_ns'],
            'anomaly_score_max': r['anomaly_score_max'],
        }
        
        # Flatten band metrics
        num_bands = len(r['bandpower_mean_db'])
        for i in range(num_bands):
            row_flat[f'bandpower_mean_db_{i}'] = r['bandpower_mean_db'][i]
            row_flat[f'bandpower_max_db_{i}'] = r['bandpower_max_db'][i]
            row_flat[f'occupancy_mean_pct_{i}'] = r['occupancy_mean_pct'][i]
        
        rows_flat.append(row_flat)
    
    # Create DataFrame
    df = pd.DataFrame(rows_flat)
    
    # Write to Parquet
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)


def export_all(
    frame_features: List[FrameFeatures],
    tile_metrics: List[TileMetrics],
    output_dir: str
) -> None:
    """
    Export all data (frames + tiles, Parquet + GeoJSON).
    
    Args:
        frame_features: List of FrameFeatures
        tile_metrics: List of TileMetrics
        output_dir: Output directory
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Export frames
    if frame_features:
        export_frames_parquet(frame_features, str(output_path / "frames.parquet"))
        print(f"✓ Exported {len(frame_features)} frames to {output_path / 'frames.parquet'}")
    
    # Export tiles
    if tile_metrics:
        export_tiles_parquet(tile_metrics, str(output_path / "tiles.parquet"))
        export_tiles_geojson(tile_metrics, str(output_path / "tiles.geojson"))
        print(f"✓ Exported {len(tile_metrics)} tiles to {output_path / 'tiles.parquet'} and tiles.geojson")

