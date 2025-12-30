"""
Streamlit UI components: PyDeck map layers (2D tile heatmap, 3D extrusion).
"""

import pydeck as pdk
import pandas as pd
import numpy as np
import base64
import os
from typing import List, Dict, Any, Optional

from common.types import TileMetrics


def create_base_map_layers(
    city_block_geojson: str,
    house_geojson: str
) -> List[pdk.Layer]:
    """
    Create base map layers (polygons from GeoJSON).
    
    Args:
        city_block_geojson: Path to city block GeoJSON
        house_geojson: Path to house GeoJSON
        
    Returns:
        List of pydeck Layer objects
    """
    import json
    
    layers = []
    
    # City block layer
    try:
        with open(city_block_geojson, 'r') as f:
            city_block_data = json.load(f)
        
        layers.append(pdk.Layer(
            "GeoJsonLayer",
            city_block_data,
            opacity=0.3,
            stroked=True,
            filled=True,
            extruded=False,
            get_fill_color=[100, 100, 100],
            get_line_color=[200, 200, 200],
            line_width_min_pixels=2,
        ))
    except Exception as e:
        print(f"Warning: Could not load city block: {e}")
    
    # House layer
    try:
        with open(house_geojson, 'r') as f:
            house_data = json.load(f)
        
        layers.append(pdk.Layer(
            "GeoJsonLayer",
            house_data,
            opacity=0.5,
            stroked=True,
            filled=True,
            extruded=False,
            get_fill_color=[150, 100, 50],
            get_line_color=[255, 200, 100],
            line_width_min_pixels=2,
        ))
    except Exception as e:
        print(f"Warning: Could not load house: {e}")
    
    return layers


def create_tile_heatmap_layer(
    tile_metrics: List[TileMetrics],
    metric_name: str = "bandpower_mean",
    band_idx: int = 0,
    colormap: str = "plasma"
) -> pdk.Layer:
    """
    Create 2D tile heatmap layer (colored grid cells).
    
    Args:
        tile_metrics: List of TileMetrics
        metric_name: Metric to visualize ('bandpower_mean', 'occupancy_mean', etc.)
        band_idx: Band index (for multi-band metrics)
        colormap: Color map name
        
    Returns:
        pydeck Layer
    """
    if len(tile_metrics) == 0:
        # Return empty layer
        return pdk.Layer(
            "GeoJsonLayer",
            {"type": "FeatureCollection", "features": []},
        )
    
    # Extract metric values
    metric_values = []
    for tm in tile_metrics:
        if metric_name == "bandpower_mean":
            val = tm.bandpower_mean_db[band_idx] if band_idx < len(tm.bandpower_mean_db) else 0
        elif metric_name == "bandpower_max":
            val = tm.bandpower_max_db[band_idx] if band_idx < len(tm.bandpower_max_db) else 0
        elif metric_name == "occupancy_mean":
            val = tm.occupancy_mean_pct[band_idx] if band_idx < len(tm.occupancy_mean_pct) else 0
        else:
            val = 0
        metric_values.append(val)
    
    # Normalize to 0-255 for color mapping
    metric_array = np.array(metric_values)
    if len(metric_array) > 0 and metric_array.max() > metric_array.min():
        metric_norm = (metric_array - metric_array.min()) / (metric_array.max() - metric_array.min())
    else:
        metric_norm = np.zeros_like(metric_array)
    
    # Map to RGB (simple plasma-like colormap)
    colors = []
    for val in metric_norm:
        r = int(255 * val)
        g = int(128 * (1 - val))
        b = int(255 * (1 - val))
        colors.append([r, g, b, 180])
    
    # Build GeoJSON
    features = []
    for tm, color in zip(tile_metrics, colors):
        coords = [
            [tm.lon_min, tm.lat_min],
            [tm.lon_max, tm.lat_min],
            [tm.lon_max, tm.lat_max],
            [tm.lon_min, tm.lat_max],
            [tm.lon_min, tm.lat_min],
        ]
        
        # Add label for 2D view
        val = float(metric_values[tile_metrics.index(tm)])
        label = f"{tm.tile_id}\n{val:.1f}"
        
        # Get tile center for tooltip
        lat_center = (tm.lat_min + tm.lat_max) / 2
        lon_center = (tm.lon_min + tm.lon_max) / 2
        
        feature = {
            "type": "Feature",
            "properties": {
                "tile_id": tm.tile_id,
                "metric_value": f"{val:.2f}",  # Pre-format as string
                "fill_color": color,
                "label": label,
                "lat_center": f"{lat_center:.8f}",  # Pre-format as string
                "lon_center": f"{lon_center:.8f}",  # Pre-format as string
                "frame_count": tm.frame_count,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            }
        }
        features.append(feature)
    
    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }
    
    # Create GeoJSON layer for polygons
    geojson_layer = pdk.Layer(
        "GeoJsonLayer",
        geojson_data,
        opacity=0.7,
        stroked=True,
        filled=True,
        extruded=False,
        get_fill_color="properties.fill_color",
        get_line_color=[255, 255, 255],
        line_width_min_pixels=1,
        pickable=True,
    )
    
    # Return just the GeoJSON layer (TextLayer removed to fix rendering)
    return geojson_layer


