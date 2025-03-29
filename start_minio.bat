@echo off
SETLOCAL

:: Set port number and MinIO path
SET MINIO_PORT=9000
SET MINIO_PATH=C:\minio\minio.exe
SET DATA_DIR=C:\minio-data

:: Check if MinIO is already running
echo Checking if MinIO is already running on port %MINIO_PORT%...
netstat -ano | findstr :%MINIO_PORT% >nul

IF %ERRORLEVEL% EQU 0 (
    echo ✅ MinIO is already running on port %MINIO_PORT%.
) ELSE (
    echo 🚀 Starting MinIO...
    start "" "%MINIO_PATH%" server %DATA_DIR% --console-address ":9001"
    timeout /t 3 >nul
    echo ✅ MinIO started.
)

echo.
echo ✔️ Ready for data extraction.
pause
