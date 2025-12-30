"""
Ring buffer for storing rolling time-series data.
"""

from collections import deque
from typing import List, Optional
import time


class RingBuffer:
    """Fixed-size rolling buffer for time-series data."""
    
    def __init__(self, max_size: int):
        self.max_size = max_size
        self.timestamps = deque(maxlen=max_size)
        self.values = deque(maxlen=max_size)
    
    def append(self, value: Optional[float], timestamp: Optional[float] = None):
        """Add a value with timestamp."""
        if timestamp is None:
            timestamp = time.time()
        self.timestamps.append(timestamp)
        self.values.append(value)
    
    def get_arrays(self) -> tuple[List[float], List[Optional[float]]]:
        """Get timestamps and values as lists."""
        return list(self.timestamps), list(self.values)
    
    def get_latest(self) -> Optional[float]:
        """Get the most recent value."""
        return self.values[-1] if self.values else None
    
    def clear(self):
        """Clear all data."""
        self.timestamps.clear()
        self.values.clear()
    
    def __len__(self):
        return len(self.values)

