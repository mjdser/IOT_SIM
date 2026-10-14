@echo off
cd /d "%~dp0simulator"
if not exist "build\lvgl_sim.exe" (
  echo Build the host first: python build.py
  pause
  exit /b 1
)
if not exist "node_modules\electron\dist\electron.exe" (
  echo Install the desktop dependencies first: npm install
  pause
  exit /b 1
)
python launch.py
if errorlevel 1 pause
