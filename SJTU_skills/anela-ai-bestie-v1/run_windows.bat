@echo off
setlocal EnableExtensions
title AI Bestie Expert Evaluation

cd /d "%~dp0"
if errorlevel 1 goto bad_start_dir

set "IS_32BIT_WINDOWS="
if /i "%PROCESSOR_ARCHITECTURE%"=="x86" if "%PROCESSOR_ARCHITEW6432%"=="" set "IS_32BIT_WINDOWS=1"

echo AI Bestie Expert Evaluation
echo Working directory: %CD%
echo.

if defined IS_32BIT_WINDOWS (
  echo Detected 32-bit Windows.
  echo This launcher will use local Python if uv is unavailable or fails.
  echo.
)

where uv >nul 2>nul
if not errorlevel 1 goto run_with_uv

if defined IS_32BIT_WINDOWS (
  echo uv was not found. Skipping uv auto-install on 32-bit Windows.
  echo.
  goto run_with_python
)

echo uv was not found.
echo This evaluator can use uv to create an isolated Python environment.
set /p INSTALL_UV="Install uv now? [Y/N]: "
if /i "%INSTALL_UV%"=="N" goto run_with_python

powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
where uv >nul 2>nul
if not errorlevel 1 goto run_with_uv

echo uv install did not complete successfully.
echo.
goto run_with_python

:run_with_uv
echo Running with uv...
echo.
uv run --with "pydantic>=2.7" --with "python-dotenv>=1.0" python run_expert_eval.py
set "RUN_EXIT=%ERRORLEVEL%"
if "%RUN_EXIT%"=="0" goto done

echo.
echo uv run failed with exit code %RUN_EXIT%.
echo Trying local Python fallback...
echo.
goto run_with_python

:run_with_python
call :find_python
if not defined PYTHON_CMD goto no_python

echo Using local Python: %PYTHON_CMD%
%PYTHON_CMD% -c "import sys; print(sys.version); raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto old_python

if not exist "requirements-expert.txt" goto missing_requirements

if not exist ".expert_eval_venv\Scripts\python.exe" (
  echo Creating local environment...
  %PYTHON_CMD% -m venv ".expert_eval_venv"
)

if exist ".expert_eval_venv\Scripts\python.exe" (
  set "RUN_PY=.expert_eval_venv\Scripts\python.exe"
  "%RUN_PY%" -m pip install --upgrade pip
  if errorlevel 1 goto pip_failed
  "%RUN_PY%" -m pip install -r requirements-expert.txt
  if errorlevel 1 goto pip_failed
  "%RUN_PY%" run_expert_eval.py
  set "RUN_EXIT=%ERRORLEVEL%"
  if "%RUN_EXIT%"=="0" goto done
  goto app_failed
)

echo Could not create a local environment. Trying user-site install...
%PYTHON_CMD% -m pip install --user -r requirements-expert.txt
if errorlevel 1 goto pip_failed
%PYTHON_CMD% run_expert_eval.py
set "RUN_EXIT=%ERRORLEVEL%"
if "%RUN_EXIT%"=="0" goto done
goto app_failed

:find_python
set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if defined PYTHON_CMD exit /b 0

where python >nul 2>nul
if not errorlevel 1 (
  python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)
exit /b 0

:bad_start_dir
echo Could not enter the evaluator folder.
goto fail

:no_python
echo No usable Python was found.
echo Please install Python 3.10 or newer, then run this file again.
goto fail

:old_python
echo Python 3.10 or newer is required.
goto fail

:missing_requirements
echo requirements-expert.txt is missing from this folder.
goto fail

:pip_failed
echo Failed to install required Python packages.
echo On 32-bit Windows, please make sure Python 3.10+ and pip are installed.
goto fail

:app_failed
echo The evaluator stopped with exit code %RUN_EXIT%.
goto fail

:done
echo.
echo Evaluation finished.
goto end

:fail
echo.
echo The evaluator could not start. Please send a screenshot of this window.

:end
echo.
pause
