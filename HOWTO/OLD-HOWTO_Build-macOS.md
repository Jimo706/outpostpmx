-------------------------------------
HOWTO-CREATE-Outpostx-macOS-Deliverable.txt
14 June 2026
-------------------------------------

Naming convention:
outpostx-windows-x86_64.zip
outpostx-linux-x86_64.tar.gz      # Intel/AMD Linux PCs
outpostx-linux-arm64.tar.gz       # Raspberry Pi 4/5 64-bit OS
outpostx-macos-x86_64.zip

There are several steps in creating the OutpostX executable.

1. Create (Pack) the Outpost Source 
2. Unpack Outpost Source 
3. Build the macOS Virtual Environment (venv)
4. Build the macOS Executable file
5. Digitally sign the program -- NOTHING TO DO
6. Build the macOS Distribution file
7. Receive and install the program

--------------------------
1. Create (Pack) the Outpost Source on dev't
--------------------------
This step is common for windows, Linux, and macOS.

1. Verify the program is complete and works on the development system

2. Find or create the he file 'create_outpostx_src_7zip.bat'

3. cd /dev

4. From File manager, double-click on the file 'create_outpostx_src_7zip.bat' 

5. Verify that these files were created
	outpostx_archive.zip
	outpostx_archive.log
   As of 13 June 2026, the outpost_archive.zip has 111 files, 12 folders.

--------------------------
2. Unpack Outpost Source on macOS
--------------------------
1. create the source folder structure
   cd dev
   mkdir outpostx
   cd dev/outpostx

2. Copy the outpostx_archive.zip to the dev/outpostx directory
3. From the terminal program.
   	ls /Volumes		I should see Macintosh HD, USBDRIVE

4. Verify the zip file is there...
	ls /Volumes/USBDRIVE (or OUTPOSTX)		

3. Copy it into your development directory
	cp /Volumes/USBDRIVE/outpost_archive.zip ~/dev/outpostx/

4. Verify the copy
	ls ~/dev/outpostx

5. Move to the dev directory
	cd ~/dev/outpostx

6. Run to unpack the source code.
   	unzip outpost_archive.zip	

--------------------------
3. Build the macOS Virtual Environment (venv)
--------------------------
Need python@3.12 version installed.

1. Make sure...
   	cd ~/dev/outpostx
   	deactivate 2>/dev/null
   	rm -rf venv

2. Install Python with Homebrew (THIS WILL TAKE A WHILE):
   	brew install python@3.12
	 Python is installed as:
	 /usr/local/bin/python3.12

	It then says that all unversioned and major-versioned symlinks 'python', 'python3',  
	 'pip', 'pip3' etc are 	pointing to 'python3.12' and pip3.12 

3. create the venv using Homebrew Python:
	python3.12 -m venv venv
	source venv/bin/activate
	(venv)python3 --version
	   Python 3.12.13
	(venv)python -m pip install --upgrade pip setuptools wheel
	(venv) $ pip install --upgrade pip	
	Successfully uninstalled pip-24.0
	Successfully installed pip-26.1.2
	(venv) $ pip --version
	pip 26.0.1 from /Users/jimo/dev/outpostx/venv/lib/python3.9/site-packages/pip (python 3.9)

4. Install pyserial… 
	python -m pip install PySide6
	verify:  
	  python -c "import PySide6; print(PySide6.__version__)"
	  6.9.3

5. Install pyserial… 
	(venv) $ python -m pip install pyserial
	verify:
 	  python -c "import serial; print(serial.__version__)"... replies with 3.6

6. Install paramiko..
	(venv) $ python -m pip install paramiko
	verify:
 	  python -c "import paramiko; print(paramiko.__version__)"... replies with 5.0.0

7. Install pyinstaller..
	(venv) $ python -m pip install pyinstaller
	verify:
 	  pyinstaller --version... replies with 6.21.0

8. Test VENV
	# python3 outpostx.py

9. Test:
	(venv) $ python3 outpostx.py
	(venv) $ python --version		returns: 3.12.3
	(venv) $ pip --version			returns: 26.1.2
	(venv) $ pyinstaller --version		returns: 6.21.0
    if any fail, fix	

10. Build the macOS venv requirements file
	(venv) $ pip freeze > requirements_macos.txt
	Move to the ~/dev directory so you don't loose it for the next time:
	NEXT TIME:  pip install -r requirements_macos.txt

--------------------------
4. Build the macOS Executable file
--------------------------

1. Activate the virtual environment if not already activated
	cd: \dev\outpostx
	venv\Scripts\activate
	(venv) C:\Dev\outpostx>

2. Build the executable
	python3 -m PyInstaller --clean --noconfirm outpostx_macos.spec

--------------------------
5. Digitally sign the program
--------------------------
PENDING for macOS

--------------------------
6. Build the Distribution file -- linux
--------------------------

1. start at the appropriate position:
cd ~/dev/outpostx
mkdir -p release

ditto -c -k --sequesterRsrc --keepParent \
    dist/OutpostX.app \
    release/outpostx-macos-x86_64.zip

This creates the file 'outpostx-macos-x86_64.zip' in the 'release' directory 

--------------------------
7. Receive and install the program
--------------------------

1. set up a download directory: ./outpostx


2. download the Linux outpostx file here.  then:
	tar -xzf outpostx-linux-x86_64.tar.gz
	cd outpostx
	./outpostx

