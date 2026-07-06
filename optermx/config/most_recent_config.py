import json, os, hashlib, time
from dataclasses import dataclass, asdict
# 260522: migrate from PyQt5 to PySide6
from PySide6.QtWidgets import QMenu
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QAction

MRC_MAX = 10

def _normalize_config(cfg: dict) -> dict:
    """ 
    This function cleans and stabilizes a config dict so that two logically identical 
    configurations (but with different runtime junk) look identical for comparison/hashing.
    """
    # Example: drop session-only things
    # keys that are volatile or session-specific (like timestamps, error strings, or random session IDs)
    # not included in the comparison, else every run would look 'different' even though the real connection settings are the same
    drop = {"session_id", "last_error", "connected_at"} 

    # Builds a new dictionary with only the “stable” fields
    # Sorting the keys ensures the dictionary is always built in a consistent order.
    return {k: cfg[k] for k in sorted(cfg) if k not in drop}


def _config_key(cfg: dict) -> str:
    """
    This function generates a unique string identifier for a given configuration.
    That identifier is used to detect duplicates in your MRC list.

    Because dictionaries in Python aren't directly hashable across sessions, we want a quick, stable key for each config:
    * Two configs that are logically the same -> produce the same hash.
    * A different config -> produces a totally different hash.
    """
    # First, clean the config with _normalize_config
    norm = _normalize_config(cfg)
    
    # Converts the cleaned dict into a JSON string, with keys sorted.
    # Makes the JSON compact (no spaces) so two equal dicts produce identical text.
    blob = json.dumps(norm, sort_keys=True, separators=(",", ":")).encode("utf-8")

    # Runs the bytes through SHA-1 (a hashing algorithm).  
    # .hexdigest() produces a 40-character hex string
    return hashlib.sha1(blob).hexdigest()


"""
The data structure that represents one row in your "Most Recent Configurations" list.
This is Python's shorthand for defining a "record class."

The MrcEntry class is just the container for one saved config, making it easy to store 
a list, save/load JSON, and display in your menu.
"""
@dataclass
class MrcEntry:
    """
    The data structure that represents one row in your "Most Recent Configurations" list.
    This is Python's shorthand for defining a "record class."

    The MrcEntry class is just the container for one saved config, making it easy to store 
    a list, save/load JSON, and display in your menu.
    """
    ts: float                 # unix timestamp, seconds since epoch
    label: str                # short human label shown in the File > MRC menu
    iftype: str               # "serial" | "tcp" | "ssh" | "agwpe" | ... Helps you decide which run_* function to call
    config: dict              # the actual parameters needed to reconnect
    key: str                  # dedup key; the fingerprint string; ensures this entry is unique


