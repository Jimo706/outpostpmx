# OutpostPMX Installation Guide

**Version:** 2026.07.0 Beta 1

---

# Welcome

Thank you for downloading the OutpostPMX Suite.

OutpostPMX is a modern, cross-platform Packet Message Manager designed for Amateur Radio packet operators. It is the successor to the original Outpost Packet Message Manager and has been redesigned to operate on Windows, Linux, and macOS using a common source code base.

This guide explains how to install OutpostPMX for the first time and verify that the installation completed successfully.

---

# Who Should Read This Guide

This guide is intended for operators who are installing OutpostPMX for the first time.

No previous experience with Outpost or OutpostPMX is assumed.

---

# System Requirements

## Supported Operating Systems

* Microsoft Windows 11
* Ubuntu Linux 24.04 LTS (or compatible)
* Raspberry Pi OS (64-bit)
* macOS Sequoia (Intel)

Future releases may support additional operating systems.

---

## Hardware Requirements

OutpostPMX has modest hardware requirements.

Recommended:

* 64-bit processor
* 4 GB RAM or more
* 250 MB available disk space
* Internet connection (for updates and TELNET operation)

---

# Chapter 1 – Downloading OutpostPMX

Visit the official OutpostPMX GitHub Releases page.

Download the package appropriate for your operating system.

| Operating System | Package                                          |
| ---------------- | ------------------------------------------------ |
| Windows          | outpostpmx-windows-x86_64.zip                    |
| Linux            | outpostpmx-linux-x86_64.tar.gz                   |
| Raspberry Pi OS  | outpostpmx-linux-arm64.tar.gz *(when available)* |
| macOS            | outpostpmx-macos-x86_64.zip                      |

---

# Chapter 2 – Installing on Windows

1. Create a directory on your Windows PC where you would like OutpostPMX installed.

   Example:

       C:\MyPrograms

2. Download the current Windows release package from the OutpostPMX GitHub Releases page.

3. Extract the ZIP archive into the directory you created.

   Either right-click on the zip file and select **Extract All**, or use 7z (for 7-Zip):

       7z x outpostpmx-windows-x86_64.zip

4. Verify that the extraction created an OutpostPMX directory similar to:

    ```text
    C:\MyPrograms\
        outpostpmx\
            outpostx
            optermx
            _internal\
    ```

    If it creates a directory named 'outpostpmx-windows-x86_64', rename it to 'outpostpmx'.

5. Open the OutpostPMX directory.

6. Double-click **outpostx.exe** to start OutpostX.

7. (Optional) Create a desktop shortcut by right-clicking **outpostx.exe** and selecting:

       Send to → Desktop (Create shortcut)


No installation program is required.

OutpostPMX is designed as a portable application.

---

# Chapter 3 – Installing on Linux

1. Create a directory where you would like to install OutpostPMX.

   Example:

       mkdir -p ~/MyPrograms

2. Download the current Linux release package from the OutpostPMX GitHub Releases page.

3. Change to the installation directory.

```bash
cd ~/MyPrograms
```

4. Extract the release archive.

Example:

```bash
tar -xzf outpostpmx-linux-x86_64.tar.gz
```

5. Verify that the extraction created a directory similar to:

```text
~/MyPrograms/

    outpostpmx/
        outpostx
        optermx
        _internal/
```

6. Change into the OutpostPMX directory.

```bash
cd outpostpmx
```

7. Ensure the applications have execute permission.

```bash
chmod +x outpostx
chmod +x optermx
```

Normally this step is unnecessary, but it does no harm if repeated.

8. Start OutpostX.

```bash
./outpostx
```

---

# Chapter 4 – Installing on macOS

1. Download the current macOS release package from the OutpostPMX GitHub Releases page.

2. Open your **Downloads** folder and double-click the ZIP archive.

   macOS automatically extracts the archive into a folder named **OutpostPMX**.

3. Move the **OutpostPMX** folder to the location where you would like to keep it.

   Examples:

       Applications

   or

       Documents/Amateur Radio

4. Open the **OutpostPMX** folder.

5. Double-click **OutpostX** to start the application.

### First Launch

The first time OutpostX is started, macOS may display a security warning because the application was downloaded from the Internet and is not yet digitally signed.

If this occurs:

1. Right-click **OutpostX**.
2. Select **Open**.
3. Click **Open** when prompted.

This confirmation is normally required only once.

### Expected Result

The OutpostX main window should appear.

During the first startup, OutpostPMX automatically creates its working data directory within your Home folder.

No additional installation steps are required.

---

# Chapter 5 – First Startup

The first time OutpostPMX starts it automatically creates its working data directory.

This directory stores:

* Configuration information
* Message database
* Logs
* BBS specifications
* Sounds

No user action is normally required.

Each Outpostpmx application has a Display Data Directory menu item under View or Actions.  
Click on this menu item to open a platform-specific file manager form.  Note the path to where the data is located.
Curently, the first time the program runs, it automatically creates the OutpostPMX
data directory within your home directory. 

---

# Chapter 6 – Data Directory Locations

The default data directory depends upon the operating system.

| Platform | Default Location                                 |
| -------- | ------------------------------------------------ |
| Windows  | LocalAppData/OutpostPM/OutpostX                  |
| Linux    | ~/.local/share/OutpostPM/OutpostX                |
| macOS    | ~/Library/Application Support/OutpostPM/OutpostX |

Future versions may allow this location to be customized.

---

# Chapter 7 – Upgrading

To upgrade:

1. Download the newer release.
2. Replace the application directory.
3. Leave the existing data directory unchanged.

Your existing:

* Configuration
* Messages
* Profiles
* Logs
* Message Database

will normally be preserved automatically.

---

# Chapter 8 – Uninstalling

To remove OutpostPMX:

1. Delete the application directory.

Optionally remove the data directory if you no longer wish to retain:

* Messages
* Configuration
* Profiles
* Logs

Deleting the data directory permanently removes all stored OutpostPMX information.

---

# Troubleshooting

If OutpostPMX does not start:

* Verify that the archive extracted correctly.
* Confirm that all application files remain together.
* Verify executable permissions (Linux).
* Verify macOS security settings.
* Consult the Troubleshooting Guide.

---

# Next Steps

Congratulations!

OutpostPMX has now been installed successfully.

The next document to read is:

**OutpostPMX Quick Start Guide**

The Quick Start Guide walks through creating your first Station Profile, connecting to a BBS, downloading messages, and sending your first packet message.

---

# Need Help?

Additional documentation, release notes, and updates are available on the OutpostPMX GitHub project page.

We welcome bug reports, suggestions, and feedback from the Packet Radio community.
