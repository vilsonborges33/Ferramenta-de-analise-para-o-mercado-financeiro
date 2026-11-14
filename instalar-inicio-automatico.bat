@echo off
REM Faz o sistema ligar sozinho quando voce entra no Windows (e buscar os dados atrasados), sem abrir janelas:
REM o atalho chama o iniciar-oculto.vbs, que roda o iniciar.bat escondido (registro em logs\inicio.log).
REM Para desfazer, rode este arquivo de novo com "remover":  instalar-inicio-automatico.bat remover
set PASTA_INICIO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set ATALHO=%PASTA_INICIO%\Analise de mercado.vbs

REM Versao antiga (.bat): abria uma janela do cmd a cada login. Sai em qualquer caso.
del "%PASTA_INICIO%\Analise de mercado.bat" >nul 2>&1

if "%1"=="remover" (
  del "%ATALHO%" >nul 2>&1
  echo Inicio automatico removido.
  pause
  exit /b 0
)

> "%ATALHO%" echo CreateObject("WScript.Shell").Run "wscript.exe ""%~dp0iniciar-oculto.vbs""", 0, False
echo Pronto. O sistema vai ligar sozinho, sem abrir janelas, sempre que voce entrar no Windows.
echo (Para desfazer: instalar-inicio-automatico.bat remover)
pause
