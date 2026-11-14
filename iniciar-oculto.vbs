' Liga o sistema sem abrir nenhuma janela (usado pelo inicio automatico do Windows).
' Roda o iniciar.bat em modo "silencioso" com a janela oculta; a saida vai para logs\inicio.log.
Set fso = CreateObject("Scripting.FileSystemObject")
pasta = fso.GetParentFolderName(WScript.ScriptFullName)
If Not fso.FolderExists(pasta & "\logs") Then fso.CreateFolder(pasta & "\logs")
comando = "cmd /c """"" & pasta & "\iniciar.bat"" silencioso > """ & pasta & "\logs\inicio.log"" 2>&1"""
' 0 = janela oculta; False = nao espera terminar
CreateObject("WScript.Shell").Run comando, 0, False
