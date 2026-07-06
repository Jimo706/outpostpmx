# connection_factory.py
"""
Connection factory for constructing concrete connection objects.

OutpostX/OpTermX compatibility note:
- We use lazy imports so missing transports (ssh/tcp/agwpe) do not break serial-first usage.
"""

from __future__ import annotations


def get_connection(conn_type: str, **kwargs):
    """
    Create and return a concrete connection instance for the requested type.

    Supported values:
    - 'ssh'     → SSHConnection(host, port, username, password)
    - 'tcp'     → TcpConnection(host, port)
    - 'serial'  → SerialConnection(port, baudrate=9600, databits=8, stopbits=1,
                                  parity="None", flowcontrol="RTS/CTS")
    - 'agwpe'   → AGWConnection(host, port)

    Lazy-import behavior:
    - Only imports the module for the requested connection type.
    - This allows OutpostX to use 'serial' without requiring ssh/tcp/agw files.
    """
    c = (conn_type or "").strip().lower()

    if c == "ssh":
        # Lazy import
        from .ssh_connection import SSHConnection
        return SSHConnection(
            kwargs["host"],
            kwargs["port"],
            kwargs["username"],
            kwargs["password"],
        )

    if c == "tcp":
        from .tcp_connection import TcpConnection
        return TcpConnection(
            kwargs["host"],
            kwargs["port"],
            connect_timeout=kwargs.get("connect_timeout", 5.0),
            crlf=kwargs.get("crlf", False),
        )

    if c == "serial":
        from .serial_connection import SerialConnection
        return SerialConnection(
            kwargs["port"],
            kwargs.get("baudrate", 9600),
            kwargs.get("databits", 8),
            kwargs.get("stopbits", 1),
            kwargs.get("parity", "None"),
            kwargs.get("flowcontrol", "RTS/CTS"),
        )

    if c == "agwpe":
        from .agw_connection import AGWConnection
        return AGWConnection(
            kwargs["host"],
            kwargs["port"],
        )

    raise ValueError(f"Unsupported connection type: {conn_type}")
