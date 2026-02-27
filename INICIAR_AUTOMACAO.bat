@echo off
chcp 65001 >nul
color 0b
echo =======================================================
echo    INICIANDO AUTOMACAO DE RANKING MUSICAL
echo =======================================================
echo.

:: Tenta usar o comando 'py' que é o padrão do launcher do Python no Windows
set "PYTHON_CMD=py"

echo [*] Verificando dependencias...
%PYTHON_CMD% -m pip install -r requirements.txt --quiet

echo.
echo [*] Abrindo Interface Grafica...
%PYTHON_CMD% app_gui.py

echo.
echo =======================================================
echo  Interface Fechada.
echo =======================================================
pause