def create_tile_3d_layer(
    tile_metrics: List[TileMetrics],
    metric_name: str = "bandpower_mean",
    band_idx: int = 0,
    extrusion_scale: float = 10.0
) -> pdk.Layer:
    """
    Create 3D extruded tile layer (column layer).
    
    Args:
        tile_metrics: List of TileMetrics
        metric_name: Metric to visualize (determines height)
        band_idx: Band index
        extrusion_scale: Height scaling factor
        
    Returns:
        pydeck Layer
    """
    if len(tile_metrics) == 0:
        return pdk.Layer("ColumnLayer", [])
    
    # Get metric values for normalization
    metric_values = []
    for tm in tile_metrics:
        if metric_name == "bandpower_mean":
            val = tm.bandpower_mean_db[band_idx] if band_idx < len(tm.bandpower_mean_db) else -100
        elif metric_name == "bandpower_max":
            val = tm.bandpower_max_db[band_idx] if band_idx < len(tm.bandpower_max_db) else -100
        elif metric_name == "occupancy_mean":
            val = tm.occupancy_mean_pct[band_idx] if band_idx < len(tm.occupancy_mean_pct) else 0
        else:
            val = 0
        metric_values.append(val)
    
    val_min = min(metric_values) if metric_values else -100
    val_max = max(metric_values) if metric_values else 0
    
    # Prepare data for ColumnLayer
    data = []
    for tm, val in zip(tile_metrics, metric_values):
        # Normalize height (avoid negative heights)
        height = max(0, val + 100) * extrusion_scale  # Shift to positive range
        
        # Tile center
        lat_center = (tm.lat_min + tm.lat_max) / 2
        lon_center = (tm.lon_min + tm.lon_max) / 2
        
        # Color based on value (plasma-like colormap)
        val_norm = (val - val_min) / (val_max - val_min) if val_max > val_min else 0.5
        r = int(255 * val_norm)
        g = int(128 * (1 - val_norm))
        b = int(255 * (1 - val_norm))
        
        data.append({
            "position": [lon_center, lat_center],
            "elevation": height,
            "color": [r, g, b, 200],
            "tile_id": tm.tile_id,
            "metric_value": f"{val:.2f}",
            "frame_count": tm.frame_count,
            "lat_center": f"{lat_center:.8f}",
            "lon_center": f"{lon_center:.8f}",
        })
    
    # Create ColumnLayer for 3D
    column_layer = pdk.Layer(
        "ColumnLayer",
        data,
        get_position="position",
        get_elevation="elevation",
        get_fill_color="color",
        elevation_scale=1,
        radius=20,  # Column radius in meters
        pickable=True,
        auto_highlight=True,
        material=False,  # Disable material lighting for flatter colors
        get_line_color=[0, 0, 0, 0],  # No border
    )
    
    # Return just the column layer (TextLayer can cause rendering issues)
    # Tooltips will show the info instead
    return column_layer


