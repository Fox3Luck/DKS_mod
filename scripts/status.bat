@echo off
REM Check DKS_mod service status
REM Can be run without admin privileges

set INSTALL_DIR=%~dp0..
set NSSM_PATH=%INSTALL_DIR%\nssm.exe
set SERVICE_NAME=DKS-Mod
set SERVICE_PORT=8400

echo DKS_mod Status Check
echo ================================================

REM Check service status
echo.
echo [Service]
"%NSSM_PATH%" status %SERVICE_NAME% 2>nul
if %errorlevel% neq 0 (
    echo Service %SERVICE_NAME% is NOT installed
)

REM Check if port is listening
echo.
echo [Port %SERVICE_PORT%]
netstat -an | findstr ":%SERVICE_PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo Port %SERVICE_PORT% is LISTENING
) else (
    echo Port %SERVICE_PORT% is NOT listening
)

REM Hit health endpoint
echo.
echo [Health Check]
curl -s http://localhost:%SERVICE_PORT%/api/health 2>nul
if %errorlevel% neq 0 (
    echo API not responding
)

echo.
echo.

REM Show recent log entries
echo [Recent Logs]
if exist "%INSTALL_DIR%\logs\stderr.log" (
    echo --- Last 10 lines of stderr.log ---
    powershell -Command "Get-Content '%INSTALL_DIR%\logs\stderr.log' -Tail 10"
) else (
    echo No log files found
)

echo.
echo ================================================
pause
