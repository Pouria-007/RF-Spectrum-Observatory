"""
Synthetic GPS source: route playback from CSV.

Generates GPS fixes along a predefined route with configurable speed.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Iterator, Optional, List

from common.types import GPSFix
from common.timebase import now_ns, sec_to_ns
from ingest.gps_base import BaseGPSSource


class SyntheticGPSSource(BaseGPSSource):
    """
    Synthetic GPS source that replays a route from CSV.
    
    CSV format:
        t_sec, lat_deg, lon_deg
    
    The source interpolates between waypoints at a constant speed.
    """
    
    def __init__(
        self,
        route_csv: str,
        update_rate_hz: float = 5.0,
        speed_mps: float = 5.0,
        loop: bool = True,
    ):
        """
        Initialize synthetic GPS source.
        
        Args:
            route_csv: Path to route CSV file
            update_rate_hz: GPS fix update rate (Hz)
            speed_mps: Speed along route (m/s)
            loop: If True, loop route indefinitely
        """
        self.route_csv = route_csv
        self.update_rate_hz = update_rate_hz
        self.speed_mps = speed_mps
        self.loop = loop
        
        # Load route
        self._waypoints: Optional[pd.DataFrame] = None
        self._load_route()
        
        # Internal state
        self._running = False
        self._start_time_ns = 0
        self._current_idx = 0
        self._interp_progress = 0.0  # Progress between current and next waypoint
    
    def _load_route(self) -> None:
        """Load route from CSV."""
        path = Path(self.route_csv)
        if not path.exists():
            raise FileNotFoundError(f"Route file not found: {self.route_csv}")
        
        self._waypoints = pd.read_csv(path)
        
        # Validate columns
        required_cols = ['t_sec', 'lat_deg', 'lon_deg']
        for col in required_cols:
            if col not in self._waypoints.columns:
                raise ValueError(f"Route CSV missing column: {col}")
        
        # Sort by time
        self._waypoints = self._waypoints.sort_values('t_sec').reset_index(drop=True)
    
    def start(self) -> None:
        """Start the GPS source."""
        self._running = True
        self._start_time_ns = now_ns()
        self._current_idx = 0
        self._interp_progress = 0.0
    
    def stop(self) -> None:
        """Stop the GPS source."""
        self._running = False
    
    def __iter__(self) -> Iterator[GPSFix]:
        """Iterate over GPS fixes."""
        return self
    
    def __next__(self) -> GPSFix:
        """Get next fix (for iterator protocol)."""
        if not self._running:
            raise StopIteration
        
        fix = self.get_fix()
        if fix is None:
            raise StopIteration
        return fix
    
    def get_fix(self) -> Optional[GPSFix]:
        """
        Get current GPS fix based on elapsed time and route progress.
        
        Returns:
            GPSFix or None if route exhausted (and not looping)
        """
        if not self._running or self._waypoints is None:
            return None
        
        # Check if we've reached the end
        if self._current_idx >= len(self._waypoints) - 1:
            if self.loop:
                self._current_idx = 0
                self._interp_progress = 0.0
            else:
                return None
        
        # Get current and next waypoints
        wp_curr = self._waypoints.iloc[self._current_idx]
        wp_next = self._waypoints.iloc[self._current_idx + 1]
        
        # Interpolate position
        alpha = self._interp_progress
        lat = wp_curr['lat_deg'] * (1 - alpha) + wp_next['lat_deg'] * alpha
        lon = wp_curr['lon_deg'] * (1 - alpha) + wp_next['lon_deg'] * alpha
        
        # Compute heading (bearing from curr to next)
        heading_deg = self._compute_bearing(
            wp_curr['lat_deg'], wp_curr['lon_deg'],
            wp_next['lat_deg'], wp_next['lon_deg']
        )
        
        # Create fix
        timestamp_ns = now_ns()
        fix = GPSFix(
            gps_timestamp_ns=int(timestamp_ns),
            lat_deg=float(lat),
            lon_deg=float(lon),
            alt_m=None,  # Not simulated
            heading_deg=heading_deg,
            speed_mps=self.speed_mps,
        )
        
        # Advance progress
        elapsed_sec = (timestamp_ns - self._start_time_ns) / 1e9
        segment_duration_sec = self._compute_segment_duration(wp_curr, wp_next)
        
        if segment_duration_sec > 0:
            self._interp_progress += (1.0 / self.update_rate_hz) / segment_duration_sec
        
        if self._interp_progress >= 1.0:
            self._current_idx += 1
            self._interp_progress = 0.0
        
        return fix
    
    def _compute_segment_duration(self, wp1: pd.Series, wp2: pd.Series) -> float:
        """
        Compute time to travel from wp1 to wp2 at constant speed.
        
        Args:
            wp1: First waypoint
            wp2: Second waypoint
            
        Returns:
            Duration in seconds
        """
        dist_m = self._haversine_distance(
            wp1['lat_deg'], wp1['lon_deg'],
            wp2['lat_deg'], wp2['lon_deg']
        )
        return dist_m / self.speed_mps if self.speed_mps > 0 else 0
    
    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Compute distance between two lat/lon points (Haversine formula).
        
        Args:
            lat1, lon1: First point (degrees)
            lat2, lon2: Second point (degrees)
            
        Returns:
            Distance in meters
        """
        R = 6371000  # Earth radius in meters
        phi1 = np.radians(lat1)
        phi2 = np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlambda = np.radians(lon2 - lon1)
        
        a = np.sin(dphi/2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda/2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        
        return R * c
    
    @staticmethod
    def _compute_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Compute bearing (heading) from point 1 to point 2.
        
        Args:
            lat1, lon1: Start point (degrees)
            lat2, lon2: End point (degrees)
            
        Returns:
            Bearing in degrees (0=North, 90=East)
        """
        phi1 = np.radians(lat1)
        phi2 = np.radians(lat2)
        dlambda = np.radians(lon2 - lon1)
        
        x = np.sin(dlambda) * np.cos(phi2)
        y = np.cos(phi1) * np.sin(phi2) - np.sin(phi1) * np.cos(phi2) * np.cos(dlambda)
        
        bearing_rad = np.arctan2(x, y)
        bearing_deg = np.degrees(bearing_rad)
        
        return (bearing_deg + 360) % 360

