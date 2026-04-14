"""A group of utility functions"""

import logging

logger = logging.getLogger(__name__)


def to_float(value: str) -> float:
    """Converts a string to a float type"""
    if value is None:
        return -1.0
    try:
        return float(value)
    except (ValueError, TypeError):
        logger.warning("Failed to convert value to float: %s", value)
        return -1.0
