@echo off
setlocal

for /f %%v in ('uv run python -c "from version import __version__; print(__version__)"') do set VERSION=%%v
set APP_NAME=WSL-Snapaste-v%VERSION%

echo Building WSL Snapaste v%VERSION%...
uv run pyinstaller --onefile --windowed --name "%APP_NAME%" --clean main.py
if errorlevel 1 exit /b %errorlevel%

copy /Y "dist\%APP_NAME%.exe" "dist\WSL-Snapaste.exe" >nul
echo Build complete: dist\%APP_NAME%.exe
echo Stable latest alias: dist\WSL-Snapaste.exe

if not defined CI pause