def create_deck(
    tile_metrics: List[TileMetrics],
    map_center_lat: float,
    map_center_lon: float,
    zoom: int = 15,
    pitch: int = 0,
    show_3d: bool = False,
    metric_name: str = "bandpower_mean",
    band_idx: int = 0,
    extrusion_scale: float = 10.0,
    city_block_geojson: Optional[str] = None,
    house_geojson: Optional[str] = None,
    current_gps_lat: float = None,
    current_gps_lon: float = None,
) -> pdk.Deck:
    """
    Create PyDeck Deck with all layers.
    
    Args:
        tile_metrics: List of TileMetrics
        map_center_lat: Map center latitude
        map_center_lon: Map center longitude
        zoom: Zoom level
        pitch: Pitch angle (0=2D, 45=3D)
        show_3d: If True, use 3D columns; else use 2D heatmap
        metric_name: Metric to visualize
        band_idx: Band index
        extrusion_scale: 3D height scale
        city_block_geojson: Path to city block GeoJSON
        house_geojson: Path to house GeoJSON
        
    Returns:
        pydeck Deck
    """
    layers = []
    
    # Base map layers (commented out - they clutter the view)
    # if city_block_geojson and house_geojson:
    #     layers.extend(create_base_map_layers(city_block_geojson, house_geojson))
    
    # Tile layers
    if show_3d:
        tile_layer = create_tile_3d_layer(tile_metrics, metric_name, band_idx, extrusion_scale)
        layers.append(tile_layer)
    else:
        tile_layer = create_tile_heatmap_layer(tile_metrics, metric_name, band_idx)
        layers.append(tile_layer)
    
    # Add drone marker at current GPS position
    if current_gps_lat is not None and current_gps_lon is not None:
        # Calculate max elevation for 3D positioning
        max_elevation = 0
        if show_3d and len(tile_metrics) > 0:
            # Find the tallest bar
            for tm in tile_metrics:
                if metric_name == "bandpower_mean":
                    val = tm.bandpower_mean_db[band_idx] if band_idx < len(tm.bandpower_mean_db) else -100
                elif metric_name == "occupancy_mean":
                    val = tm.occupancy_mean_pct[band_idx] if band_idx < len(tm.occupancy_mean_pct) else 0
                else:
                    val = 0
                height = max(0, val + 100) * extrusion_scale
                max_elevation = max(max_elevation, height)
        
        # APPROACH: IconLayer with local helicopter image (100% reliable!)
        # Convert local PNG to base64 data URI for PyDeck
        helicopter_icon_path = os.path.join(
            os.path.dirname(__file__), 
            "../../assets/icons/helicopter.png"
        )
        helicopter_icon_path = os.path.abspath(helicopter_icon_path)
        
        # Read and encode the image as base64 data URI
        try:
            with open(helicopter_icon_path, "rb") as f:
                image_data = f.read()
                base64_image = base64.b64encode(image_data).decode()
                helicopter_data_uri = f"data:image/png;base64,{base64_image}"
            
            icon_layer = pdk.Layer(
                "IconLayer",
                data=[{
                    "position": [current_gps_lon, current_gps_lat, max_elevation + 15],
                    "icon_data": {
                        "url": helicopter_data_uri,
                        "width": 256,  # Actual image size
                        "height": 256,
                        "anchorY": 128,
                        "anchorX": 128,
                    },
                    "name": "🚁 Helicopter",
                }],
                get_position="position",
                get_icon="icon_data",
                get_size=4,  # Medium size - clearly visible
                size_scale=12,  # Good balance between visibility and size
                pickable=True,
                get_color=[255, 255, 255, 255],  # No tint - use original colors
            )
            layers.append(icon_layer)
        except Exception as e:
            # If image loading fails, fall back to just the markers
            print(f"Warning: Could not load helicopter icon: {e}")
        
        # BACKUP: Small cyan dot (keep it for now as backup marker)
        # Make it smaller so helicopter icon is more prominent
        drone_marker = pdk.Layer(
            "ScatterplotLayer",
            data=[{
                "position": [current_gps_lon, current_gps_lat, max_elevation + 5],
                "name": "🚁 Drone Position",
            }],
            get_position="position",
            get_radius=8,  # Smaller - just a backup marker
            get_fill_color=[0, 255, 255, 200],  # Slightly transparent cyan
            get_line_color=[255, 255, 255, 255],  # White outline
            line_width_min_pixels=2,
            pickable=True,
            auto_highlight=True,
        )
        layers.append(drone_marker)
        
        # Yellow base circle - make smaller so helicopter is more prominent
        drone_layer = pdk.Layer(
            "ScatterplotLayer",
            data=[{
                "position": [current_gps_lon, current_gps_lat, max_elevation],
                "name": "🚁 Helicopter Base",
            }],
            get_position="position",
            get_radius=18,  # Smaller base - helicopter will be more visible
            get_fill_color=[255, 255, 0, 150],  # More transparent yellow
            get_line_color=[255, 200, 0, 255],  # Orange outline
            line_width_min_pixels=2,
            pickable=True,
        )
        layers.append(drone_layer)
    
    # View state
    view_state = pdk.ViewState(
        latitude=map_center_lat,
        longitude=map_center_lon,
        zoom=zoom,
        pitch=pitch,
        bearing=0,
    )
    
    # Deck with free basemap
    # Using Carto Dark Matter (free, no API key required)
    # Alternative options:
    # - "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json" (light)
    # - "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json" (balanced)
    # Enhanced tooltip - PyDeck supports HTML tooltips
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip={
            "html": "<b>Tile ID:</b> {tile_id}<br/>"
                    "<b>Latitude:</b> {lat_center}°<br/>"
                    "<b>Longitude:</b> {lon_center}°<br/>"
                    "<b>RF Signal Power:</b> {metric_value} dB<br/>"
                    "<b>IQ Frames:</b> {frame_count} frames<br/>"
                    "<i>Averaged over {frame_count} IQ frame measurements</i>",
            "style": {
                "backgroundColor": "rgba(0, 0, 0, 0.8)",
                "color": "white",
                "fontSize": "12px",
                "padding": "8px"
            }
        },
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    )
    
    return deck

