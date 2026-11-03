@echo off
REM Liga o sistema e abre no navegador. Ao ligar, o sistema busca sozinho os dados
REM que ficaram para tras enquanto o computador estava desligado.
REM Uso: dois cliques. Com "silencioso" (inicio automatico do Windows), nao abre o navegador nem pausa.
cd /d "%~dp0"
set MODO=%1

docker info >nul 2>&1
if not errorlevel 1 goto pronto
echo === Abrindo o Docker Desktop ===
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
set /a TENTATIVAS=0
:esperar
timeout /t 5 /nobreak >nul
docker info >nul 2>&1
if not errorlevel 1 goto pronto
set /a TENTATIVAS+=1
if %TENTATIVAS% lss 60 goto esperar
echo O Docker Desktop nao respondeu em 5 minutos. Abra-o manualmente e tente de novo.
if not "%MODO%"=="silencioso" pause
exit /b 1
:pronto

if not exist .env copy .env.example .env >nul

echo === Ligando o sistema ===
docker compose up -d
if errorlevel 1 (
  echo Falha ao ligar o sistema. Veja a mensagem acima.
  if not "%MODO%"=="silencioso" pause
  exit /b 1
)

echo.
echo Sistema ligado. Os dados atrasados estao sendo buscados em segundo plano
echo (acompanhe em http://localhost:3000/status).
if "%MODO%"=="silencioso" exit /b 0
timeout /t 5 /nobreak >nul
start "" http://localhost:3000
