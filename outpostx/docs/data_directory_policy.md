# OutpostX Data Directory Policy

**Version:** 2.0\
**Status:** Draft\
**Applies To:** OutpostX, OpTermX, and future Outpost Suite applications

---

# 1. Purpose

This document defines how Outpost Suite applications locate, organize, and access files.

The goals are:

* Provide a consistent file location strategy across all Outpost Suite applications.
* Support Windows, Linux, and macOS.
* Separate application binaries from user data.
* Support PyInstaller deployment and development environments.
* Allow portable or administrator-controlled data locations.
* Minimize platform-specific code.
* Provide a common storage model for future applications.

---

# 2. Design Principles

Outpost Suite separates files into four categories:

| Category                | Purpose                                | Writable |
| ----------------------- | -------------------------------------- | -------- |
| Program Files           | Executables and source modules         | No       |
| Resources               | Icons, sounds, bundled assets          | No       |
| Bootstrap Configuration | Startup configuration and pointers     | Rarely   |
| Application Data        | Databases, logs, exports, user content | Yes      |

A key design rule is:

> Application data must never be written into the Program Directory.

---

# 3. Program Directory

The Program Directory contains the executable and application code.

Examples:

### Windows

```text
C:\Program Files\OutpostX
```

### Linux

```text
/home/<user>/Applications/OutpostX
/opt/outpostx                           # only if installer/admin puts it here
```
### MacOS

```text
/Applications/OutpostX.app
~/Applications/OutpostX.app             # or for manual/dev use
```

### Development

```text
C:\Dev\OutpostX
```

Typical contents:

```text
OutpostX.exe
Opx.conf
polar3232.ico

data/
├── bbs_specs/
└── sounds/
```

Program files should be considered read-only during normal operation.

---

# 4. Resource Directory

Resources are files distributed with the application.

Examples include:

* Icons
* Images
* Sounds
* Templates
* Default configuration files
* Help files

Resources are loaded through:

```python
AppPaths.resource_path(...)
```

Resources may reside:

* In the source tree
* Beside the executable
* In a PyInstaller bundle
* In a PyInstaller one-file temporary extraction directory

Applications should treat resources as read-only.

---

### 4.1 Bundled Resource Data

Certain files ship with the application and are used to initialize the writable Data Directory.

These files are bundled with the application and treated as read-only.

Example:

```text
Program Directory
│
└── data
    ├── bbs_specs
    │   ├── jnos_spec.json
    │   ├── bpq_spec.json
    │   ├── wl2k_spec.json
    │   └── ...
    │
    └── sounds
        ├── ding.wav
        ├── notify.wav
        └── ...
```

On startup, OutpostX may copy these files into the writable Data Directory if the destination files do not already exist.

Existing user files are never overwritten.

This process is known as **Data Directory Seeding**.

---

# 5. Bootstrap Configuration File

## Purpose

The bootstrap file provides optional startup information before the application can access its normal data directory.

Its primary purpose is to identify the location of the writable Data Directory.

### Filename

```text
Opx.conf
```

---

## Example

```ini
[DataDirectory]
DataDir=C:\Packet Data\OutpostX
```

---

## Search Order

Applications search for the bootstrap file in the following order:

### 1. Program Directory

```text
OutpostX\Opx.conf
```

### 2. PyInstaller Internal Directory

```text
OutpostX\_internal\Opx.conf
```

### 3. Suite Root Directory

```text
..\Opx.conf
```

The first matching file is used.

If no bootstrap file is found, platform defaults are used.

---

# 6. Data Directory

The Data Directory is the root location for all writable application data.
The platform default depends on Qt organization/application identity.

Examples:

### User-selected

```text
D:\Packet Data\OutpostX
```

### Platform Default (Windows)

```text
C:\Users\<user>\AppData\Local\OutpostPM\OutpostX
```

### Platform Default (Linux)

```text
~/.local/share/OutpostPM/OutpostX
```

### Platform Default (macOS)

```text
~/Library/Application Support/OutpostPM/OutpostX
```

