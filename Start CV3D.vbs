Option Explicit

Dim fso, sh, appDir, appPath, parentDir
Dim candidates, pythonFound, chosenPythonW, chosenPython
Dim pathEnv, pathParts, part, versions, v
Dim localAppData, programFiles, programFilesX86, virtualEnv
Dim key, candidate, pyExe, rc, msg

Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
Set candidates = CreateObject("Scripting.Dictionary")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
appPath = fso.BuildPath(appDir, "CV3D_app.py")
parentDir = fso.GetParentFolderName(appDir)

If Not fso.FileExists(appPath) Then
    MsgBox "CV3D_app.py was not found next to this launcher." & vbCrLf & vbCrLf & _
           "Keep 'Start CV3D.vbs' in the CV3D UI folder together with CV3D_app.py.", _
           vbCritical + vbOKOnly, "CV3D could not start"
    WScript.Quit 2
End If

Sub AddCandidate(ByVal p)
    Dim normalized
    If Len(Trim(p)) = 0 Then Exit Sub
    normalized = fso.GetAbsolutePathName(p)
    If InStr(1, LCase(normalized), "\windowsapps\", vbTextCompare) > 0 Then Exit Sub
    If Not candidates.Exists(LCase(normalized)) Then
        candidates.Add LCase(normalized), normalized
    End If
End Sub

Function HasPySide6(ByVal pythonExe)
    Dim checkRc
    On Error Resume Next
    Err.Clear
    checkRc = sh.Run("""" & pythonExe & """ -c ""import PySide6""", 0, True)
    If Err.Number <> 0 Then
        Err.Clear
        HasPySide6 = False
    Else
        HasPySide6 = (checkRc = 0)
    End If
    On Error GoTo 0
End Function

' Prefer Python environments shipped with or placed next to CV3D.
AddCandidate fso.BuildPath(appDir, "python\pythonw.exe")
AddCandidate fso.BuildPath(appDir, "runtime\pythonw.exe")
AddCandidate fso.BuildPath(appDir, ".venv\Scripts\pythonw.exe")
AddCandidate fso.BuildPath(appDir, "venv\Scripts\pythonw.exe")
AddCandidate fso.BuildPath(parentDir, ".venv\Scripts\pythonw.exe")
AddCandidate fso.BuildPath(parentDir, "venv\Scripts\pythonw.exe")

virtualEnv = sh.ExpandEnvironmentStrings("%VIRTUAL_ENV%")
If InStr(virtualEnv, "%VIRTUAL_ENV%") = 0 And Len(Trim(virtualEnv)) > 0 Then
    AddCandidate fso.BuildPath(virtualEnv, "Scripts\pythonw.exe")
End If

' Then try normal per-user/system Python installations, newest versions first.
versions = Array("314", "313", "312", "311", "310", "39")
localAppData = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%")
programFiles = sh.ExpandEnvironmentStrings("%ProgramFiles%")
programFilesX86 = sh.ExpandEnvironmentStrings("%ProgramFiles(x86)%")

For Each v In versions
    If InStr(localAppData, "%LOCALAPPDATA%") = 0 Then
        AddCandidate fso.BuildPath(localAppData, "Programs\Python\Python" & v & "\pythonw.exe")
    End If
    If InStr(programFiles, "%ProgramFiles%") = 0 Then
        AddCandidate fso.BuildPath(programFiles, "Python" & v & "\pythonw.exe")
    End If
    If InStr(programFilesX86, "%ProgramFiles(x86)%") = 0 Then
        AddCandidate fso.BuildPath(programFilesX86, "Python" & v & "\pythonw.exe")
    End If
Next

' Finally search PATH, while deliberately ignoring Windows Store app aliases.
pathEnv = sh.ExpandEnvironmentStrings("%PATH%")
pathParts = Split(pathEnv, ";")
For Each part In pathParts
    part = Trim(part)
    If Len(part) > 0 Then
        AddCandidate fso.BuildPath(part, "pythonw.exe")
    End If
Next

pythonFound = False
chosenPythonW = ""
chosenPython = ""

For Each key In candidates.Keys
    candidate = candidates(key)
    If fso.FileExists(candidate) Then
        pythonFound = True
        pyExe = fso.BuildPath(fso.GetParentFolderName(candidate), "python.exe")
        If fso.FileExists(pyExe) Then
            If HasPySide6(pyExe) Then
                chosenPythonW = candidate
                chosenPython = pyExe
                Exit For
            End If
        End If
    End If
Next

If Len(chosenPythonW) = 0 Then
    If pythonFound Then
        msg = "Python was found, but no detected installation has PySide6 available." & vbCrLf & vbCrLf & _
              "CV3D needs PySide6 in the Python environment used to start it." & vbCrLf & _
              "Install PySide6 in your CV3D Python environment, then double-click this launcher again."
    Else
        msg = "No suitable Python installation could be found." & vbCrLf & vbCrLf & _
              "The launcher checked CV3D-local environments, standard Python install folders, and PATH." & vbCrLf & _
              "Install Python (or place a CV3D virtual environment in .venv) and try again."
    End If
    MsgBox msg, vbCritical + vbOKOnly, "CV3D could not start"
    WScript.Quit 3
End If

' CV3D resolves its bundled helpers relative to CV3D_app.py, but using the app
' directory as the working directory also keeps any ordinary relative paths sane.
sh.CurrentDirectory = appDir

On Error Resume Next
Err.Clear
rc = sh.Run("""" & chosenPythonW & """ """ & appPath & """", 1, False)
If Err.Number <> 0 Then
    msg = "Python was found, but CV3D could not be launched." & vbCrLf & vbCrLf & _
          "Python: " & chosenPythonW & vbCrLf & _
          "CV3D: " & appPath & vbCrLf & vbCrLf & _
          "Windows error: " & Err.Description
    MsgBox msg, vbCritical + vbOKOnly, "CV3D could not start"
    Err.Clear
    WScript.Quit 4
End If
On Error GoTo 0
