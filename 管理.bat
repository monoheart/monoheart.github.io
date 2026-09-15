@echo off
REM 双击打开本地管理台（书影音/文章），关闭窗口即停止
cd /d "%~dp0"
python tools\app.py
pause
