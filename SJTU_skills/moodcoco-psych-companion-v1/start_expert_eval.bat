@echo off
setlocal

cd /d "%~dp0"
set RUNNER_PATH=expert-eval\runner.py

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%RUNNER_PATH%"
  goto end
)

where python >nul 2>nul
if %errorlevel%==0 (
  python "%RUNNER_PATH%"
  goto end
)

echo Python 3 is not installed or not in PATH.
echo Please install Python 3 and try again.

:end
echo.
pause
