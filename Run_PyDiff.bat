@echo off
rem ======================================================================
rem  PyDiff launcher (c) 2026 Constantinos, MIT License - see LICENSE
rem  Double-click to start pydiff (no command window).
rem
rem  - Finds Python on this PC (offers to install it if there is none).
rem  - Checks pydiff's dependencies every run and installs anything
rem    missing; anything already installed is left alone.
rem  - You can drag two files (or two folders) onto this file to open
rem    them straight away in a comparison.
rem ======================================================================
setlocal
cd /d "%~dp0"
title PyDiff launcher

rem ---- 1. find a working Python 3 (skips the Microsoft Store stub) ----
set "PY="
set "PYW="
set "PYWEXE="
py -3 -c "import sys" >nul 2>&1 && (
    set "PY=py -3"
    set "PYW=pyw -3"
    set "PYWEXE=pyw"
)
if not defined PY (
    python -c "import sys; sys.exit(sys.version_info[0] < 3)" >nul 2>&1 && (
        set "PY=python"
        set "PYW=pythonw"
        set "PYWEXE=pythonw"
    )
)
if not defined PY goto :no_python

rem ---- 2. check / install dependencies (fast if all present) ----
%PY% "%~dp0pydiff.py" --check-deps >"%TEMP%\pydiff_deps.log" 2>&1
if errorlevel 1 (
    type "%TEMP%\pydiff_deps.log"
    echo.
    echo PyDiff could not start - see the message above.
    pause
    exit /b 1
)

rem ---- 3. start the GUI without a console window, then close this one ----
where %PYWEXE% >nul 2>&1
if errorlevel 1 (
    start "PyDiff" /min %PY% "%~dp0pydiff.py" %*
) else (
    start "" %PYW% "%~dp0pydiff.py" %*
)
exit /b 0

:no_python
echo Python 3 was not found on this computer.
echo.
where winget >nul 2>&1
if errorlevel 1 goto :manual_python
choice /m "Install Python 3.12 now using winget"
if errorlevel 2 goto :manual_python
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
echo.
echo Python is installed. Close this window and double-click the launcher again.
pause
exit /b 0

:manual_python
echo Please install Python 3 from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH" and keep "tcl/tk and IDLE" selected),
echo then double-click this launcher again.
start "" https://www.python.org/downloads/
pause
exit /b 1
