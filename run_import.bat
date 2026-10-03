@echo off
chcp 65001 >nul
cd /d "%~dp0"
python import_gui.py
if errorlevel 1 pause
