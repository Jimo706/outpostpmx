# optermx: services/app_paths.py

from pathlib import Path
import configparser
import sys

from PySide6.QtCore import QStandardPaths


class AppPaths:
    def __init__(self, app_name: str = "OpTermX", suite_name: str = "OutpostSuite"):
        self.app_name = app_name
        self.suite_name = suite_name

        self.program_dir = self._get_program_dir()
        self.bootstrap_file = self._find_bootstrap_file()

        self.data_dir = self._resolve_data_dir()
        self.logs_dir = self.data_dir / "logs"
        self.docs_dir = self.data_dir / "docs"
        self.bspecs_dir = self.data_dir / "bbs_specs"
        self.sounds_dir = self.data_dir / "sounds"

        # Optermx specifics
        self.optermx_dir = self.data_dir / "optermx"
        self.mrc_file = self.optermx_dir / "optermx_mrc.json"
        self.hotkey_profiles_file = self.optermx_dir / "hotkey_profiles.json"

        self._ensure_dirs()

        ### self._found_dirs()       # DEBUG ONLY, 260702, commented out


    def _get_program_dir(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[1]


    def _resolve_data_dir(self) -> Path:
        if self.bootstrap_file is not None:
            cfg = configparser.ConfigParser()
            cfg.read(self.bootstrap_file)

            data_dir = cfg.get(
                "DataDirectory",
                "DataDir",
                fallback=""
            ).strip()

            if data_dir:
                return Path(data_dir).expanduser()

        return self._default_data_dir()


    def _default_data_dir(self) -> Path:
        base = Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
        )

        # return Path(base) # returns: .../OutpostPM/OptermX
        return base.parent  # returns: .../OutpostPM


    def _find_bootstrap_file(self) -> Path | None:
        """
        Search for Opx.conf in several supported locations.
        """
        candidates = [
            self.program_dir / "Opx.conf",                  # dev
            self.program_dir / "_internal" / "Opx.conf",    # PyInstaller default
            self.program_dir.parent / "Opx.conf",           # suite root
        ]

        for path in candidates:
            if path.exists():
                return path

        return None


    def _ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.bspecs_dir.mkdir(parents=True, exist_ok=True)
        self.sounds_dir.mkdir(parents=True, exist_ok=True)
        self.optermx_dir.mkdir(parents=True, exist_ok=True)


    def _found_dirs(self):
        print(f"AppPaths:")
        print(f"  ProgramDir : {self.program_dir}")
        print(f"  Bootstrap  : {self.bootstrap_file}")
        print(f"  DataDir    : {self.data_dir}")

    @staticmethod
    def app_icon() -> str:
        # windows
        if sys.platform.startswith("win"):
            return AppPaths.resource_path("polar3232.ico")

        # macOS
        if sys.platform == "darwin":
            return AppPaths.resource_path("polar3232.icns")

        # linux
        return AppPaths.resource_path("polar3232.png")


    @staticmethod
    def resource_path(relative_path: str) -> str:
        """
        Return the absolute path to a bundled resource.

        Works in:
        - development
        - PyInstaller one-folder
        - PyInstaller one-file
        """

        if getattr(sys, "frozen", False):
            base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        else:
            base_dir = Path(__file__).resolve().parents[1]

        return str(base_dir / relative_path)

    