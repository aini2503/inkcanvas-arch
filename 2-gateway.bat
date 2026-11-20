@echo off
title AI Gateway - do not close this window
set "PY=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" (
  echo [ERROR] Python not found.
  pause
  exit /b 1
)
"%PY%" "%~dp0gateway\server.py" --offline --port 8788
pause