---

# 7. Application Startup Resolution

At application startup, Outpost Suite applications determine the location of their writable Data Directory using the following process:

```text
Application Start
        |
        v
Locate Program Directory
        |
        v
Locate Bootstrap File (Opx.conf)
        |
        v
Read DataDirectory/DataDir
        |
        +---- Found? ---- Yes ---> Use configured location
        |                     |
        |                     v
        |               Create if needed
        |
        +---- No -----------------> Use platform default
                                    |
                                    v
                                Create if needed
                                    |
                                    v
                            Create standard subdirectories
                                    |
                                    v
                             Seed bundled data files
                           (bbs_specs and sounds)
                                    |
                                    v
                              Application runs
```

---

# 8. Data Directory Resolution

Applications determine the Data Directory using the following process:

```text
Locate Program Directory
        |
        v
Locate Opx.conf
        |
        +-- Found? -- Yes --> Read DataDirectory/DataDir
        |                       |
        |                       v
        |                 Use configured path
        |
        +-- No ------------------------------+
                                             |
                                             v
                              Use platform default location
                                             |
                                             v
                                Create directory if needed
```

---

# 9. Standard Data Directory Structure

The following structure is used by Outpost Suite applications:

```text
<DataDir>
│
├── logs/
├── docs/
├── bbs_specs/
├── sounds/
│
├── outpostx.db
├── optermx_mrc.json
│
└── application-specific files
```

### logs/

Stores:

* Send/Receive session logs
* Session transcripts
* Diagnostic logs
* Future troubleshooting information

### docs/

Stores:

* Exported documents
* Generated forms
* User-created exports
* Future report output

**NOTE:**  Project .md files are in the project/source tree, not the runtime Data Directory.

### bbs_specs/

Stores:

* User-editable BBS specification files
* JSON protocol definitions
* Customized parser specifications

These files are initially copied from the bundled application resources during first-run initialization.

### sounds/

Stores:

* Notification sounds
* User-selected sound files
* Application audio assets

These files are initially copied from the bundled application resources during first-run initialization.

---

# 10. Directory Ownership

## Program Directory

Owned by:

* Installer
* Developer
* System Administrator

Applications will not write files here.

---

## Data Directory

Owned by:

* User
* Application

Applications may create, modify, and delete files within this directory.

---

# 11. AppPaths Responsibilities

The AppPaths service provides a single source of truth for:

* Program Directory
* Bootstrap File Location
* Data Directory
* Standard Subdirectories
* Database Paths
* Resource Resolution

Applications should use AppPaths rather than hard-coded filesystem paths.

---

# 12. Future Expansion

Future Outpost Suite applications should follow this same model.

Examples:

* OutpostX
* OpTermX
* OpxScripts
* Opx Session Manager

Each application may maintain its own files beneath the common Data Directory while sharing the same bootstrap mechanism.

---

# 13. Summary

```text
Program Directory
│
├── Opx.conf
├── polar3232.ico
│
└── data
    ├── bbs_specs
    └── sounds
            |
            v
      Data Directory
            |
            +-- outpostx.db
            +-- logs/
            +-- docs/
            +-- bbs_specs/
            +-- sounds/
```

### Development Data Directory Structure

```text
C:\Dev\outpostx\
├── data\
│   ├── bbs_specs\
│   └── sounds\
├── services\
├── ui\
├── Opx.conf
└── polar3232.ico
```

### PyInstaller bundle Data Directory Structure

```text
OutpostX\
├── OutpostX.exe
├── Opx.conf
├── polar3232.ico
└── _internal\
    └── data\
        ├── bbs_specs\
        └── sounds\
```

### First Run Data Directory Structure

```text
<DataDir>\
├── outpostx.db
├── bbs_specs\
├── sounds\
├── logs\
└── docs\
```

This architecture provides:

* Cross-platform compatibility
* User-controlled data locations
* Installer independence
* Clean separation of code and data
* Consistent application behavior
* A common foundation for future Outpost Suite applications
