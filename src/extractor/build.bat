@echo off
setlocal

echo === 🛠 Building Extractor ===

REM Step 1: Compile Go binary
echo --- Compiling Go code...
go build -o build/extractor.exe ./cmd/extractor.go
if %errorlevel% neq 0 (
    echo ❌ Go build failed!
    exit /b %errorlevel%
)
echo ✅ Go build successful: build\extractor.exe

REM Step 2: Build Docker image from precompiled binary
echo --- Building Docker image...
pushd ..\

docker build -f extractor/Dockerfile -t extractor .
if %errorlevel% neq 0 (
    echo ❌ Docker build failed!
    popd
    exit /b %errorlevel%
)

popd
echo ✅ Docker image built: extractor

endlocal


