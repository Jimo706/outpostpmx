# get_char.py (optional utility file)

import sys
import platform

IS_WINDOWS = platform.system() == 'Windows'

if IS_WINDOWS:
    # msvcrt: provides access to functions from the Microsoft Visual C++ runtime library 
    #   on Windows systems.  It allows Python programs to interact with low-level.  Windows 
    #   functionalities, esp those related to the console and standard C library functions.
    import msvcrt
else:

    # tty: Terminal control functions. The tty module defines functions for putting the 
    #    tty into cbreak and raw modes
    # termios: a POSIX standard interface used to control terminal devices in Unix-like 
    #    operating systems
    import tty, termios

# This function handles cross-platform keyboard input. esp  in character-by-character 
#   mode which is crucial for interactive serial work.
def get_char():
    if IS_WINDOWS:
        try:
            return msvcrt.getch().decode('UTF-8')
        except UnicodeDecodeError:
            return ''
    else:
        return sys.stdin.read(1)

        
def bin2ascii(indata: bytes) -> str:
    """
    Converts binary data to a hex dump with printable ASCII on the side.
    Similar in behavior to the original VB6 Bin2Ascii function.
    """
    output = ""
    decode = ""
    
    for i in range(0, len(indata)):
        # New line and ascii decode every 16 bytes
        if i % 16 == 0:
            if i > 0:
                output += " | " + decode + "\n"
                decode = ""
        
        # Get hex representation, pad with 0 if needed
        hex_byte = f"{indata[i]:02x}"
        output += f" {hex_byte}"

        # Determine printable ASCII or '.'
        if 32 <= indata[i] <= 126:
            decode += chr(indata[i])
        else:
            decode += "."

    # Handle last line padding if less than 16 bytes
    remaining = 16 - (len(indata) % 16)
    if remaining < 16:
        output += " --" * remaining

    output += " | " + decode + "\n"
    return output

def to_bool(value):
    """
    Makes False, 0, No, etc. become actual boolean.
    bool() doesn’t convert strings like "False" the way you expect;  only checks if the string is empty or not.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)
