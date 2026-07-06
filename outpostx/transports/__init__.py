"""
OutpostX transport layer.

This package provides connection factories and concrete transport
implementations (serial, TCP, SSH, AGWPE) used by both:

- OutpostX Send/Receive sessions
- (optionally) OpTermX later, once aligned
"""

from .connection_factory import get_connection
from .connection_base import BaseConnection

__all__ = ["get_connection", "BaseConnection"]
