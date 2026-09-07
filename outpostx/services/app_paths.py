# outpostx: services/app_paths.py

from pathlib import Path
import configparser
import sys
from PySide6.QtCore import QStandardPaths

class AppPaths:
    """
    Resolve all application file-system locations.

    AppPaths separates three concepts:

    1. Program directory
       Where the executable or source tree is running from.

    2. Bootstrap file
       A small config file located beside the program. It may point to the
       writable data directory.

    3. Data directory
       The user-writable location where OutpostX/OpTermX stores runtime data,
       logs, documents, BBS specs, and other generated files.

    The rest of the application should use these resolved paths instead of
    hard-coded directories.
    """
    def __init__(self, app_name):
        self.app_name = app_name
    
        # Directory containing the running program:
        # - PyInstaller build: folder containing the executable
        # - Development run: project/source root
        self.program_dir = self._get_program_dir()

        # Bootstrap config file located next to the program.
        # This file can redirect the writable data directory.
        self.bootstrap_file = self._find_bootstrap_file()

        # Resolve the writable data directory.
        # Resolution policy belongs in _resolve_data_dir().
        self.data_dir = self._resolve_data_dir()

        # Standard subdirectories under the writable data directory.
        self.logs_dir = self.data_dir / "logs"
        self.docs_dir = self.data_dir / "docs"
        self.bspecs_dir = self.data_dir / "bbs_specs"
        self.sounds_dir = self.data_dir / "sounds"
        self.forms_dir = self.data_dir / "forms"        #  #164

        # Create the writable directory tree if needed.
        self._ensure_dirs()

        # Development diagnostic only; remove or guard before release.
        ### self._found_dirs()       # DEBUG ONLY 


    def _get_program_dir(self) -> Path:
        """
        Return the directory containing the running application.

        Runtime behavior:

        - PyInstaller executable:
        Returns the directory containing the bundled executable.

        - Development environment:
        Returns the project root directory.

        This location is used to find program resources that ship with the
        application, including the bootstrap configuration file (Opx.conf).

        Note:
        This is NOT the writable data directory. User data, logs, databases,
        and generated files belong under the resolved data directory.
        """
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent

        return Path(__file__).resolve().parents[1]


    def _resolve_data_dir(self) -> Path:
        """
        Resolve the writable application data directory.

        Resolution order:

        1. Bootstrap override
        If Opx.conf contains a [DataDirectory] section with a
        DataDir entry, use that location.

        2. Platform default
        If no bootstrap override is defined, use the platform-
        appropriate default returned by _default_data_dir().

        The returned directory becomes the root of all user-writable
        application data, including:

        - databases
        - logs
        - documents
        - BBS specifications
        - exported files
        - future application-generated content

        Notes:
        - The bootstrap file acts only as a pointer to the data directory.
        - Application data should never be written into the program directory.
        - The directory itself is created later by _ensure_dirs().
        """
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
        """
        Return the platform-default writable data directory.

        This location is used only when no DataDir override is found
        in the bootstrap configuration file.

        The path is obtained from Qt's AppDataLocation so that each
        operating system uses its native application-data convention.

        Typical examples:

        Windows:
            C:\\Users\\<user>\\AppData\\Local\\<Application>

        Linux:
            ~/.local/share/<Application>

        macOS:
            ~/Library/Application Support/<Application>

        Notes:
        - Qt determines the actual location.
        - The application should not assume a specific directory structure.
        - The returned path may not yet exist; creation is handled later
        by _ensure_dirs().
        """
        base = Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
        )

        # return Path(base) # returns: .../OutpostPM/OutpostX
        return base.parent  # returns: .../OutpostPM


    def _find_bootstrap_file(self) -> Path | None:
        """
        Locate the OutpostX bootstrap configuration file.

        The bootstrap file (Opx.conf) is a small configuration file that
        provides startup information, most notably the location of the
        writable data directory.

        Search order:

        1. Program directory
        Development builds and simple deployments.

        2. PyInstaller internal directory
        Supports bundled application layouts where resources are stored
        under "_internal".

        3. Suite root directory
        Supports multiple OutpostX applications sharing a common
        bootstrap file.

        Returns:
            Path to the first Opx.conf file found.

            None if no bootstrap file exists.

        Notes:
        - The bootstrap file is optional.
        - If no bootstrap file is found, the application falls back to
        platform-default locations.
        - The first matching file found wins.
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
        """
        Ensure the writable application directory structure exists.

        Creates the data directory and all standard OutpostX
        subdirectories if they do not already exist.

        Standard directories:

        data_dir/
            Root writable application data directory

        logs/
            Session logs, transcripts, diagnostic logs

        docs/
            Exported documents, imported documents,
            generated reports, and user-facing files

        bspecs/
            BBS specification files and protocol definitions

        sounds/
            User-selectable notification sounds and audio assets.
            Applications may ship default sound files during 
            installation or first-run setup, but all operational 
            sound files reside in the Data Directory.

        forms/
            User-installable OutpostX form definitions and associated
            assets such as PDF templates.

        Notes:
        - Safe to call repeatedly.
        - Missing directories are created automatically.
        - Existing directories are left unchanged.
        - Parent directories are created as needed.
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.bspecs_dir.mkdir(parents=True, exist_ok=True)
        self.sounds_dir.mkdir(parents=True, exist_ok=True)
        self.forms_dir.mkdir(parents=True, exist_ok=True)       # #164

    # TODO: DEBUG Only.  Remove when certain it works
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
        Return the absolute path to a bundled application resource.

        Resources are files that ship with the application and are
        considered read-only at runtime.

        Examples:
            - icons
            - images
            - sounds
            - bundled templates
            - default configuration files

        This method automatically resolves the correct resource location
        for the current execution environment:

        - Development:
            Resources are loaded from the source tree.

        - PyInstaller one-folder:
            Resources are loaded from the bundled application directory.

        - PyInstaller one-file:
            Resources are loaded from PyInstaller's temporary extraction
            directory (_MEIPASS).

        Args:
            relative_path:
                Resource path relative to the application resource root.

        Returns:
            Absolute filesystem path to the requested resource.

        Notes:
        - Resources are application assets, not user data.
        - Resources should be treated as read-only.
        - User-created files belong in the data directory, not in the
        resource directory.
        """
        if getattr(sys, "frozen", False):
            base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        else:
            base_dir = Path(__file__).resolve().parents[1]

        return str(base_dir / relative_path)
