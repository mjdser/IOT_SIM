@echo off
cd /d "%~dp0simulator"
set IOT_MIRROR=0
python launch.py
if errorlevel 1 pause
