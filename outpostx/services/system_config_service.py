# system_config_service.py
# 251207: updated

from dataclasses import dataclass
from typing import Optional

from PySide6 import QtCore

from data.station_profile_repo import StationProfileRepository
from data.tactical_profile_repo import TacticalProfileRepository
from data.bbs_profile_repo import BBSProfileRepository
from data.interface_profile_repo import InterfaceProfileRepository
from data.bbs_logon_repo import BBSLogonRepository

from app_config import AppConfig
from services.send_receive_settings import SendReceiveSettings, load_send_receive_settings

@dataclass(frozen=True)
class ActiveSelection:
    """Snapshot of the currently active configuration."""

    station_id: Optional[int]
    legal_call: Optional[str]
    station_user_name: Optional[str]

    tactical_id: Optional[int]
    tactical_call: Optional[str]

    bbs_id: Optional[int]
    bbs_name: Optional[str]
    bbs_call: Optional[str]

    interface_id: Optional[int]
    interface_name: Optional[str]


class SystemConfigService(QtCore.QObject):
    """Central service that knows which Station/Tactical/BBS/Interface are active."""

    activeConfigChanged = QtCore.Signal(ActiveSelection)

    def __init__(
        self,
        config: AppConfig,
        station_repo: StationProfileRepository,
        tactical_repo: TacticalProfileRepository,
        bbs_repo: BBSProfileRepository,
        iface_repo: InterfaceProfileRepository,
        bbs_logons_repo: BBSLogonRepository,
        parent: Optional[QtCore.QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._station_repo = station_repo
        self._tactical_repo = tactical_repo
        self._bbs_repo = bbs_repo
        self._iface_repo = iface_repo
        self._bbs_logons_repo = bbs_logons_repo
        self._snapshot = self._rebuild_snapshot_from_repos()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_active_selection(self) -> ActiveSelection:
        """Return the current snapshot."""
        return self._snapshot

    # ----- setters used by SetupDialog "Activate" -----
    def set_active_station(self, station_id: Optional[int]) -> None:
        """
        Set the active Station ID profile.

        If station_id is None -> all station_profiles become inactive.
        """
        self._station_repo.set_active(station_id)
        self._update_and_emit()

    def set_active_tactical(self, tactical_id: Optional[int]) -> None:
        """
        Set/toggle the active Tactical ID profile.

        If tactical_id is None -> clears any active Tactical ID.
        """
        self._tactical_repo.set_active(tactical_id)
        self._update_and_emit()

    def set_active_bbs(self, bbs_id: Optional[int]) -> None:
        """
        Set the active BBS profile.

        If bbs_id is None -> clears any active BBS.
        """
        self._bbs_repo.set_active(bbs_id)
        self._update_and_emit()

    def set_active_interface(self, interface_id: Optional[int]) -> None:
        """Set the active Interface profile."""
        self._iface_repo.set_active(interface_id)
        self._update_and_emit()

    def refresh_from_repos(self) -> None:
        """
        Manually re-sync from repos without changing any 'active' flags.

        Useful if something else (e.g., a migration) changed is_active.
        """
        self._update_and_emit()


    def get_signature_context(self) -> dict[str, str]:
        """
        Return signature information for the compose editor.

        Result dict:
            {
                "station_signature": "<station sig or ''>",
                "tactical_signature": "<tactical sig or ''>",
                "preferred": "tactical" | "station" | "",
            }

        IRS 5.1.3 rules:

        - If Station is active and has a signature → button can append Station signature.
        - If Station AND Tactical are active and Tactical has a signature → Tactical wins.
        """
        station = self._station_repo.get_active()
        tactical = self._tactical_repo.get_active()

        station_sig = (getattr(station, "signature", "") or "").strip() if station else ""
        tactical_sig = (getattr(tactical, "signature", "") or "").strip() if tactical else ""

        if tactical_sig:
            preferred = "tactical"
        elif station_sig:
            preferred = "station"
        else:
            preferred = ""

        return {
            "station_signature": station_sig,
            "tactical_signature": tactical_sig,
            "preferred": preferred,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _update_and_emit(self) -> None:
        new_snapshot = self._rebuild_snapshot_from_repos()
        # Avoid spurious signals if nothing actually changed
        if new_snapshot != self._snapshot:
            self._snapshot = new_snapshot
            self.activeConfigChanged.emit(self._snapshot)

    def _rebuild_snapshot_from_repos(self) -> ActiveSelection:
        station = self._station_repo.get_active()
        tactical = self._tactical_repo.get_active()
        bbs = self._bbs_repo.get_active()
        iface = self._iface_repo.get_active()

        # Station
        if station:
            legal_call = (station.legal_call_sign or "").upper() or None
            user_name = (station.user_name or "").strip() or None
            station_id = station.id
        else:
            legal_call = None
            user_name = None
            station_id = None

        # Tactical
        if tactical:
            tactical_call = (tactical.tactical_call_sign or "").upper() or None
            tactical_id = tactical.id
        else:
            tactical_call = None
            tactical_id = None

        # BBS name
# BBS
        if bbs:
            bbs_call = (bbs.bbs_call or "").strip() or None
            bbs_name = (bbs.friendly_name or "").strip() or bbs_call or None
            bbs_id = bbs.id
        else:
            bbs_call = None
            bbs_name = None
            bbs_id = None


        # Interface
        if iface:
            iface_name = (iface.friendly_name or "").strip() or (iface.interface_name or "").strip() or None
            iface_id = iface.id
        else:
            iface_id = None
            iface_name = None

        return ActiveSelection(
            station_id=station_id,
            legal_call=legal_call,
            station_user_name=user_name,
            tactical_id=tactical_id,
            tactical_call=tactical_call,
            bbs_id=bbs_id,
            bbs_name=bbs_name,
            bbs_call=bbs_call,
            interface_id=iface_id,
            interface_name=iface_name,
        )


    # ------------------------------------------------------------------
    # Convenience Getters
    # ------------------------------------------------------------------
    def get_active_station(self):
        sel = self.get_active_selection()
        if not sel or not sel.station_id:
            return None
        return self._station_repo.get(sel.station_id)

    def get_active_tactical(self):
        sel = self.get_active_selection()
        if not sel or not sel.tactical_id:
            return None
        return self._tactical_repo.get(sel.tactical_id)


    def get_default_from_call(self) -> str:
        """
        Return the callsign used as the default From: value for new outbound messages.

        Rule:
        - legal_call_sign is required
        - tactical_call_sign, when active/present, overrides legal_call_sign
        """
        station = self.get_active_station()
        tactical = self.get_active_tactical()

        legal_call = (getattr(station, "legal_call_sign", "") or "").strip().upper()
        tactical_call = (getattr(tactical, "tactical_call_sign", "") or "").strip().upper()

        if not legal_call:
            raise RuntimeError(
                "Cannot create a message: active station legal call sign is empty."
            )

        return tactical_call or legal_call


    def get_active_interface(self):
        sel = self.get_active_selection()
        if not sel or not sel.interface_id:
            return None
        return self._iface_repo.get(sel.interface_id)

    def get_active_bbs(self):
        sel = self.get_active_selection()
        if not sel or not sel.bbs_id:
            return None
        return self._bbs_repo.get(sel.bbs_id)

    def get_send_receive_settings(self) -> SendReceiveSettings:
        return load_send_receive_settings(self._config)


    def get_bbs_logon_for_session(
        self,
        *,
        bbs_connect_call: str,
        operator_id: str,
    ):
        """
        Called by: service_send_receive_session.py
        Return the BBS logon credentials for the given session.

        Lookup key:
            (bbs_connect_call, operator_id)

        Args:
            bbs_connect_call: BBS connect callsign (e.g. "W1XSC-1")
            operator_id: Active operator identity (tactical or legal call)

        Returns:
            BBSLogon object or None if not found.
        """

        connect_call = (bbs_connect_call or "").strip().upper()
        operator = (operator_id or "").strip().upper()
        # CONFIRMED,  print(f"connect_call={connect_call}, operator={operator}")

        if not connect_call or not operator:
            return None

        # Delegate to repository (calls: bbs_logon_repo.py)
        logon = self._bbs_logons_repo.get_by_connect_call_and_operator(
            connect_call,
            operator,
        )
        from dataclasses import asdict
        ### CONFIRNED:  print(asdict(logon))

        return logon
    
    def set_active_combination(
        self,
        *,
        station_id: Optional[int],
        tactical_id: Optional[int],
        bbs_id: Optional[int],
        interface_id: Optional[int],
    ) -> None:
        """
        Set active Station/Tactical/BBS/Interface as one logical operation.

        Used by File > Most Recently Used so the UI can restore a saved
        operating combination without emitting multiple intermediate UI states.
        """
        self._station_repo.set_active(station_id)
        self._tactical_repo.set_active(tactical_id)
        self._bbs_repo.set_active(bbs_id)
        self._iface_repo.set_active(interface_id)
        self._update_and_emit()    
        