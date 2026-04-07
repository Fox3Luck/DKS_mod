@echo off
REM Install DKS_mod as Windows Service using NSSM
REM Run as Administrator on .202 customer platform machines

echo Installing DKS_mod Integration API...
echo ================================================

REM Check if running as administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

REM Set paths
set INSTALL_DIR=%~dp0..
set PYTHON_PATH=python
set NSSM_PATH=%INSTALL_DIR%\nssm.exe
set SERVICE_NAME=DKS-Mod
set SERVICE_PORT=8400

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH!
    pause
    exit /b 1
)

REM Check if NSSM exists
if not exist "%NSSM_PATH%" (
    echo ERROR: NSSM not found at %NSSM_PATH%
    echo Please copy nssm.exe to the DKS_mod directory
    pause
    exit /b 1
)

REM Install Python dependencies
echo Installing Python dependencies...
pip install -r "%INSTALL_DIR%\requirements.txt"
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Python dependencies!
    pause
    exit /b 1
)

REM Check for required environment variables
if "%DKS_ADMIN_KEY%"=="" (
    echo WARNING: DKS_ADMIN_KEY environment variable not set!
    echo You must set this before the service can issue API tokens.
    echo   setx DKS_ADMIN_KEY "your-secret-admin-key" /M
    echo.
)

if "%DKS_SECRET_KEY%"=="" (
    echo WARNING: DKS_SECRET_KEY environment variable not set!
    echo A random key will be generated, but it will change on restart.
    echo For production, set a permanent key:
    echo   setx DKS_SECRET_KEY "your-64-char-hex-key" /M
    echo.
)

REM Remove existing service if present
"%NSSM_PATH%" status %SERVICE_NAME% >nul 2>&1
if %errorlevel% equ 0 (
    echo Removing existing %SERVICE_NAME% service...
    net stop %SERVICE_NAME% >nul 2>&1
    "%NSSM_PATH%" remove %SERVICE_NAME% confirm
)

REM Install service
echo Installing %SERVICE_NAME% service...
"%NSSM_PATH%" install %SERVICE_NAME% "%PYTHON_PATH%" "-m" "dks_mod.main"

echo Configuring service settings...
"%NSSM_PATH%" set %SERVICE_NAME% DisplayName "DKS_mod Integration API"
"%NSSM_PATH%" set %SERVICE_NAME% Description "Fox3 DCS x Digital Kneeboard Simulator Integration API (port %SERVICE_PORT%)"
"%NSSM_PATH%" set %SERVICE_NAME% Start SERVICE_AUTO_START
"%NSSM_PATH%" set %SERVICE_NAME% AppDirectory "%INSTALL_DIR%"

REM Restart behavior
"%NSSM_PATH%" set %SERVICE_NAME% AppThrottle 5000
"%NSSM_PATH%" set %SERVICE_NAME% AppRestartDelay 10000
"%NSSM_PATH%" set %SERVICE_NAME% AppExit Default Restart

REM Logging
"%NSSM_PATH%" set %SERVICE_NAME% AppStdout "%INSTALL_DIR%\logs\stdout.log"
"%NSSM_PATH%" set %SERVICE_NAME% AppStderr "%INSTALL_DIR%\logs\stderr.log"
"%NSSM_PATH%" set %SERVICE_NAME% AppRotateFiles 1
"%NSSM_PATH%" set %SERVICE_NAME% AppRotateOnline 1
"%NSSM_PATH%" set %SERVICE_NAME% AppRotateBytes 10485760

REM Create logs directory if it doesn't exist
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"

REM Add firewall rule for the API port
echo Adding firewall rule for port %SERVICE_PORT%...
netsh advfirewall firewall show rule name="DKS_mod API" >nul 2>&1
if %errorlevel% neq 0 (
    netsh advfirewall firewall add rule name="DKS_mod API" dir=in action=allow protocol=TCP localport=%SERVICE_PORT%
)

REM Start the service
echo Starting %SERVICE_NAME% service...
net start %SERVICE_NAME%

if %errorlevel% equ 0 (
    echo.
    echo ================================================
    echo SUCCESS: DKS_mod service installed and started!
    echo.
    echo Service Name: %SERVICE_NAME%
    echo API Port:     %SERVICE_PORT%
    echo Status:       Running
    echo Auto-start:   Enabled
    echo.
    echo API Health: http://localhost:%SERVICE_PORT%/api/health
    echo.
    echo To manage the service:
    echo   Start:  net start %SERVICE_NAME%
    echo   Stop:   net stop %SERVICE_NAME%
    echo   View:   services.msc
    echo.
    echo IMPORTANT: Set environment variables for production:
    echo   setx DKS_ADMIN_KEY "your-secret-admin-key" /M
    echo   setx DKS_SECRET_KEY "your-64-char-hex-key" /M
    echo ================================================
) else (
    echo.
    echo ERROR: Failed to start the service!
    echo Check the logs in %INSTALL_DIR%\logs\ for details
)

pause
