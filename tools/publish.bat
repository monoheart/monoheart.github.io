@echo off
REM 一劳永逸入口：双击即 补封面 -> 生成页面 -> 发布到 GitHub Pages
cd /d "%~dp0.."
python tools\build.py --deploy
pause
