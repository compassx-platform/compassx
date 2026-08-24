@echo off
rem CompassX platform CLI wrapper (Windows).
setlocal
cd /d "%~dp0backend"
if defined BACKEND_VENV_PATH (
    if exist "%BACKEND_VENV_PATH%\Scripts\python.exe" (
        set "PY=%BACKEND_VENV_PATH%\Scripts\python.exe"
        goto :run
    )
)
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)
:run
"%PY%" -m compassx.cli.main %*
endlocal
