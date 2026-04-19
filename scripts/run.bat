@echo off
chcp 65001 > nul
cd /d "%~dp0.."
set PY=libs\python\python.exe
set UV_LINK_MODE=hardlink
set UV_CACHE_DIR=%CD%\libs\.uv-cache

if not exist "%PY%" (echo Python not found: %CD%\%PY% & pause & exit /b 1)
if not exist "NeuroMita.pyz" (echo NeuroMita.pyz not found & pause & exit /b 1)

%PY% -c "import dotenv" >nul 2>&1
if errorlevel 1 (
    echo Packages not installed. Running install...
    %PY% NeuroMita.pyz --install || (echo Install failed. & pause & exit /b 1)
)

:launch
%PY% NeuroMita.pyz
if %errorlevel% == 42 (
    echo Update applied, restarting...
    goto :launch
)
