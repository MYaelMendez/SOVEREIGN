@echo off
REM curriculum-cron.bat — Auto-complete threejs curriculum (W4-W12)
REM Checks for missing/failed videos, re-renders them, deploys to github-pages.
REM Scheduled via Windows Task Scheduler (schtasks).

set PYTHON=C:\gpu\Scripts\python.exe
set SCRIPT=C:\æ\scripts\cron\re-render_missing.py
set LOG=C:\æ\logs\curriculum-cron.log
set NODE=C:\Users\yaelm\AppData\Local\hermes\tools\node-26.7.0-win32-x64\node.exe
set FFNVENC=C:\Users\yaelm\AppData\Local\hermes\tools\ffmpeg-7.1-nvenc\bin
set PATH=%FFNVENC%;%PATH%

echo [%date% %time%] === curriculum-cron start === >> "%LOG%"

"%PYTHON%" "%SCRIPT%" --once >> "%LOG%" 2>&1
set RC=%errorlevel%

if %RC% equ 0 (
    echo [%date% %time%] PASS - all weeks complete >> "%LOG%"
) else (
    echo [%date% %time%] RC=%RC% - some weeks still pending >> "%LOG%"
)

echo [%date% %time%] === curriculum-cron complete === >> "%LOG%"
echo. >> "%LOG%"
