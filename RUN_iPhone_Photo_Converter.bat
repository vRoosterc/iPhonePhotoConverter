@echo off
title iPhone Photo Converter - One-Click Launcher
echo ================================================================
echo  iPhone Photo Converter - Starting Application...
echo ================================================================
echo.

REM Function to check if Python is available
:check_python
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        goto install_python
    ) else (
        set PYTHON_CMD=py
        goto python_found
    )
) else (
    set PYTHON_CMD=python
    goto python_found
)

:install_python
echo Python is not installed or not in PATH.
echo.
choice /C YN /M "Would you like to download and install Python automatically"
if errorlevel 2 goto manual_install
if errorlevel 1 goto auto_install

:auto_install
echo.
echo Downloading Python installer...
echo This may take a few minutes...
echo.

REM Create temp directory
set TEMP_DIR=%TEMP%\python_installer_%RANDOM%
mkdir "%TEMP_DIR%"

REM Download Python installer using PowerShell
powershell -Command "& {try { Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.7/python-3.11.7-amd64.exe' -OutFile '%TEMP_DIR%\python_installer.exe'; Write-Host 'Download completed successfully!' } catch { Write-Host 'Download failed:' $_.Exception.Message; exit 1 }}"
if errorlevel 1 (
    echo Download failed. Please install Python manually.
    goto manual_install
)

echo.
echo Installing Python...
echo Please wait, this may take several minutes...
echo.

REM Run installer silently
"%TEMP_DIR%\python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_tcltk=1

REM Wait a bit for installation to complete
timeout /t 10 /nobreak >nul

REM Clean up
rmdir /s /q "%TEMP_DIR%" >nul 2>&1

echo.
echo Python installation completed!
echo Refreshing environment variables...
echo.

REM Refresh PATH without restarting
call :refresh_env

REM Check if Python is now available
goto check_python

:manual_install
echo.
echo Please install Python manually:
echo 1. Visit: https://www.python.org/downloads/
echo 2. Download Python 3.11 or newer
echo 3. During installation, make sure to check "Add Python to PATH"
echo 4. After installation, run this launcher again
echo.
start https://www.python.org/downloads/
pause
exit /b 1

:python_found
echo Python found: %PYTHON_CMD%
echo.

REM Run the launcher
%PYTHON_CMD% "RUN_iPhone_Photo_Converter.py"

REM Keep window open if there was an error
if errorlevel 1 (
    echo.
    echo The application encountered an error.
    pause
)
goto :eof

:refresh_env
REM Refresh environment variables by reading from registry
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USER_PATH=%%B"
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "SYS_PATH=%%B"
set "PATH=%SYS_PATH%;%USER_PATH%"
goto :eof 