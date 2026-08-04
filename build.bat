@echo off
setlocal EnableExtensions

title PS2 Classics GUI - Mod by Chrisser - Builder
cd /d "%~dp0"

set "ROOT=%~dp0"
set "SOURCE_FILE=%ROOT%ps2_classics_gui_mod.py"
set "ICON_FILE=%ROOT%app.ico"
set "PNG_ICON_FILE=%ROOT%app.png"
set "DIST_DIR=%ROOT%_build"
set "INTERNAL_NAME=PS2ClassicsGUIMod"

echo.
echo ============================================================
echo  PS2 Classics GUI - Mod by Chrisser - Builder
echo ============================================================
echo.

if not exist "%SOURCE_FILE%" (
    echo [ERROR] ps2_classics_gui_mod.py was not found.
    echo The build.bat must be in the same project root folder.
    goto :failed
)

if not exist "%ICON_FILE%" (
    echo [ERROR] app.ico was not found.
    echo Add app.ico to the project root before building.
    goto :failed
)

if not exist "%PNG_ICON_FILE%" (
    echo [ERROR] app.png was not found.
    echo Add app.png to the project root before building.
    goto :failed
)

set "PYTHON_CMD="

py -3 -c "import sys; raise SystemExit(0 if sys.version_info.major == 3 else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
    python -c "import sys; raise SystemExit(0 if sys.version_info.major == 3 else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo [ERROR] Python 3 was not found.
    echo Install Python 3 and enable "Add Python to PATH".
    echo https://www.python.org/downloads/
    goto :failed
)

echo [OK] Python 3:
%PYTHON_CMD% --version
echo.

%PYTHON_CMD% -m pip --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] pip was not found.
    echo Try:
    echo %PYTHON_CMD% -m ensurepip --upgrade
    goto :failed
)

echo [OK] pip:
%PYTHON_CMD% -m pip --version
echo.

%PYTHON_CMD% -c "import tkinter, _tkinter; print('Tk', tkinter.TkVersion, '- Tcl', tkinter.TclVersion)" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Tkinter or the Tcl/Tk runtime is not available.
    echo.
    echo Install the standard Python 3 distribution from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure the Tcl/Tk and IDLE component is enabled
    echo in the Python installer.
    goto :failed
)

echo [OK] Tkinter and Tcl/Tk found:
%PYTHON_CMD% -c "import tkinter; print('Tk', tkinter.TkVersion, '- Tcl', tkinter.TclVersion)"
echo.

%PYTHON_CMD% -c "from PIL import Image" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Pillow is not installed.
    echo Install it with:
    echo %PYTHON_CMD% -m pip install --upgrade Pillow
    goto :failed
)

echo [OK] Pillow found.
echo.

%PYTHON_CMD% -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] PyInstaller is not installed.
    echo Install it with:
    echo %PYTHON_CMD% -m pip install --upgrade PyInstaller
    goto :failed
)

echo [OK] PyInstaller:
%PYTHON_CMD% -m PyInstaller --version
echo.

set "VERSION="
for /f "tokens=2 delims==" %%V in ('findstr /c:"APP_VERSION" "%SOURCE_FILE%"') do (
    if not defined VERSION set "VERSION=%%V"
)

set "VERSION=%VERSION: =%"
set "VERSION=%VERSION:"=%"

if not defined VERSION (
    echo [ERROR] APP_VERSION could not be read from ps2_classics_gui_mod.py.
    goto :failed
)

set "FINAL_EXE=PS2 Classics GUI - Mod by Chrisser v%VERSION%.exe"

echo Application version: %VERSION%
echo Output filename: %FINAL_EXE%
echo.

set "TEMP_ROOT=%TEMP%\PS2ClassicsGUIMod_Build_%RANDOM%_%RANDOM%"
set "WORK_DIR=%TEMP_ROOT%\work"
set "SPEC_DIR=%TEMP_ROOT%\spec"

mkdir "%WORK_DIR%" >nul 2>nul
mkdir "%SPEC_DIR%" >nul 2>nul

if not exist "%WORK_DIR%" (
    echo [ERROR] The temporary build directory could not be created.
    goto :failed
)

if exist "%DIST_DIR%" (
    echo Removing the previous _build folder...
    call :remove_directory "%DIST_DIR%"
)

if exist "%DIST_DIR%" (
    echo [ERROR] The previous _build folder could not be removed.
    echo Close the old EXE and any Explorer window using:
    echo %DIST_DIR%
    call :remove_directory "%TEMP_ROOT%"
    goto :failed
)

mkdir "%DIST_DIR%" >nul 2>nul

if not exist "%DIST_DIR%" (
    echo [ERROR] The _build output folder could not be created.
    call :remove_directory "%TEMP_ROOT%"
    goto :failed
)

echo.
echo ============================================================
echo  Building production EXE
echo ============================================================
echo.

%PYTHON_CMD% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "%INTERNAL_NAME%" ^
    --icon "%ICON_FILE%" ^
    --add-data "%ICON_FILE%;." ^
    --add-data "%PNG_ICON_FILE%;." ^
    --distpath "%DIST_DIR%" ^
    --workpath "%WORK_DIR%" ^
    --specpath "%SPEC_DIR%" ^
    "%SOURCE_FILE%"

set "BUILD_RESULT=%ERRORLEVEL%"

if not "%BUILD_RESULT%"=="0" (
    echo.
    echo [ERROR] PyInstaller build failed with error code %BUILD_RESULT%.
    call :remove_directory "%TEMP_ROOT%"
    goto :failed
)

if not exist "%DIST_DIR%\%INTERNAL_NAME%.exe" (
    echo [ERROR] The generated EXE was not found.
    call :remove_directory "%TEMP_ROOT%"
    goto :failed
)

move /y "%DIST_DIR%\%INTERNAL_NAME%.exe" "%DIST_DIR%\%FINAL_EXE%" >nul

if errorlevel 1 (
    echo [ERROR] The generated EXE could not be renamed.
    call :remove_directory "%TEMP_ROOT%"
    goto :failed
)

echo Cleaning temporary build files...
call :remove_directory "%TEMP_ROOT%"

echo.
echo ============================================================
echo  BUILD SUCCESSFUL
echo ============================================================
echo.
echo Created:
echo "%DIST_DIR%\%FINAL_EXE%"
echo.
pause
exit /b 0

:remove_directory
set "CLEAN_TARGET=%~1"
if not exist "%CLEAN_TARGET%" exit /b 0

for /L %%R in (1,1,5) do (
    rmdir /s /q "%CLEAN_TARGET%" >nul 2>nul
    if not exist "%CLEAN_TARGET%" exit /b 0
    timeout /t 1 /nobreak >nul
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Remove-Item -LiteralPath $env:CLEAN_TARGET -Recurse -Force -ErrorAction SilentlyContinue" >nul 2>nul
exit /b 0

:failed
echo.
echo ============================================================
echo  BUILD FAILED
echo ============================================================
echo.
pause
exit /b 1
