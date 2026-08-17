@echo off
rem CompassX platform CLI wrapper (Windows).
setlocal
cd /d "%~dp0backend"
if exist ".venv\Scripts\python.exe" (
    set PY=.venv\Scripts\python.exe
) else (
    set PY=python
)
"%PY%" -m compassx.cli.main %*
endlocal
