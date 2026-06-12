@echo off
setlocal

for /f %%v in ('uv run python -c "from version import __version__; print(__version__)"') do set VERSION=%%v
set APP_NAME=WSL-Snapaste-v%VERSION%

echo Building WSL Snapaste v%VERSION%...
uv run pyinstaller --noconfirm --windowed --name "%APP_NAME%" --clean main.py
if errorlevel 1 exit /b %errorlevel%

powershell -NoProfile -Command "Remove-Item -Recurse -Force 'dist\WSL-Snapaste' -ErrorAction SilentlyContinue; Copy-Item -Recurse 'dist\%APP_NAME%' 'dist\WSL-Snapaste'; Copy-Item 'dist\WSL-Snapaste\%APP_NAME%.exe' 'dist\WSL-Snapaste\WSL-Snapaste.exe' -Force; Compress-Archive -Path 'dist\WSL-Snapaste\*' -DestinationPath 'dist\%APP_NAME%.zip' -Force"
if errorlevel 1 exit /b %errorlevel%
echo Build complete: dist\%APP_NAME%\%APP_NAME%.exe
echo Stable latest alias: dist\WSL-Snapaste\WSL-Snapaste.exe
echo Release package: dist\%APP_NAME%.zip

if not defined CI pause
