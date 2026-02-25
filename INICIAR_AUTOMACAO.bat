@echo off
chcp 65001 >nul
color 0b
echo =======================================================
echo    INICIANDO AUTOMACAO DE RANKING MUSICAL
echo =======================================================
echo.

set "PYTHON_EXE=c:\Users\Gustavo\Downloads\Automação Cortes\venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [!] O ambiente virtual da pasta de Cortes não foi encontrado.
    set "PYTHON_EXE=python"
)

echo [*] Verificando dependencias...
"%PYTHON_EXE%" -m pip install edge-tts yt-dlp google-generativeai python-dotenv groq

echo.
echo [*] Executando o script principal da IA...
"%PYTHON_EXE%" main.py

echo.
echo =======================================================
echo  Processo Concluido! Verifique a pasta "output"
echo =======================================================
pause
