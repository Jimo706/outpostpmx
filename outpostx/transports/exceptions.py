# exceptions.py
"""
Custom exception hierarchy for OpxTerm.

This module defines all errors specific to OpxTerm’s connection
and protocol handling. All exceptions inherit from `OpTermxError`,
providing a single base type for catching application-specific
errors while allowing fine-grained handling by category.

Exception Groups
----------------
- SSH exceptions
- TCP exceptions
- Serial exceptions
- AGWPE exceptions
"""

class OpTermxError(Exception):
    """Base class for all opxterm errors."""
    pass

#class SSHConnectionError(OpTermxError):
class SSHConnectionError(OpTermxError):
    """Raised when an connection or operation fails."""
    pass

class SSHResizeError(OpTermxError):
    """Raised when terminal resize fails."""
    pass

class SSHReadError(OpTermxError):
    """Raised when reading from SSH channel fails."""
    pass

class TCPConnectionError(OpTermxError):
    """Raised when the TCP connection fails or cannot be established."""
    pass

class TCPReadError(OpTermxError):
    """Raised when reading from a TCP socket fails."""
    pass

class TCPWriteError(OpTermxError):
    """Raised when writing to a TCP socket fails."""
    pass

class SerialConnectionError(OpTermxError):
    """Raised when serial port fails to open or configure."""
    pass

class SerialReadError(OpTermxError):
    """Raised when reading from the serial port fails."""
    pass

class SerialWriteError(OpTermxError):
    """Raised when writing to the serial port fails."""
    pass

class AGWConnectionError(OpTermxError):
    """Raised when the AGWPE connection fails."""
    pass

class AGWReadError(OpTermxError):
    """Raised when reading from the AGWPE socket fails."""
    pass

class AGWProtocolError(OpTermxError):
    """Raised when the AGWPE protocol frame is malformed or invalid."""
    pass

