@echo off
REM teologia-cron.bat — Daily teologia.ai surface audit + freshness check
REM Runs: teologia_audit.py, verifies live deployment, logs to kænbæn genesis

set PYTHON=C:\gpu\Scripts\python.exe
set AUDIT_SCRIPT=C:\æ\scripts\cron\teologia_audit.py
set LOG=C:\æ\logs\teologia-cron.log
set GH=C:\æ\github-pages

echo [%date% %time%] === teologia cron start === >> "%LOG%"

REM 1. Run audit script
"%PYTHON%" "%AUDIT_SCRIPT%" >> "%LOG%" 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] AUDIT ISSUES FOUND >> "%LOG%"
) else (
    echo [%date% %time%] AUDIT PASS >> "%LOG%"
)

REM 2. Check live deployment
curl -s -o NUL -w "%%{http_code}" https://myaelmendez.github.io/teologia/ >> "%LOG%" 2>&1
echo " teologia/" >> "%LOG%"
curl -s -o NUL -w "%%{http_code}" https://myaelmendez.github.io/teologia/calendario.html >> "%LOG%" 2>&1
echo " calendario.html" >> "%LOG%"
curl -s -o NUL -w "%%{http_code}" https://myaelmendez.github.io/teologia/rtx-accelerator.html >> "%LOG%" 2>&1
echo " rtx-accelerator.html" >> "%LOG%"

REM 3. Git status check
cd /d "%GH%"
git status --short >> "%LOG%" 2>&1

echo [%date% %time%] === teologia cron complete === >> "%LOG%"
echo. >> "%LOG%"
