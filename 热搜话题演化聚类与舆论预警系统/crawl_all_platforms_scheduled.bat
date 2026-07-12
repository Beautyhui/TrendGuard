@echo off
REM 任务计划程序专用：操作里程序填本文件，「添加参数」留空。
setlocal
cd /d "%~dp0"

set "INV=%~dp0data\scheduled_invoke.txt"
if not exist "%~dp0data" mkdir "%~dp0data" 2>nul
echo [%date% %time%] scheduled wrapper started>>"%INV%"

call "%~dp0crawl_all_platforms_once.bat" silent
set "RC=%ERRORLEVEL%"
echo [%date% %time%] finished rc=%RC%>>"%INV%"
endlocal
exit /b %RC%
