@echo off
setlocal enabledelayedexpansion
title Karaoke Maker Launcher

cd /d "%~dp0"

set "PY_EXE="
if exist "%~dp0python_env\python.exe" (
    set "PY_EXE=%~dp0python_env\python.exe"
    goto :START_APP
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_EXE=python"
    goto :START_APP
)

echo [!] No Python found on this computer.
echo [*] Downloading portable Python (embed)...
mkdir "%~dp0python_env" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile '%~dp0python_env\python.zip'"
if not exist "%~dp0python_env\python.zip" (
    echo [ERROR] Failed to download Python.
    pause
    exit /b 1
)

echo [*] Extracting Python...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%~dp0python_env\python.zip' -DestinationPath '%~dp0python_env' -Force"
del "%~dp0python_env\python.zip" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem '%~dp0python_env\*._pth' | ForEach-Object { Add-Content $_.FullName 'import site' }"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%~dp0python_env\get-pip.py'"
"%~dp0python_env\python.exe" "%~dp0python_env\get-pip.py" --no-warn-script-location
del "%~dp0python_env\get-pip.py" >nul 2>&1
set "PY_EXE=%~dp0python_env\python.exe"

:START_APP
start "" "%PY_EXE%" "%~dp0main.py"
exit
