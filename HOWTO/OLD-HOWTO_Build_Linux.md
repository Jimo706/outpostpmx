-------------------------------------
HOWTO-CREATE-Outpostx-Linux-Deliverable.txt
14 June 2026
-------------------------------------

Naming convention:
outpostx-linux-x86_64.tar.gz      # Intel/AMD Linux PCs
outpostx-linux-arm64.tar.gz       # Raspberry Pi 4/5 64-bit OS

There are several steps in creating the OutpostX executable.

1. Create (Pack) the Outpost Source 
2. Unpack Outpost Source 
3. Build the Linux Virtual Environment (venv)
4. Build the Linux Executable file
5. Digitally sign the program -- NOTHING TO DO
6. Build the Distribution file
7. Receive and install the program

--------------------------
1. Create (Pack) the Outpost Source on dev't
--------------------------
This step is common for windows, Linux, and macOS.

1. Verify the program is complete and works on the development system

2. Find or create the he file 'create_outpostpmx_src_7zip.bat'

3. cd /dev

4. From File manager, double-click on the file 'create_outpostx_src_7zip.bat' 

5. Verify that these files were created
	outpostx_archive.zip
	outpostx_archive.log
   As of 13 June 2026, the outpost_archive.zip has 111 files, 12 folders.

--------------------------
2. Unpack Outpost Source on linux
--------------------------
1. # maintains the original folder structure
   cd dev
   $ mkdir outpostpmx
   $ cd dev/outpostpmx

2. Copy the outpostpmx_src_archive.zip to the dev/outpostpmx directory

3. Run to unpack the source code.
   $ 7z x outpostx_archive.zip	

--------------------------
3. Build the Linux Virtual Environment (venv)
--------------------------

1. create the venv environment
	$ cd ..\dev\outpostpmx
	$ python3 -m venv ./venv
	$
2. VERIFY: an 'ls -al' should now include a venv directory.

3. Activate the environment
	$ source venv/bin/activate
	(venv) $

4. Install or upgrade Pip.  Once done, running pip 25.1.1 from /usr/lib/python3/dist-packages/pip (python 3.12)
	(venv) $ python -m pip install --upgrade pip
	(venv) $ pip --version
	pip 26.1.2 from /home/jimo/dev/outpostx/venv/lib/python3.12/site-packages/pip (python 3.12)

5. Add the pyside6 tools
	(venv) $ pip install pyside6

6. Install pyserial
	(venv) $ pip install pyserial

7. Install paramiko
	(venv) $ pip install paramiko

8. Install pyinstaller..
	(venv) $ pip install pyinstaller

9. Test:
	(venv) $ python3 outpostx.py
	(venv) $ python --version		returns: 3.12.3
	(venv) $ pip --version			returns: 26.1.2
	(venv) $ pyinstaller --version		returns: 6.21.0
    if any fail, fix	

10. Build the Linux venv requirements file
	(venv) $ pip freeze > requirements_linux.txt

11. Run OutpostX
	(venv) $ cd dev/outpostpmx
	(venv) $ python3 outpostx/outpostx.py


--------------------------
4. Build the Linux Executable file
--------------------------

1. Activate the virtual environment if not already activated
	cd: \dev\outpostpmx
	venv\Scripts\activate
	(venv) $

2. Build the executable
	python3 -m PyInstaller -y --clean outpostpmx_linux.spec

    VERIFY:
	cd dist/outpostpmx
	(venv) jimo@dell02:~/dev/outpostpmx/dist/outpostpmx$ ls -al
	total 3560
	drwxrwxr-x  3 jimo jimo    4096 Jun 13 10:12 .
	drwxrwxr-x  3 jimo jimo    4096 Jun 13 10:12 ..
	drwxrwxr-x 12 jimo jimo   12288 Jun 13 10:12 _internal
	-rwxr-xr-x  1 jimo jimo 3623040 Jun 13 10:12 optermx
	-rwxr-xr-x  1 jimo jimo 3623040 Jun 13 10:12 outpostx


--------------------------
5. Digitally sign the program
--------------------------
nothing to do for Linux

--------------------------
6. Build the Distribution file -- linux
--------------------------

1. start at the appropriate position:
cd ~/dev/outpostpmx

2. make a release folder
mkdir -p release

3. package the PyInstaller onedir output
cd dist
tar -czf ./release/outpostpmx-linux-x86_64.tar.gz outpostpmx

This creates the file 'outpostpmx-linux-x86_64.tar.zip' in the 'release' directory 

--------------------------
7. Receive and install the program
--------------------------

1. set up a download directory: ./outpostx


2. download the Linux outpostx file here.  then:
	tar -xzf outpostx-linux-x86_64.tar.gz
	cd outpostpmx
	./outpostpmx

