@echo off
rem ============================================================
rem  Unified local docs entry for Heston-Model-Calibration.
rem  1) Build the MkDocs site (docs/ -> site/)
rem  2) Open the unified entry page (index.html) in browser
rem
rem  Prefers the data_process env; falls back to python on PATH.
rem ============================================================
setlocal
set "PYTHON=python"
if exist "E:\Anaconda\envs\data_process\python.exe" set "PYTHON=E:\Anaconda\envs\data_process\python.exe"

echo Using Python: %PYTHON%
echo [1/2] Building MkDocs site ...
"%PYTHON%" -m mkdocs build
if errorlevel 1 (
    echo [ERROR] mkdocs build failed. Make sure mkdocs and mkdocstrings are installed.
    pause
    exit /b 1
)

echo [2/2] Opening unified docs entry: index.html
start "" "%~dp0index.html"

endlocal
