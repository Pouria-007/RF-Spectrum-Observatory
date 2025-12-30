"""
Logging setup using Loguru.
"""

import sys
from pathlib import Path
from loguru import logger

from .config import LoggingConfig


def setup_logging(config: LoggingConfig) -> None:
    """
    Configure Loguru logger.
    
    Args:
        config: Logging configuration
    """
    # Remove default handler
    logger.remove()
    
    # Add console handler
    logger.add(
        sys.stderr,
        format=config.format,
        level=config.level,
        colorize=True,
    )
    
    # Add file handler
    log_path = Path(config.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        log_path,
        format=config.format,
        level=config.level,
        rotation="100 MB",
        retention="7 days",
        compression="zip",
    )
    
    logger.info(f"Logging initialized: level={config.level}, file={config.log_file}")


# Convenience function to get logger
def get_logger(name: str):
    """Get a logger with a specific name."""
    return logger.bind(name=name)

