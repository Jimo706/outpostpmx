# connection_base.py
# Define the Base Interface


from abc import ABC, abstractmethod

class BaseConnection(ABC):
    """
    Abstract base class that defines the common interface for all 
    connection types (e.g., Serial, TCP, SSH, AGWPE). 

    This class enforces a standard set of methods that every 
    concrete connection class must implement, ensuring a 
    consistent API across different connection types.

    Information
    -----------
    "ABC" primarily refers to Abstract Base Classes. These are classes that 
    cannot be instantiated directly and are designed to serve as blueprints 
    or interfaces for other classes. Used for achieving abstraction and enforcing 
    structure in the code.

    The `@abstractmethod` decorator is used to define abstract methods within an 
    abstract class. When you decorate a method with `abstractmethod`, it becomes 
    an abstract method that must be implemented by any subclass.

    Methods
    -------
    connect():
        Establish the connection to the target endpoint.
    send(command: str):
        Transmit a command or data string over the active connection.
    receive():
        Retrieve data from the connection. The return type depends 
        on the implementation (e.g., string, bytes).
    disconnect():
        Cleanly close the connection and release any associated resources.
    """
    @abstractmethod
    def connect(self):
        """
        Establish a connection to the underlying transport (e.g., 
        open a serial port, create a TCP socket, or start an SSH session).

        Raises
        ------
        ConnectionError
            If the connection attempt fails.
        """
        pass

    @abstractmethod
    def send(self, command: str):
        """
        Send a command or data string over the established connection.

        Parameters
        ----------
        command : str
            The command or data to send.

        Raises
        ------
        ConnectionError
            If no active connection exists or the send operation fails.
        """
        pass

    @abstractmethod
    def receive(self):
        """
        Receive data from the active connection.

        Returns
        -------
        Any
            Data received from the connection. The concrete implementation 
            determines the format (e.g., str, bytes).

        Raises
        ------
        ConnectionError
            If no active connection exists or the receive operation fails.
        """
        pass

    @abstractmethod
    def disconnect(self):
        """
        Terminate the connection and release resources.

        Ensures that sockets, file descriptors, or other resources 
        associated with the connection are properly closed.

        Raises
        ------
        ConnectionError
            If an error occurs while disconnecting.
        """
        pass
