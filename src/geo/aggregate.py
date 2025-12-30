"""
GPU-accelerated geospatial aggregation using cuDF.
"""

import cudf
import cupy as cp
from typing import List, Dict, Any, Optional

from common.types import FrameFeatures, TileMetrics
from geo.tiling import TileGrid


class TileAggregator:
    """
    Aggregate frame features into spatial tiles using cuDF (GPU dataframes).
    
    Maintains a rolling buffer of frames and performs GPU-accelerated groupby
    aggregations (mean, max, count) per tile.
    """
    
    def __init__(
        self,
        tile_grid: TileGrid,
        aggregate_window_frames: int,
        num_bands: int,
    ):
        """
        Initialize tile aggregator.
        
        Args:
            tile_grid: TileGrid defining spatial tiles
            aggregate_window_frames: Number of frames to aggregate before emitting tiles
            num_bands: Number of frequency bands
        """
        self.tile_grid = tile_grid
        self.aggregate_window_frames = aggregate_window_frames
        self.num_bands = num_bands
        
        # Frame buffer (will be converted to cuDF)
        self.frame_buffer: List[Dict[str, Any]] = []
    
    def add_frame(self, features: FrameFeatures) -> None:
        """
        Add a frame to the buffer.
        
        Args:
            features: FrameFeatures with GPS location
        """
        # Skip frames without GPS
        if features.lat_deg is None or features.lon_deg is None:
            return
        
        # Get tile
        tile_x, tile_y, tile_id = self.tile_grid.get_tile(features.lat_deg, features.lon_deg)
        if tile_id == "out_of_bounds":
            return
        
        # Add to buffer (flatten band features)
        row = {
            'frame_id': features.frame_id,
            'timestamp_ns': features.timestamp_ns,
            'lat_deg': features.lat_deg,
            'lon_deg': features.lon_deg,
            'tile_id': tile_id,
            'tile_x': tile_x,
            'tile_y': tile_y,
            'noise_floor_db': features.noise_floor_db,
        }
        
        # Add band features
        for i, (bp, occ) in enumerate(zip(features.bandpower_db, features.occupancy_pct)):
            row[f'bandpower_db_{i}'] = bp
            row[f'occupancy_pct_{i}'] = occ
        
        if features.anomaly_score is not None:
            row['anomaly_score'] = features.anomaly_score
        
        self.frame_buffer.append(row)
    
    def should_aggregate(self) -> bool:
        """Check if buffer is full and ready for aggregation."""
        return len(self.frame_buffer) >= self.aggregate_window_frames
    
    def aggregate(self) -> List[TileMetrics]:
        """
        Aggregate buffered frames into tile metrics (GPU-accelerated).
        
        Returns:
            List of TileMetrics objects
        """
        if len(self.frame_buffer) == 0:
            return []
        
        # Convert buffer to cuDF (GPU dataframe)
        df = cudf.DataFrame(self.frame_buffer)
        
        # Group by tile_id
        grouped = df.groupby('tile_id')
        
        # Aggregations
        agg_dict = {
            'frame_id': 'count',
            'timestamp_ns': ['min', 'max'],
            'tile_x': 'first',
            'tile_y': 'first',
        }
        
        # Band aggregations
        for i in range(self.num_bands):
            agg_dict[f'bandpower_db_{i}'] = ['mean', 'max']
            agg_dict[f'occupancy_pct_{i}'] = 'mean'
        
        if 'anomaly_score' in df.columns:
            agg_dict['anomaly_score'] = 'max'
        
        # Perform aggregation (GPU)
        agg_df = grouped.agg(agg_dict)
        
        # Flatten multi-level columns
        agg_df.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col 
                          for col in agg_df.columns.values]
        
        # Convert to host (pandas) for TileMetrics construction
        agg_df_host = agg_df.to_pandas()
        
        # Build TileMetrics objects
        tile_metrics = []
        for tile_id, row in agg_df_host.iterrows():
            # Get tile geometry
            if tile_id not in self.tile_grid.tile_lookup:
                continue
            tile = self.tile_grid.tile_lookup[tile_id]
            
            # Extract band metrics
            bandpower_mean_db = []
            bandpower_max_db = []
            occupancy_mean_pct = []
            
            for i in range(self.num_bands):
                bandpower_mean_db.append(row.get(f'bandpower_db_{i}_mean', 0.0))
                bandpower_max_db.append(row.get(f'bandpower_db_{i}_max', 0.0))
                occupancy_mean_pct.append(row.get(f'occupancy_pct_{i}_mean', 0.0))
            
            anomaly_score_max = row.get('anomaly_score_max', None)
            
            tile_metric = TileMetrics(
                tile_id=tile_id,
                tile_x=int(row.get('tile_x_first', tile.tile_x)),
                tile_y=int(row.get('tile_y_first', tile.tile_y)),
                lat_min=tile.lat_min,
                lat_max=tile.lat_max,
                lon_min=tile.lon_min,
                lon_max=tile.lon_max,
                frame_count=int(row.get('frame_id_count', 0)),
                timestamp_min_ns=int(row.get('timestamp_ns_min', 0)),
                timestamp_max_ns=int(row.get('timestamp_ns_max', 0)),
                bandpower_mean_db=bandpower_mean_db,
                bandpower_max_db=bandpower_max_db,
                occupancy_mean_pct=occupancy_mean_pct,
                anomaly_score_max=anomaly_score_max,
            )
            tile_metrics.append(tile_metric)
        
        # Clear buffer after aggregation (tiles are kept in session state)
        self.frame_buffer = []
        
        return tile_metrics
    
    def flush(self) -> List[TileMetrics]:
        """
        Force aggregation of remaining frames (called at end of run).
        
        Returns:
            List of TileMetrics objects
        """
        return self.aggregate()

