@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

REM 必须先到本 bat 所在目录（否则找不到 crawl_*.py）
cd /d "%~dp0"

REM 任务计划程序「添加参数」填：silent   （不暂停，避免卡住）
REM 资源管理器双击：不要填参数，结束时会 pause，方便你看结果

set "LOG=%~dp0data\crawl_log.txt"
if not exist "%~dp0data" mkdir "%~dp0data" 2>nul
echo.>>"%LOG%"
echo ===== START %date% %time% cwd=%cd% =====>>"%LOG%"

where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo [错误] 找不到 python 或 py。请安装 Python 并勾选「添加到 PATH」。
    echo [错误] 找不到 python>>"%LOG%"
    goto :END
  )
  set "PY=py"
) else (
  set "PY=python"
)

title 热搜三平台采集

echo ============================================
echo 热搜快照采集  %date% %time%
echo 当前目录: %cd%
echo 日志: %LOG%
echo ============================================

echo [1/3] 微博...
"%PY%" crawl_once.py
if errorlevel 1 (
  echo [提示] 微博失败，检查 WEIBO_COOKIE / 网络
  echo [1/3] weibo FAIL>>"%LOG%"
) else (
  echo [1/3] weibo OK>>"%LOG%"
)

echo [2/3] B站...
"%PY%" crawl_bilibili_once.py
if errorlevel 1 (
  echo [提示] B站失败
  echo [2/3] bilibili FAIL>>"%LOG%"
) else (
  echo [2/3] bilibili OK>>"%LOG%"
)

echo [3/3] 抖音...
"%PY%" crawl_douyin_once.py
if errorlevel 1 (
  echo [提示] 抖音失败，可试 DOUYIN_COOKIE
  echo [3/3] douyin FAIL>>"%LOG%"
) else (
  echo [3/3] douyin OK>>"%LOG%"
)

echo ============================================
echo 全部步骤已执行完毕。
echo If CSV files did not grow, read errors above or open: data\crawl_log.txt
echo ============================================
echo ===== END %date% %time% =====>>"%LOG%"

:END
endlocal
if /i "%~1"=="silent" exit /b 0
echo.
echo 按任意键关闭窗口...
pause >nul
exit /b 0
