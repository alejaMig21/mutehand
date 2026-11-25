@echo off
rem Opens Workflow Factory: starts the editor without a console window and opens it in your browser.
rem Double-click this file. A second double-click opens the same editor again.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo The project environment is missing. Run "uv sync" in this folder first, then double-click this file again.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m workflow_factory.app
