# 07/27/25: Added INI file support
# appconfig.py
"""
Application configuration manager.

This module defines `appconfig`, a lightweight wrapper around
`configparser.ConfigParser` that handles loading, saving, and
querying application settings stored in an INI file.

Features
--------
- Loads configuration from a specified INI file.
- Creates the file with default sections/values if it does not exist.
- Provides typed getters (`get`, `getint`) with optional fallbacks.
- Offers convenience methods to retrieve grouped settings for
  Serial, Telnet (raw TCP), and AGWPE connections.

Notes
-----
Default sections created if no INI file is found:
    - [general]
    - [ssh]
    - [rawtcp]
    - [serial]
    - [agwpe]
    - [logging]
"""

from pathlib import Path    # 260702
import configparser
import os

class appconfig:
    """
    Wrapper class around ConfigParser for application settings.

    Parameters
    ----------
    filename : str, optional
        Name of the configuration file (default 'optermx.ini').

    Attributes
    ----------
    filename : str
        Path to the configuration file.
    config : ConfigParser
        Internal parser instance storing the loaded configuration.
    """
    def __init__(self, filename="optermx.ini", config_dir=None):    # 260702
        if config_dir is not None:
            config_dir = Path(config_dir).expanduser()
            config_dir.mkdir(parents=True, exist_ok=True)
            self.filename = str(config_dir / filename)
        else:
            self.filename = filename

        self.config = configparser.ConfigParser()
        self._load()

    def _load(self):
        """
        Load configuration from file, or create defaults if not found.

        Notes
        -----
        - If the file does not exist, `_set_defaults` is called and
          the defaults are written out immediately.
        - Otherwise, the file is read and parsed.
        """
        if not os.path.exists(self.filename):
            self._set_defaults()
            self.save()
        else:
            self.config.read(self.filename)

    # if the file name does not exist, then create the default .ini file
    def _set_defaults(self):
        """
        Define default configuration values for all supported sections.

        Sections created:
            - general
            - ssh
            - rawtcp
            - serial
            - agwpe
            - logging
        """
        self.config['general'] = {
            'interface': 'Serial',
            'fontsize': "12"
        }
        self.config['ssh'] = {
            'Host': '192.168.1.100',
            'Port': '22',
            'UserName': 'user',
            'AuthMethod': 'password',
            'PrivateKey': ''
        }
        self.config['rawtcp'] = {
            'Host': '192.168.1.100',
            'Port': '23'
        }
        self.config['serial'] = {
            'Port': 'COM3',
            'BaudRate': '9600',
            'DataBits': '8',
            'StopBits': '1',
            'Parity': 'None'
        }
        self.config['agwpe'] = {
            'Host': '127.0.0.1',
            'Port': '8000',
            'fmcall': 'YRCALL',
            'tocall': 'YRBBS',
            'TimeOut': '5000'
        }
        self.config['logging'] = {
            'EnableFileLog': 'True',
            'EnableDebug': 'False',
            'LogFile': 'app.log'
        }


    def get(self, section, key, fallback=None):
        """
        Retrieve a string value from the configuration.

        Parameters
        ----------
        section : str
            The section name.
        key : str
            The option key.
        fallback : Any, optional
            Value to return if the key is missing.

        Returns
        -------
        str
            The configuration value, or `fallback` if missing.
        """
        return self.config.get(section, key, fallback=fallback)


    def getint(self, section, key, fallback=None):
        """
        Retrieve an integer value from the configuration.

        Parameters
        ----------
        section : str
            The section name.
        key : str
            The option key.
        fallback : Any, optional
            Value to return if the key is missing.

        Returns
        -------
        int
            The configuration value as an integer.
        """
        # 260630, fix case where Telnet is not set
        # return self.config.getint(section, key, fallback=fallback)
        value = self.config.get(section, key, fallback=None)
        if value is None:
            return fallback

        value = str(value).strip()
        if value == "":
            return fallback

        try:
            return int(value)
        except ValueError:
            return fallback

    
    def getbool(self, section: str, key: str, fallback: bool = False) -> bool:
        """
        Retrieve a boolean value from the configuration.

        Parameters
        ----------
        section : str
            The section name.
        key : str
            The option key.
        fallback : bool, optional
            Value to return if the key is missing (default False).

        Returns
        -------
        bool
            The configuration value interpreted as a boolean.
        """
        return self.config.getboolean(section, key, fallback=fallback)

    def set(self, section, key, value):
        """
        Set a configuration value, creating the section if necessary.

        Parameters
        ----------
        section : str
            Section name.
        key : str
            Option key.
        value : Any
            Value to set (converted to string internally).
        """
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))


    def save(self):
        """
        Write the current configuration state back to the ini file.
        """
        with open(self.filename, 'w') as f:
            self.config.write(f)


    def getSerial(self) -> dict:
        """
        Return serial connection settings as a dictionary.

        Returns
        -------
        dict
            Keys: port, baudrate, databits, stopbits, parity, flowControl
        """
        cfg = {"port": self.get('serial', 'port'), 
               "baudrate": self.getint('serial', 'baudrate'),
               "databits": self.getint('serial', 'databits'),
               "stopbits": self.getint('serial', 'stopbits'),
               "parity": self.get('serial', 'parity'),
               "flowControl": self.get('serial', 'flowControl'),
        }
        return cfg


    def getTelnet(self) -> dict:
        """
        Return raw TCP (Telnet-style) settings as a dictionary.

        Returns
        -------
        dict
            Keys: host, port
        """
        cfg = {"host": self.get('tcp', 'host'),
               "port": self.getint("tcp", "port", fallback=None),
              }
        return cfg


    def getAgwpe(self) -> dict:
        """
        Return AGWPE-related settings as a dictionary.

        Returns
        -------
        dict
            Keys: host, port, fmcall, logonreq, mode, username, password,
                  bbsconnect, tocall, bbsvia, unprotoid, unprotoconnect,
                  unprotovia
        """
        cfg = {"host": self.get('agwpe', 'host'),
               "port": self.getint('agwpe', 'port'),
               "fmcall": self.get('agwpe', 'fmcall'),
               "logonreq": self.get('agwpe', 'logonreq'),
               "mode": self.get('agwpe', 'mode'),
               "username": self.get('agwpe', 'username'),
               "password": self.get('agwpe', 'password'),
               "bbsconnect": self.get('agwpe-bbs', 'connect'),
               "fmcall": self.get('agwpe', 'fmcall'),
               "tocall": self.get('agwpe-bbs', 'tocall'),
               "bbsvia": self.get('agwpe-bbs', 'via'),
               "unprotoid": self.get('agwpe-unproto', 'unprotoid'),
               "unprotoconnect": self.get('agwpe-unproto', 'connect'),
               "unprotovia": self.get('agwpe-unproto', 'via'),
        }
        return cfg
