@echo off
chcp 65001 > nul
cd /d "%~dp0"
set PY=libs\python\python.exe
set NEUROMITA_BACKEND=amd
set UV_LINK_MODE=hardlink
set UV_CACHE_DIR=%CD%\libs\.uv-cache

if not exist "%PY%" (
    echo Python runtime not found: %CD%\%PY%
    goto :fail
)
if not exist "NeuroMita.pyz" (
    echo NeuroMita.pyz not found in %CD%
    goto :fail
)

%PY% -m pip show uv >nul 2>&1 || %PY% -m pip install --upgrade uv || goto :fail
%PY% -c "import os, sys; sys.path.insert(0, os.path.abspath('NeuroMita.pyz')); from utils.uv_sync import UvSync; UvSync().apply({'core','backend-amd','asr-gigaam'})" || goto :fail

if exist "libs\python\Scripts\pywin32_postinstall.py" (
    echo Registering pywin32...
    %PY% libs\python\Scripts\pywin32_postinstall.py -install >nul 2>&1
)

%PY% NeuroMita.pyz
goto :eof

:fail
echo Launch failed.
pause
exit /b 1
