@echo off
title Push to GitHub
set "PY=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" (
  echo [ERROR] Python not found.
  pause
  exit /b 1
)
"%PY%" "%~dp0push_to_github.py"
pause