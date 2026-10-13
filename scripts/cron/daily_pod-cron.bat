@echo off
REM daily_pod-cron.bat — Daily podcast: social gathering + render + gate + deploy
REM Runs every 6 hours (midnight / noon / 6pm / 6am) as the daily podcast cycle.
REM Output: studio/output/daily-episode-*.mp4, daily MP3, published to github-pages

set PYTHON=C:\gpu\Scripts\python.exe
set AGENTS=C:\æ\agents
set SCRIPTS=C:\æ\scripts\cron
set LOG=C:\æ\logs\daily_pod_cron.log
set GH=C:\æ\github-pages

echo [%date% %time%] === daily podcast cron start === >> "%LOG%"

REM 1. Gather social media posts
echo [%date% %time%] Step 1: Gathering social feed... >> "%LOG%"
"%PYTHON%" "%AGENTS%\social_feed.py" --source auto >> "%LOG%" 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: social feed gathering failed >> "%LOG%"
) else (
    echo [%date% %time%] Step 1: Social feed gathered >> "%LOG%"
)

REM 2. Generate spec + render + gate + deploy
echo [%date% %time%] Step 2: Daily podcast cycle... >> "%LOG%"
"%PYTHON%" "%SCRIPTS%\daily_pod_cron.py" --feed auto --render >> "%LOG%" 2>&1
set POD_EXIT=%errorlevel%
echo [%date% %time%] Step 2: daily pod cycle exit=%POD_EXIT% >> "%LOG%"

echo [%date% %time%] === daily podcast cron complete === >> "%LOG%"
echo. >> "%LOG%"
