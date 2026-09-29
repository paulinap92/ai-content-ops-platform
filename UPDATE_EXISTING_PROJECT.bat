@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo Canarias Cerca Content Studio updater
echo ========================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0UPDATE_EXISTING_PROJECT.ps1"
echo.
if errorlevel 1 (
  echo UPDATE FAILED. Read the error above.
) else (
  echo Update finished.
)
echo.
pause
