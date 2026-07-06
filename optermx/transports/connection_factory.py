# connection_factory.py
"""
Connection factory for constructing concrete connection objects.

This module centralizes creation of connection instances (SSH, Telnet/tcp, Serial,
AGWPE), hiding constructor details from callers and enforcing consistent
keyword-only argument usage.

Information
-----------
kwargs is a conventional name (short for "keyword arguments"), but you can 
use any valid variable name preceded by two asterisks (**).

The double asterisks ** are the crucial part, indicating that the parameter 
will collect all keyword arguments passed to the function that don't correspond 
to other named parameters.

Design
------
- Factory Pattern: Encapsulates object creation so callers depend on a stable
  API (`get_connection`) rather than concrete class constructors.
- Keyword-only config: Accepts **kwargs to improve readability at call sites
  and avoid positional-argument bugs.

Notes
-----
- Example:
    get_connection("tcp", host="example.com", port=2023)
- Positional arguments are intentionally unsupported.

Revision History
----------------
08/14/25  Removed TelnetConnection from the set of connections.
"""

from transports.ssh_connection import SSHConnection
from transports.tcp_connection import TcpConnection
from transports.serial_connection import SerialConnection
from transports.agw_connection import AGWConnection

def get_connection(conn_type, **kwargs):
    """
    Create and return a concrete connection instance for the requested type.

    written to accept keyword args (**kwargs) and not positional ones. 
    Works: get_connection("agwpe", host=..., port=...) → fills kwargs["host"]
    Fails: get_connection("agwpe", host, port) → passes positional args

    Parameters
    ----------
    conn_type : str
        The connection type to construct. Supported values:
        - 'ssh'     → SSHConnection(host, port, username, password)
        - 'tcp'     → TcpConnection(host, port)
        - 'serial'  → SerialConnection(port, baudrate=9600, databits=8,
                                        stopbits=1, parity="None",
                                        flowcontrol="RTS/CTS")
        - 'agwpe'   → AGWConnection(host, port)

    **kwargs : Any
        Keyword-only parameters required by the selected connection type.
        This function purposely rejects positional arguments for clarity.

        For 'ssh':
            host : str
            port : int
            username : str
            password : str

        For 'tcp':
            host : str
            port : int

        For 'serial':
            port : str
            baudrate : int, optional (default 9600)
            databits : int, optional (default 8)
            stopbits : int, optional (default 1)
            parity : str, optional (default "None")
            flowcontrol : str, optional (default "RTS/CTS")

        For 'agwpe':
            host : str
            port : int

    Returns
    -------
    object
        An instance of the requested connection class.

    Raises
    ------
    KeyError
        If a required keyword is missing in **kwargs for the selected type.
        (E.g., calling with `conn_type='tcp'` but omitting `host`.)
    ValueError
        If `conn_type` is not one of the supported values.
    """
    if conn_type == 'ssh':
        return SSHConnection(
            kwargs['host'],
            kwargs['port'],
            kwargs['username'],
            kwargs['password']
        )
    elif conn_type == 'tcp':
        return TcpConnection(
            kwargs['host'],
            kwargs['port']
        )
    elif conn_type == 'serial':
        return SerialConnection(
            kwargs['port'],
            kwargs.get('baudrate', 9600),
            kwargs.get('databits', 8),
            kwargs.get('stopbits', 1),
            kwargs.get('parity', "None"),
            kwargs.get('flowcontrol', "RTS/CTS"),
        )
    elif conn_type == 'agwpe':
        return AGWConnection(
            kwargs['host'],
            kwargs['port']
        )
    else:
        raise ValueError(f"Unsupported connection type: {conn_type}")