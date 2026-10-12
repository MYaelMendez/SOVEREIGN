; æ:// Taskbar Search — AutoHotkey v2
; Transforms Win+S into the æ:// command interface
#Requires AutoHotkey v2.0
#SingleInstance Force

; ── Configuration ──
global AE_SEARCH_URL := "http://127.0.0.1:8124/ae-search.html"
global AE_SEARCH_TITLE := ">_æ://"

; ── Win+S → æ:// Search ──
#s:: {
    Run(AE_SEARCH_URL)
}

; ── Win+Shift+S → æ:// Command Prompt ──
#+s:: {
    Run("http://127.0.0.1:8124/command-prompt.html")
}

; ── Win+` → æ:// Omnibox ──
#`:: {
    Run("http://127.0.0.1:8124/omnibox.html")
}

; ── Print Screen → æ:// Capture (HP Snipping Tool features) ──
PrintScreen:: {
    Run('powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\æ\ahk\capture-region.ps1"')
}

#PrintScreen:: {
    Run('powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\æ\ahk\capture-region.ps1" -Full -Receipt')
}

+PrintScreen:: {
    Run('powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\æ\ahk\capture-region.ps1" -Annotate -Receipt')
}

; ── Tray icon ──
A_TrayMenu.Delete()
A_TrayMenu.Add(">_æ:// Search", (*) => Run(AE_SEARCH_URL))
A_TrayMenu.Add(">_æ:// Command", (*) => Run("http://127.0.0.1:8124/command-prompt.html"))
A_TrayMenu.Add(">_æ:// Omnibox", (*) => Run("http://127.0.0.1:8124/omnibox.html"))
A_TrayMenu.Add(">_æ:// Capture", (*) => Run('powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\æ\ahk\capture-region.ps1"'))
A_TrayMenu.Add()
A_TrayMenu.Add("Exit æ://", (*) => ExitApp())
