@echo off
title InkCanvas - Check All
set "PY=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" (
  echo [ERROR] Python not found:
  echo   %PY%
  echo Ask for help.
  pause
  exit /b 1
)
"%PY%" "%~dp0check_all.py"
pause