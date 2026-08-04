@echo off
setlocal EnableExtensions

title PS2 Classics GUI - Mod by Chrisser
cd /d "%~dp0"

set "SCRIPT=%~dp0ps2_classics_gui_mod.py"

if not exist "%SCRIPT%" (
    echo [ERROR] ps2_classics_gui_mod.py was not found.
    echo The start.bat must be in the same project root folder.
    pause
    exit /b 1
)

where pyw.exe >nul 2>nul
if not errorlevel 1 (
    start "" pyw.exe -3 "%SCRIPT%"
    exit /b 0
)

where pythonw.exe >nul 2>nul
if not errorlevel 1 (
    start "" pythonw.exe "%SCRIPT%"
    exit /b 0
)

echo [ERROR] Python 3 with pythonw/pyw was not found.
echo Install Python 3 and enable "Add Python to PATH".
echo https://www.python.org/downloads/
pause
exit /b 1
