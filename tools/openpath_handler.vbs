Dim url, path
url = WScript.Arguments(0)
path = Replace(url, "openpath://", "")
path = Replace(path, "/", "\")
' UNC paths must start with \\, re-add the prefix stripped during URL encoding
If Left(path, 2) <> "\\" Then
    path = "\\" & path
End If
Set shell = CreateObject("WScript.Shell")
shell.Run "explorer.exe " & Chr(34) & path & Chr(34), 1, False
