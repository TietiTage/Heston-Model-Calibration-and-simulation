@echo off
rem ============================================================
rem  Unified local docs entry for Heston-Model-Calibration.
rem  1) Build the MkDocs site (docs/ -> site/)
rem  2) Open the unified entry page (index.html) in browser
rem
rem  If data_process env is not at the path below, edit PYTHON.
rem ============================================================
setlocal
set "PYTHON=E:\Anaconda\envs\data_process\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] data_process environment not found: %PYTHON%
    echo Edit the PYTHON variable in start_docs.bat to point to your environment.
    pause
    exit /b 1
)

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
