@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Gerando executavel unico (dist\TOTVS-Cert-Uploader.exe)...
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --onefile --windowed --name "TOTVS-Cert-Uploader" --collect-all customtkinter --collect-all playwright app.py
echo Concluido! Arquivo disponivel em: dist\TOTVS-Cert-Uploader.exe
pause
