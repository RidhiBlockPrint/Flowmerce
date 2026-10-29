@echo off
rem Double-click to start Blog Ops. Uses the Python launcher (py) if present, otherwise python.
cd /d "%~dp0.."
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 scripts\run_seo.py %*
) else (
  python scripts\run_seo.py %*
)
if errorlevel 1 pause
