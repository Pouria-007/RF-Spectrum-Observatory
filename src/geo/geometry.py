"""
Geometry utilities: tile polygons, GeoJSON export.
"""

import json
from typing import List, Dict, Any
from pathlib import Path

from common.types import TileMetrics
from geo.tiling import TileGrid


def tile_to_polygon(tile_metrics: TileMetrics) -> List[List[float]]:
    """
    Convert tile bounds to polygon coordinates (closed ring).
    
    Args:
        tile_metrics: TileMetrics object
        
    Returns:
        Polygon coordinates (GeoJSON format: [lon, lat])
    """
    coords = [
        [tile_metrics.lon_min, tile_metrics.lat_min],
        [tile_metrics.lon_max, tile_metrics.lat_min],
        [tile_metrics.lon_max, tile_metrics.lat_max],
        [tile_metrics.lon_min, tile_metrics.lat_max],
        [tile_metrics.lon_min, tile_metrics.lat_min],  # Close ring
    ]
    return coords


def tiles_to_geojson(tile_metrics: List[TileMetrics]) -> Dict[str, Any]:
    """
    Convert list of TileMetrics to GeoJSON FeatureCollection.
    
    Args:
        tile_metrics: List of TileMetrics
        
    Returns:
        GeoJSON FeatureCollection dict
    """
    features = []
    
    for tm in tile_metrics:
        # Create polygon geometry
        polygon_coords = tile_to_polygon(tm)
        
        # Create feature
        feature = {
            "type": "Feature",
            "properties": {
                "tile_id": tm.tile_id,
                "tile_x": tm.tile_x,
                "tile_y": tm.tile_y,
                "frame_count": tm.frame_count,
                "timestamp_min_ns": tm.timestamp_min_ns,
                "timestamp_max_ns": tm.timestamp_max_ns,
                "bandpower_mean_db": tm.bandpower_mean_db,
                "bandpower_max_db": tm.bandpower_max_db,
                "occupancy_mean_pct": tm.occupancy_mean_pct,
                "anomaly_score_max": tm.anomaly_score_max,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon_coords]
            }
        }
        features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    return geojson


def export_tiles_geojson(tile_metrics: List[TileMetrics], output_path: str) -> None:
    """
    Export tiles to GeoJSON file.
    
    Args:
        tile_metrics: List of TileMetrics
        output_path: Output file path
    """
    geojson = tiles_to_geojson(tile_metrics)
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(geojson, f, indent=2)

