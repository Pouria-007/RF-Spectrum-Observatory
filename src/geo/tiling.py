"""
Spatial tiling: deterministic grid generation.
"""

import numpy as np
from typing import List, Tuple, Dict
from dataclasses import dataclass


@dataclass
class Tile:
    """Tile definition (grid cell)."""
    tile_id: str
    tile_x: int
    tile_y: int
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    
    def contains(self, lat: float, lon: float) -> bool:
        """Check if point is inside tile."""
        return (self.lat_min <= lat <= self.lat_max and
                self.lon_min <= lon <= self.lon_max)


class TileGrid:
    """
    Deterministic spatial tile grid.
    
    Generates a grid of square tiles covering an area around a center point.
    """
    
    def __init__(
        self,
        center_lat: float,
        center_lon: float,
        tile_size_meters: float,
        grid_extent_meters: float,
    ):
        """
        Initialize tile grid.
        
        Args:
            center_lat: Grid center latitude
            center_lon: Grid center longitude
            tile_size_meters: Tile side length (meters)
            grid_extent_meters: Total grid extent (meters, square)
        """
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.tile_size_meters = tile_size_meters
        self.grid_extent_meters = grid_extent_meters
        
        # Convert meters to degrees (approximate)
        self.lat_deg_per_m = 1.0 / 111000
        self.lon_deg_per_m = 1.0 / (88000 * np.cos(np.radians(center_lat)))
        
        # Compute grid bounds
        half_extent_lat = (grid_extent_meters / 2) * self.lat_deg_per_m
        half_extent_lon = (grid_extent_meters / 2) * self.lon_deg_per_m
        
        self.lat_min = center_lat - half_extent_lat
        self.lat_max = center_lat + half_extent_lat
        self.lon_min = center_lon - half_extent_lon
        self.lon_max = center_lon + half_extent_lon
        
        # Tile dimensions in degrees
        self.tile_size_lat = tile_size_meters * self.lat_deg_per_m
        self.tile_size_lon = tile_size_meters * self.lon_deg_per_m
        
        # Number of tiles per axis
        self.num_tiles_x = int(np.ceil(grid_extent_meters / tile_size_meters))
        self.num_tiles_y = int(np.ceil(grid_extent_meters / tile_size_meters))
        
        # Generate tiles
        self.tiles: List[Tile] = self._generate_tiles()
        self.tile_lookup: Dict[str, Tile] = {t.tile_id: t for t in self.tiles}
    
    def _generate_tiles(self) -> List[Tile]:
        """Generate all tiles in the grid."""
        tiles = []
        
        for ix in range(self.num_tiles_x):
            for iy in range(self.num_tiles_y):
                # Tile bounds
                tile_lon_min = self.lon_min + ix * self.tile_size_lon
                tile_lon_max = tile_lon_min + self.tile_size_lon
                tile_lat_min = self.lat_min + iy * self.tile_size_lat
                tile_lat_max = tile_lat_min + self.tile_size_lat
                
                tile = Tile(
                    tile_id=f"tile_x{ix}_y{iy}",
                    tile_x=ix,
                    tile_y=iy,
                    lat_min=tile_lat_min,
                    lat_max=tile_lat_max,
                    lon_min=tile_lon_min,
                    lon_max=tile_lon_max,
                )
                tiles.append(tile)
        
        return tiles
    
    def get_tile(self, lat: float, lon: float) -> Tuple[int, int, str]:
        """
        Find the tile containing a lat/lon point.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Tuple of (tile_x, tile_y, tile_id), or (-1, -1, "out_of_bounds")
        """
        if not (self.lat_min <= lat <= self.lat_max and self.lon_min <= lon <= self.lon_max):
            return (-1, -1, "out_of_bounds")
        
        ix = int((lon - self.lon_min) / self.tile_size_lon)
        iy = int((lat - self.lat_min) / self.tile_size_lat)
        
        # Clamp to grid bounds
        ix = max(0, min(ix, self.num_tiles_x - 1))
        iy = max(0, min(iy, self.num_tiles_y - 1))
        
        tile_id = f"tile_x{ix}_y{iy}"
        return (ix, iy, tile_id)
    
    def get_tile_center(self, tile_id: str) -> Tuple[float, float]:
        """
        Get the center lat/lon of a tile.
        
        Args:
            tile_id: Tile ID
            
        Returns:
            Tuple of (lat, lon)
        """
        if tile_id not in self.tile_lookup:
            raise ValueError(f"Unknown tile_id: {tile_id}")
        
        tile = self.tile_lookup[tile_id]
        lat_center = (tile.lat_min + tile.lat_max) / 2
        lon_center = (tile.lon_min + tile.lon_max) / 2
        return (lat_center, lon_center)

