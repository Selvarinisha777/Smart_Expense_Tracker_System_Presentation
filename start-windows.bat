@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo First install the project as described in README.md.
  echo py -m venv .venv
  echo .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)
echo Open http://127.0.0.1:5000 in your browser after the server starts.
.venv\Scripts\python.exe app.py
pause
