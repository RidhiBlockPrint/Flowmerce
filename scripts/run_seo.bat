@echo off
rem Double-click to start Flowmerce. Uses the Python launcher (py) if present, otherwise python.
cd /d "%~dp0.."
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 scripts\run_flowmerce.py %*
) else (
  python scripts\run_flowmerce.py %*
)
if errorlevel 1 pause
