@echo off
chcp 65001 > nul
echo.
echo  Iniciando o sistema da Secretaria de Esportes e Lazer...
echo  Abrindo navegador em http://localhost:5000
echo.
echo  Para encerrar o sistema, feche esta janela.
echo.

:: Abre o navegador (aguarda o servidor subir)
start "" "http://localhost:5000"

:: Tenta python, py, ou caminho direto
python app.py 2> nul
if %errorlevel% neq 0 (
    py app.py 2> nul
)
if %errorlevel% neq 0 (
    "%LocalAppData%\Programs\Python\Python312\python.exe" app.py 2> nul
)
if %errorlevel% neq 0 (
    echo.
    echo  [ERRO] Python nao encontrado ou nao foi possivel iniciar.
    echo         Veja o LEIA-ME.txt para instrucoes.
    echo.
    pause
)
