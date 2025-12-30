"""
Base interface for GPS sources.

All GPS sources (synthetic, hardware) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Iterator, Optional

from common.types import GPSFix


class BaseGPSSource(ABC):
    """
    Abstract base class for GPS fix sources.
    
    Implementations:
    - SyntheticGPSSource: Route playback from CSV
    - HardwareGPSSource: Real GPS (NMEA, serial) - stub for now
    """
    
    @abstractmethod
    def start(self) -> None:
        """Initialize and start the source."""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop the source and release resources."""
        pass
    
    @abstractmethod
    def __iter__(self) -> Iterator[GPSFix]:
        """Iterate over GPS fixes."""
        pass
    
    @abstractmethod
    def get_fix(self) -> Optional[GPSFix]:
        """
        Get a single GPS fix (non-blocking).
        
        Returns:
            GPSFix object or None if no fix available
        """
        pass

