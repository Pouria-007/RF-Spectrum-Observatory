"""
Base interface for IQ sources.

All IQ sources (synthetic, hardware) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Iterator

from common.types import IQFrame


class BaseIQSource(ABC):
    """
    Abstract base class for IQ sample sources.
    
    Implementations:
    - SyntheticIQSource: Deterministic synthetic signals
    - HardwareIQSource: Real SDR (SoapySDR, UHD, etc.) - stub for now
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
    def __iter__(self) -> Iterator[IQFrame]:
        """Iterate over IQ frames (blocking or non-blocking)."""
        pass
    
    @abstractmethod
    def get_frame(self) -> IQFrame:
        """
        Get a single IQ frame (blocking).
        
        Returns:
            IQFrame object
            
        Raises:
            StopIteration: If source is exhausted
        """
        pass

