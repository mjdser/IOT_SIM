@echo off
cd /d "%~dp0"
python hardware\launch.py
if errorlevel 1 pause
