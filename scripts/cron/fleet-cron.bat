@echo off
REM ae:// fleet cron — self-improvement cycle
REM Reads kænbæn before acting. Every run produces a GPU-verified receipt.

set PYTHON=C:\gpu\Scripts\python.exe
set AGENTS=C:\æ\agents
set KÆNBÆN=C:\æ\kænbæn
set LOG=C:\æ\logs\fleet-cron.log

echo [%date% %time%] === fleet-cron start === >> "%LOG%"

REM 1. Read kænbæn — system memory
if exist "%KÆNBÆN%\system-map.json" (
    echo [%date% %time%] kænbæn: system-map loaded >> "%LOG%"
) else (
    echo [%date% %time%] ERROR: kænbæn not found >> "%LOG%"
    exit /b 1
)

REM 2. Zeus self-healing on vscoder/src
echo [%date% %time%] zeus: scanning vscoder/src >> "%LOG%"
"%PYTHON%" "%AGENTS%\zeus_engine.py" code vscoder/src >> "%LOG%" 2>&1
echo [%date% %time%] zeus: vscoder/src done >> "%LOG%"

REM 3. Zeus self-healing on site
echo [%date% %time%] zeus: scanning site >> "%LOG%"
"%PYTHON%" "%AGENTS%\zeus_engine.py" code site >> "%LOG%" 2>&1
echo [%date% %time%] zeus: site done >> "%LOG%"

REM 4. Zeus self-healing on github-pages
echo [%date% %time%] zeus: scanning github-pages >> "%LOG%"
"%PYTHON%" "%AGENTS%\zeus_engine.py" code github-pages >> "%LOG%" 2>&1
echo [%date% %time%] zeus: github-pages done >> "%LOG%"

REM 5. Zeus self-healing on hermes-fork
echo [%date% %time%] zeus: scanning hermes-fork >> "%LOG%"
"%PYTHON%" "%AGENTS%\zeus_engine.py" code hermes-fork >> "%LOG%" 2>&1
echo [%date% %time%] zeus: hermes-fork done >> "%LOG%"

REM 6. Zeus self-healing on agents
echo [%date% %time%] zeus: scanning agents >> "%LOG%"
"%PYTHON%" "%AGENTS%\zeus_engine.py" code agents >> "%LOG%" 2>&1
echo [%date% %time%] zeus: agents done >> "%LOG%"

REM 7. Zeus self-healing on threejs-curriculo
echo [%date% %time%] zeus: scanning threejs-curriculo >> "%LOG%"
"%PYTHON%" "%AGENTS%\zeus_engine.py" code threejs-curriculo >> "%LOG%" 2>&1
echo [%date% %time%] zeus: threejs-curriculo done >> "%LOG%"

REM 8. AEE targets (when they exist)
if exist "C:\æ\aee\rtl" (
    echo [%date% %time%] zeus: scanning aee/rtl >> "%LOG%"
    "%PYTHON%" "%AGENTS%\zeus_engine.py" code C:\æ\aee\rtl >> "%LOG%" 2>&1
    echo [%date% %time%] zeus: aee/rtl done >> "%LOG%"
)
if exist "C:\æ\aee\synthesis" (
    echo [%date% %time%] zeus: scanning aee/synthesis >> "%LOG%"
    "%PYTHON%" "%AGENTS%\zeus_engine.py" code C:\æ\aee\synthesis >> "%LOG%" 2>&1
    echo [%date% %time%] zeus: aee/synthesis done >> "%LOG%"
)
if exist "C:\æ\aee\layout" (
    echo [%date% %time%] zeus: scanning aee/layout >> "%LOG%"
    "%PYTHON%" "%AGENTS%\zeus_engine.py" code C:\æ\aee\layout >> "%LOG%" 2>&1
    echo [%date% %time%] zeus: aee/layout done >> "%LOG%"
)

REM 9. Supervision selftest
echo [%date% %time%] supervision: selftest >> "%LOG%"
"%PYTHON%" "%AGENTS%\hermes_supervision.py" selftest >> "%LOG%" 2>&1
echo [%date% %time%] supervision: selftest done >> "%LOG%"

echo [%date% %time%] === fleet-cron complete === >> "%LOG%"
