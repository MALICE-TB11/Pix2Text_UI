@echo off
setlocal EnableDelayedExpansion
title Pix2Text UI

rem ============================================================
rem  Pix2Text formula UI - one-click launcher
rem  First run : creates a private Python environment next to this
rem              file, installs everything, then starts the UI.
rem  Next runs : just starts the UI.
rem  p2t_ui.py is located automatically (see below).
rem ============================================================

set "HERE=%~dp0"
set "VENV=%HERE%p2t_env"
set "PY=%VENV%\Scripts\python.exe"

rem 0 = CPU PyTorch (small download, works on any PC, recommended)
rem 1 = CUDA 12.8 PyTorch (about 3 GB, NVIDIA GPU only)
set "USE_GPU=0"

rem Slow downloads? Remove "rem " at the start of the lines below to use mirrors.
rem set "PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple"
rem set "HF_ENDPOINT=https://hf-mirror.com"

rem ---------- locate p2t_ui.py ----------
set "SCRIPT="
for %%D in ("%~dp0." "%CD%" "%USERPROFILE%\Desktop" "%USERPROFILE%\Downloads" "%USERPROFILE%\Documents") do (
    if not defined SCRIPT if exist "%%~D\p2t_ui.py" set "SCRIPT=%%~D\p2t_ui.py"
)
if not defined SCRIPT (
    echo Searching for p2t_ui.py ...
    for %%D in ("%USERPROFILE%\Desktop" "%USERPROFILE%\Downloads" "%USERPROFILE%\Documents") do (
        if not defined SCRIPT (
            for /f "delims=" %%F in ('dir /s /b "%%~D\p2t_ui.py" 2^>nul') do (
                if not defined SCRIPT set "SCRIPT=%%F"
            )
        )
    )
)
if not defined SCRIPT goto noscript
echo Using: !SCRIPT!

rem ---------- already installed? ----------
if exist "%PY%" (
    "%PY%" -c "from pix2text import Pix2Text" >nul 2>&1
    if !errorlevel! equ 0 goto run
    echo Existing environment is incomplete. Repairing it...
)

:install
echo.
echo ===== First-time setup =====
echo Needs internet. Download is about 1-3 GB, takes 5-15 minutes.
echo Do not close this window.
echo.

rem Preferred order: 3.12 3.11 3.10 3.9, then 3.13 as the last choice.
set "BASEPY="
for %%V in (3.12 3.11 3.10 3.9 3.13) do (
    if not defined BASEPY (
        py -%%V -c "import sys" >nul 2>&1
        if !errorlevel! equ 0 set "BASEPY=py -%%V"
    )
)
if not defined BASEPY (
    python -c "import sys; sys.exit(0 if (3,9) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>&1
    if !errorlevel! equ 0 set "BASEPY=python"
)
if not defined BASEPY goto nopython
echo Using Python: !BASEPY!

if not exist "%PY%" (
    echo Creating private environment...
    !BASEPY! -m venv "%VENV%"
    if !errorlevel! neq 0 goto fail
)

echo.
echo [1/3] Installing PyTorch...
if "%USE_GPU%"=="1" (
    "%PY%" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 --disable-pip-version-check
) else (
    "%PY%" -m pip install torch torchvision --disable-pip-version-check
)
if !errorlevel! neq 0 goto fail

echo.
echo [2/3] Installing Pix2Text...
"%PY%" -m pip install pix2text --disable-pip-version-check
if !errorlevel! neq 0 goto fail

echo.
echo [3/3] Checking dependency compatibility...
"%PY%" -c "from pix2text import Pix2Text" >nul 2>&1
if !errorlevel! equ 0 goto run

echo Default rapidocr version is not compatible. Trying other versions one by one...
set "OKV="
for %%V in (3.10.0 3.9.2 3.9.1 3.9.0 3.8.4 3.8.3 3.8.1 3.8.0 3.7.0 3.6.0 3.5.0 3.4.5 3.4.3 3.4.2 3.4.1 3.4.0 3.3.1 3.3.0 3.2.0 3.1.1 3.1.0 3.0.0) do (
    if not defined OKV (
        echo   trying rapidocr %%V
        "%PY%" -m pip install "rapidocr==%%V" -q --disable-pip-version-check >nul 2>&1
        "%PY%" -c "from pix2text import Pix2Text" >nul 2>&1
        if !errorlevel! equ 0 set "OKV=%%V"
    )
)
if not defined OKV goto fail
echo Compatible rapidocr version: !OKV!

:run
echo.
echo Starting Pix2Text UI. The browser will open automatically.
echo First start downloads the models and can take a few minutes.
echo Close this window or press Ctrl+C to stop.
echo.
"%PY%" "!SCRIPT!"
echo.
echo Server stopped.
pause
exit /b 0

:noscript
echo.
echo [ERROR] p2t_ui.py not found.
echo Put p2t_ui.py in the same folder as this file.
echo If you opened this file from inside a zip, extract the zip first.
pause
exit /b 1

:nopython
echo.
echo [ERROR] No suitable Python found. Pix2Text needs Python 3.9 to 3.13, 3.12 recommended.
echo Install Python 3.12 from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" in the installer, then run this file again.
pause
exit /b 1

:fail
echo.
echo [ERROR] Setup failed. Scroll up to see the error message.
echo Common fixes: check your network, or enable the mirror lines at the top of this file.
pause
exit /b 1
