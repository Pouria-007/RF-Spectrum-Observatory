"""
Timestamp utilities for nanosecond-precision timing.
"""

import time
from typing import Optional


def now_ns() -> int:
    """
    Get current time in nanoseconds since epoch.
    
    Returns:
        Nanosecond timestamp
    """
    return time.time_ns()


def ns_to_sec(ns: int) -> float:
    """Convert nanoseconds to seconds."""
    return ns / 1e9


def sec_to_ns(sec: float) -> int:
    """Convert seconds to nanoseconds."""
    return int(sec * 1e9)


def ns_to_ms(ns: int) -> float:
    """Convert nanoseconds to milliseconds."""
    return ns / 1e6


def format_timestamp(ns: int) -> str:
    """
    Format nanosecond timestamp as human-readable string.
    
    Args:
        ns: Nanosecond timestamp
        
    Returns:
        Formatted string (e.g., "2025-12-28 14:30:45.123456")
    """
    import datetime
    dt = datetime.datetime.fromtimestamp(ns / 1e9)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")


def align_gps_to_iq(iq_timestamp_ns: int, gps_fixes: list, tolerance_ns: int = int(1e9)) -> Optional[int]:
    """
    Find the closest GPS fix to an IQ frame timestamp.
    
    Args:
        iq_timestamp_ns: IQ frame timestamp
        gps_fixes: List of GPSFix objects
        tolerance_ns: Maximum time difference to accept (default 1 second)
        
    Returns:
        Index of closest GPS fix, or None if no fix within tolerance
    """
    if not gps_fixes:
        return None
    
    min_delta = float('inf')
    min_idx = None
    
    for idx, fix in enumerate(gps_fixes):
        delta = abs(fix.gps_timestamp_ns - iq_timestamp_ns)
        if delta < min_delta:
            min_delta = delta
            min_idx = idx
    
    if min_delta <= tolerance_ns:
        return min_idx
    return None

