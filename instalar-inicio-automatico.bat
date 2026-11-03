@echo off
REM Faz o sistema ligar sozinho quando voce entra no Windows (e buscar os dados atrasados).
REM Para desfazer, rode este arquivo de novo com "remover":  instalar-inicio-automatico.bat remover
set ATALHO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Analise de mercado.bat

if "%1"=="remover" (
  del "%ATALHO%" >nul 2>&1
  echo Inicio automatico removido.
  pause
  exit /b 0
)

> "%ATALHO%" echo @echo off
>> "%ATALHO%" echo start "Analise de mercado" /min cmd /c ""%~dp0iniciar.bat" silencioso"
echo Pronto. O sistema vai ligar sozinho sempre que voce entrar no Windows.
echo (Para desfazer: instalar-inicio-automatico.bat remover)
pause
