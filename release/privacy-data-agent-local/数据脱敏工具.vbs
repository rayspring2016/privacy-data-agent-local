' 数据脱敏工具.vbs — Silent launcher for Privacy Data Agent
' Double-click this file to start the web UI without any console window.
'
' First time: run windows\00-install-windows.bat to set up the environment.

Dim WshShell, fso, strDir, strBat
Set fso      = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

strDir = fso.GetParentFolderName(WScript.ScriptFullName)
strBat = strDir & "\windows\03-launch-web-ui-windows.bat"

If Not fso.FileExists(strBat) Then
    MsgBox "启动脚本未找到：" & vbCrLf & strBat, vbCritical, "数据脱敏工具"
    WScript.Quit 1
End If

' Run with hidden window (0), async (False)
WshShell.Run Chr(34) & strBat & Chr(34), 0, False

Set WshShell = Nothing
Set fso      = Nothing
