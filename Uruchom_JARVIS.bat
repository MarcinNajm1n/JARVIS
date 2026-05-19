@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" jarvis_app.py
) else (
  python jarvis_app.py
)
pause
