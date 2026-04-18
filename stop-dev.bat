@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM stop-dev.bat — Stop TropiCare local development environment (Windows)
REM ─────────────────────────────────────────────────────────────────────────────
setlocal

echo.
echo   TropiCare — Stopping local dev...
echo.

REM ── Parse flags ─────────────────────────────────────────────────────────────
set CLEAN_VOLUMES=0

if "%~1"=="--clean" set CLEAN_VOLUMES=1
if "%~1"=="-c"      set CLEAN_VOLUMES=1
if "%~1"=="--help"  goto :usage
if "%~1"=="-h"      goto :usage

if %CLEAN_VOLUMES% equ 1 (
    echo   [!] Stopping containers and removing volumes...
    docker compose down -v
    echo   [OK] All containers stopped and volumes removed
) else (
    docker compose down
    echo   [OK] All containers stopped (data volumes preserved)
)

echo.
echo   Restart with: start-dev.bat
echo.

endlocal
exit /b 0

:usage
echo   Usage: scripts\stop-dev.bat [OPTIONS]
echo.
echo   Options:
echo     --clean, -c   Remove Docker volumes (deletes all local data)
echo     --help,  -h   Show this help
echo.
endlocal
exit /b 0
