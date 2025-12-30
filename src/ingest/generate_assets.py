"""
Generate synthetic map assets and routes.

Creates GeoJSON polygons and CSV routes for testing without external data.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any


def generate_city_block(
    center_lat: float,
    center_lon: float,
    size_meters: float = 200.0,
    output_path: str = "assets/maps/city_block.geojson"
) -> None:
    """
    Generate a simple rectangular city block polygon.
    
    Args:
        center_lat: Block center latitude
        center_lon: Block center longitude
        size_meters: Block size (square)
        output_path: Output GeoJSON path
    """
    # Convert meters to approximate degrees
    # At ~37 degrees latitude: 1 degree lat ≈ 111 km, 1 degree lon ≈ 88 km
    lat_deg_per_m = 1.0 / 111000
    lon_deg_per_m = 1.0 / 88000
    
    half_size_lat = (size_meters / 2) * lat_deg_per_m
    half_size_lon = (size_meters / 2) * lon_deg_per_m
    
    # Create polygon (closed ring)
    coords = [
        [center_lon - half_size_lon, center_lat - half_size_lat],
        [center_lon + half_size_lon, center_lat - half_size_lat],
        [center_lon + half_size_lon, center_lat + half_size_lat],
        [center_lon - half_size_lon, center_lat + half_size_lat],
        [center_lon - half_size_lon, center_lat - half_size_lat],  # Close ring
    ]
    
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": "City Block",
                    "type": "boundary"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords]
                }
            }
        ]
    }
    
    # Write to file
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(geojson, f, indent=2)


def generate_house(
    center_lat: float,
    center_lon: float,
    size_meters: float = 30.0,
    output_path: str = "assets/maps/house.geojson"
) -> None:
    """
    Generate a small house polygon inside the city block.
    
    Args:
        center_lat: House center latitude
        center_lon: House center longitude
        size_meters: House size (square)
        output_path: Output GeoJSON path
    """
    lat_deg_per_m = 1.0 / 111000
    lon_deg_per_m = 1.0 / 88000
    
    half_size_lat = (size_meters / 2) * lat_deg_per_m
    half_size_lon = (size_meters / 2) * lon_deg_per_m
    
    coords = [
        [center_lon - half_size_lon, center_lat - half_size_lat],
        [center_lon + half_size_lon, center_lat - half_size_lat],
        [center_lon + half_size_lon, center_lat + half_size_lat],
        [center_lon - half_size_lon, center_lat + half_size_lat],
        [center_lon - half_size_lon, center_lat - half_size_lat],
    ]
    
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": "House",
                    "type": "building"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords]
                }
            }
        ]
    }
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(geojson, f, indent=2)


def generate_route(
    center_lat: float,
    center_lon: float,
    extent_meters: float = 2000.0,  # 2km coverage to ensure we hit many tiles
    num_waypoints: int = 300,  # More waypoints for better coverage
    output_path: str = "assets/routes/route.csv",
    mode: str = "grid_walk"  # "random_walk" or "grid_walk"
) -> None:
    """
    Generate a synthetic GPS route covering multiple tiles.
    
    Args:
        center_lat: Route center latitude
        center_lon: Route center longitude
        extent_meters: Maximum deviation from center (increased for more coverage)
        num_waypoints: Number of waypoints (increased for more locations)
        output_path: Output CSV path
        mode: "random_walk" or "grid_walk" (grid covers more area systematically)
    """
    lat_deg_per_m = 1.0 / 111000
    lon_deg_per_m = 1.0 / 88000
    
    np.random.seed(42)
    
    if mode == "grid_walk":
        # Grid-based walk: systematically covers area in a grid pattern
        # This ensures we hit many different tiles
        grid_size = int(np.sqrt(num_waypoints))  # e.g., 17x17 grid for 300 points
        lats = []
        lons = []
        
        # Calculate actual extent in degrees
        lat_extent_deg = extent_meters * lat_deg_per_m
        lon_extent_deg = extent_meters * lon_deg_per_m
        
        for i in range(num_waypoints):
            # Create grid pattern
            row = (i // grid_size) % grid_size
            col = i % grid_size
            
            # Grid position (normalized 0-1, then centered around 0)
            row_norm = row / (grid_size - 1) if grid_size > 1 else 0.5
            col_norm = col / (grid_size - 1) if grid_size > 1 else 0.5
            
            # Center around 0 and scale to extent
            lat_offset = (row_norm - 0.5) * lat_extent_deg
            lon_offset = (col_norm - 0.5) * lon_extent_deg
            
            # Add small random jitter (10% of grid spacing)
            grid_spacing_lat = lat_extent_deg / grid_size
            grid_spacing_lon = lon_extent_deg / grid_size
            jitter_lat = np.random.randn() * 0.1 * grid_spacing_lat
            jitter_lon = np.random.randn() * 0.1 * grid_spacing_lon
            
            lats.append(center_lat + lat_offset + jitter_lat)
            lons.append(center_lon + lon_offset + jitter_lon)
    else:
        # Random walk (original method)
        lats = [center_lat]
        lons = [center_lon]
        
        for i in range(num_waypoints - 1):
            # Larger random steps to cover more area
            dlat = np.random.randn() * 0.5 * lat_deg_per_m * extent_meters / num_waypoints
            dlon = np.random.randn() * 0.5 * lon_deg_per_m * extent_meters / num_waypoints
            
            new_lat = lats[-1] + dlat
            new_lon = lons[-1] + dlon
            
            # Clamp to extent
            new_lat = np.clip(new_lat, center_lat - extent_meters * lat_deg_per_m, center_lat + extent_meters * lat_deg_per_m)
            new_lon = np.clip(new_lon, center_lon - extent_meters * lon_deg_per_m, center_lon + extent_meters * lon_deg_per_m)
            
            lats.append(new_lat)
            lons.append(new_lon)
    
    # Create DataFrame
    df = pd.DataFrame({
        't_sec': np.arange(num_waypoints, dtype=float),
        'lat_deg': lats,
        'lon_deg': lons,
    })
    
    # Write to CSV
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)


def generate_all_assets(
    map_center_lat: float = 37.7946,
    map_center_lon: float = -122.3999,
) -> None:
    """
    Generate all synthetic assets (maps + routes).
    
    Args:
        map_center_lat: Map center latitude (default: SF Financial District)
        map_center_lon: Map center longitude
    """
    # City block (200m x 200m)
    generate_city_block(
        center_lat=map_center_lat,
        center_lon=map_center_lon,
        size_meters=200.0
    )
    
    # House (30m x 30m, offset slightly from center)
    generate_house(
        center_lat=map_center_lat + 0.0005,
        center_lon=map_center_lon + 0.0005,
        size_meters=30.0
    )
    
    # Route (2000m grid walk, 300 waypoints - covers many tiles)
    generate_route(
        center_lat=map_center_lat,
        center_lon=map_center_lon,
        extent_meters=2000.0,  # 2km coverage to hit many tiles
        num_waypoints=300,  # More waypoints = more tiles
        mode="grid_walk"  # Grid pattern ensures diverse locations
    )
    
    print("✓ Generated synthetic assets:")
    print("  - assets/maps/city_block.geojson")
    print("  - assets/maps/house.geojson")
    print("  - assets/routes/route.csv")


if __name__ == '__main__':
    generate_all_assets()

