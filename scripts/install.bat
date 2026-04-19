@echo off
chcp 65001 > nul
cd /d "%~dp0.."
set UV_LINK_MODE=hardlink
set UV_CACHE_DIR=%CD%\libs\.uv-cache
libs\python\python.exe NeuroMita.pyz --install
pause
