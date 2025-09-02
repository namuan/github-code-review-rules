"""
Logging configuration and utilities
"""

import logging
import sys
from typing import Optional
from pathlib import Path

from ..config import get_settings


def setup_logging(
    name: Optional[str] = None,
    level: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Setup logging configuration
    
    Args:
        name: Logger name
        level: Log level
        format_string: Log format string
        
    Returns:
        Configured logger instance
    """
    settings = get_settings()
    
    # Use provided parameters or fall back to settings
    log_level = level or settings.log_level
    log_format = format_string or settings.log_format
    
    # Create logger
    logger = logging.getLogger(name or __name__)
    
    # Set level
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Create formatter
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return setup_logging(name)


def setup_file_logging(
    logger: logging.Logger,
    log_file: Path,
    level: Optional[str] = None
) -> logging.Logger:
    """
    Add file handler to logger
    
    Args:
        logger: Existing logger instance
        log_file: Path to log file
        level: Log level for file handler
        
    Returns:
        Updated logger instance
    """
    settings = get_settings()
    log_level = level or settings.log_level
    
    # Create logs directory if it doesn't exist
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Create formatter
    formatter = logging.Formatter(settings.log_format)
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(file_handler)
    
    return logger


class LoggerMixin:
    """Mixin class to add logging capability to other classes"""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class"""
        return get_logger(self.__class__.__name__)