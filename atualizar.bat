@echo off
REM Atualiza o projeto com a versao mais recente do GitHub e reinicia o sistema.
REM Uso: de dois cliques neste arquivo (o Docker Desktop precisa estar aberto).
cd /d "%~dp0"

echo === Baixando a versao mais recente ===
git pull
if errorlevel 1 (
  echo.
  echo Nao foi possivel atualizar. Veja a mensagem acima.
  pause
  exit /b 1
)

if not exist .env copy .env.example .env

echo.
echo === Reconstruindo e reiniciando o sistema ===
docker compose up -d --build
if errorlevel 1 (
  echo.
  echo Falha ao subir o sistema. O Docker Desktop esta aberto?
  pause
  exit /b 1
)

echo.
echo Pronto. Abra http://localhost:3000 no navegador.
pause
