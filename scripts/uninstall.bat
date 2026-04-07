@echo off
REM Uninstall DKS_mod Windows Service
REM Run as Administrator

echo Uninstalling DKS_mod Integration API...
echo ================================================

REM Check if running as administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

set INSTALL_DIR=%~dp0..
set NSSM_PATH=%INSTALL_DIR%\nssm.exe
set SERVICE_NAME=DKS-Mod

REM Stop and remove service
echo Stopping %SERVICE_NAME% service...
net stop %SERVICE_NAME% >nul 2>&1

echo Removing %SERVICE_NAME% service...
"%NSSM_PATH%" remove %SERVICE_NAME% confirm >nul 2>&1

REM Remove firewall rule
echo Removing firewall rule...
netsh advfirewall firewall delete rule name="DKS_mod API" >nul 2>&1

echo.
echo ================================================
echo DKS_mod service removed.
echo.
echo NOTE: Project files, database, and logs were NOT deleted.
echo   Database: %INSTALL_DIR%\dks_mod.db
echo   Logs:     %INSTALL_DIR%\logs\
echo.
echo To fully remove, delete the DKS_mod directory.
echo ================================================

pause
