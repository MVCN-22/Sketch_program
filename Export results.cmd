@echo off
rem SOFiSTiK results for Rebar Sketch Studio: drop a .cdb on this file, or double-click it and pick one.
rem Writes <model>.results.json next to the .cdb; open that on step 2 of the website. Nothing is sent anywhere.
setlocal
set "HERE=%~dp0"
set "PY=%USERPROFILE%\.rhinocode\py39-rh8\python.exe"
if not exist "%PY%" set "PY="
if not defined PY for /f "delims=" %%p in ('where python 2^>nul') do if not defined PY set "PY=%%p"
if not defined PY (
  echo Python was not found. Install Rhino 8, or Python 3.9 or newer ^(64-bit^), and try again.
  pause
  exit /b 1
)
"%PY%" "%HERE%export_results.py" %*
echo.
pause