class MostRecentConfig(QObject):
    # Optional: signal if you want to notify others
    updated = Signal()

    def __init__(self, file_menu: QMenu, storage_path: str, ini=None, parent=None):
        super().__init__(parent)                    # critical: wires up self.parent()
        self.file_menu = file_menu                  # The File menu (QMenu)
        self.storage_path = storage_path            # e.g., ~/.OpTermx/mrc.json
        self.ini = ini                              #  reference to ini
        self.submenu_title = "Most Recent Configuration"
        self.submenu = QMenu(self.submenu_title, self.file_menu)
        self.file_menu.addMenu(self.submenu)
        self.entries: list[MrcEntry] = []
        self._load()
        self.create_mrc_menu()

    # 1) AddMrcEntry
    def add_mrc_entry(self, iftype: str, config: dict, label: str = None):
        """
        How an MRC entry gets added, called after a successful Connect
            * iftype: which interface type ("serial", "tcp", "ssh", etc.).
            * config: the actual settings (host, port, baudrate…).
            * label: optional friendly text to show in the menu (if not given, we’ll generate one).
        """
        # Clean up the config (strip volatile fields) & Generate a unique fingerprint
        cfg_norm = _normalize_config(config)
        key = _config_key(cfg_norm)

        # If the caller didn't supply a menu label, create one from the config.
        if label is None:
            # Example labels: "Serial COM3 9600" or "TCP 192.168.1.10:23"
            label = self._default_label(iftype, cfg_norm)

        # De-dup: Remove any old entry with the same fingerprint
        self.entries = [e for e in self.entries if e.key != key]

        # Make a new MrcEntry object; Insert at top
        self.entries.insert(0, MrcEntry(
            ts=time.time(), label=label, iftype=iftype, config=cfg_norm, key=key
        ))

        # Enforce cap; Prevents the list from growing forever; 
        # Oldest entries at the bottom get dropped.
        if len(self.entries) > MRC_MAX:
            self.entries = self.entries[:MRC_MAX]

        # Calls the method that writes the self.entries list back to disk (JSON file).
        # Clears the old MRC menu items and rebuilds them from the updated self.entries
        self._save()
        self.create_mrc_menu()   # rebuild menu
        # self.updated.emit()    # optional, other possible uses
 

    # 2) CreateMrcMenu
    def create_mrc_menu(self):
        """
        (re)builds the "Most Recent Config" submenu from the in-memory list.
        """
        # Start from a clean slate: wipe existing actions so you don't duplicate items when the list changes.
        self.clear_mrc_menu()
        # If nothing to show, then insert a disabled placeholder so the menu isn't empty/confusing, then bail.
        if not self.entries:
            disabled = QAction("(No recent configurations)", self.submenu)
            disabled.setEnabled(False)
            self.submenu.addAction(disabled)
            return

        # Build each visible row.
        for idx, entry in enumerate(self.entries, start=1):
            text = f"&{idx} {entry.label}"  # accelerators 1..9
            # Parent is self.submenu, so Qt manages the action's lifetime.
            act = QAction(text, self.submenu)
            # Stash all we need to reconnect; Attach the payload right onto the QAction via setData.
            act.setData({"iftype": entry.iftype, "config": entry.config})
            act.triggered.connect(self._detect_mrc_click)
            self.submenu.addAction(act)

        # Housekeeping actions
        self.submenu.addSeparator()
        clear = QAction("Clear List", self.submenu)
        clear.setToolTip("Remove all Most Recent Configuration entries")
        clear.triggered.connect(self.clear_all_mrc)
        self.submenu.addAction(clear)


    # 3) ClearMrcMenu
    def clear_mrc_menu(self):
        self.submenu.clear()

    # 4) DetectMrcClick
    # Declares this method as a Qt slot.
    @Slot()
    def _detect_mrc_click(self, checked=False):
        # gets the object that emitted the signal → in this case, the menu item (QAction) that was clicked.
        # if for some reason the sender isn’t an action, bail out.
        act = self.sender()
        if not isinstance(act, QAction):
            return
        # previously, when the action was created, we stashed the config inside it.
        # Here we pull that dictionary back out. If nothing's there, use an empty dict.
        payload = act.data() or {}

        # Extract the interface type and stored configuration dict
        iftype = payload.get("iftype")
        cfg = payload.get("config", {})
        try:
            self.load_config_into_ini(iftype, cfg)

            # >>> Your integration point:
            #  - Put cfg back into your appconfig/INI/GUI fields
            #  - Then call the appropriate run/connect path
            #
            # Example pseudo:
            # self.parent().ini.update_section(iftype, cfg)   # or load into widgets
            # self.parent().adapter = get_adapter(iftype, cfg)
            # self.parent().adapter.run()  # or run_serial / run_telnet / run_agwpe

            # Hand off to your integration routine, where we actually load those settings 
            # into your app and call the right connection method
            self._apply_config_and_connect(iftype, cfg)
        except Exception as e:
            if hasattr(self, "append_to_session"):
                self.append_to_session(f"[MRC] Error applying config: {e}\n")


    def load_config_into_ini(self, iftype: str, cfg: dict):
        """
        Update the INI/appconfig store with values from an MRC entry.

        Parameters
        ----------
        iftype : str
            Interface type ("serial", "tcp", "ssh", "agwpe", ...).
        cfg : dict
            Configuration dictionary containing key/value pairs to restore.
        """
        try:
            # assume self.ini is your appconfig object
            # Guard clause: makes sure the class has an ini property (your appconfig instance).
            if not hasattr(self, "ini"):
                raise RuntimeError("No ini object available on this class")

            # update the section for this interface
            for key, value in cfg.items():
                # Ensure we always write as string
                # Iterates all cfg key/values, writes each into the [section] of the INI named after iftype.
                self.ini.set(iftype, key, str(value))
                # print(f"iftype={iftype}, key={key}, value={str(value)}")
            self.ini.save()

        except Exception as e:
            if hasattr(self, "append_to_session"):
                self.append_to_session(f"[MRC] Failed to update INI for {iftype}: {e}\n")


    def _apply_config_and_connect(self, iftype: str, cfg: dict):
        """Replace this with your app’s real load+run logic."""
        # Example sketch:
        main = self.parent() # or self.file_menu.parent()
        try:
            main.update_status(iftype)

            # 1) load config into your settings model
            # This may be pushing it back into the ini
            if hasattr(main, "load_config_into_ui"):
                main.load_config_into_ui(iftype, cfg)
            return

            # 2) run appropriate connection method
            if iftype == "serial": # and hasattr(main, "run_serial"):
                main.adapter.run_serial(cfg)
            elif iftype == "tcp" and hasattr(main, "run_telnet"):
                main.run_telnet(cfg)
            elif iftype == "ssh" and hasattr(main, "run_ssh"):
                main.run_ssh(cfg)
            elif iftype == "agwpe" and hasattr(main, "run_agwpe_terminal"):
                main.run_agwpe_terminal(cfg)
            else:
                # Fallback: generic runner if you expose one
                if hasattr(main, "run_with_config"):
                    main.run_with_config(iftype, cfg)
        except Exception as e:
            # Show a message in your session console or status bar
            if hasattr(main, "append_to_session"):
                main.append_to_session(f"[MRC] Failed to run {iftype}: {e}\n")

    def clear_all_mrc(self):
        """
        Wipe all MRC entries (memory + disk) and rebuild the menu.
        This is a just-in-case function, possibly an option to click
        """
        self.entries = []
        try:
            # Persist empty list
            self._save()
        except Exception:
            pass
        # Rebuild menu and notify
        self.create_mrc_menu()
        self.updated.emit()


    # 5) ReadMrcFile
    def _load(self):
        path = os.path.expanduser(self.storage_path)
        if not os.path.exists(path):
            self.entries = []
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.entries = [
                MrcEntry(
                    ts=e.get("ts", 0.0),
                    label=e.get("label", ""),
                    iftype=e.get("iftype", ""),
                    config=e.get("config", {}),
                    key=e.get("key") or _config_key(e.get("config", {})),
                )
                for e in raw.get("entries", [])
            ]
        except Exception:
            self.entries = []

    # 6) WriteMrcFile
    def _save(self):
        path = os.path.expanduser(self.storage_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        serializable = {"entries": [asdict(e) for e in self.entries]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)

    # Helpers
    def _default_label(self, iftype: str, cfg: dict) -> str:
        try:
            if iftype == "serial":
                return f"Serial {cfg.get('port')} {cfg.get('baudrate','')}"
            if iftype == "tcp":
                return f"TCP {cfg.get('host')}:{cfg.get('port',23)}"
            if iftype == "ssh":
                return f"SSH {cfg.get('user','')}@{cfg.get('host')}:{cfg.get('port',22)}"
            if iftype == "agwpe-bbs":
                return f"AGWPE BBS {cfg.get('fmcall')} to {cfg.get('tocall','')}"
            if iftype == "agwpe-unproto":
                return f"AGWPE Unproto {cfg.get('port')}:{cfg.get('baudrate')} ({cfg.get('unprotoid','')})"
        except Exception:
            pass
        return f"{iftype} session"
      

