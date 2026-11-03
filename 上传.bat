@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PROXY=http://127.0.0.1:7897"
set "DEPLOY=%TEMP%\monoheart-deploy"
set "NO_PUSH=0"
if /i "%~1"=="--no-push" set "NO_PUSH=1"

echo ========================================
echo  monoheart - publish
echo ========================================
echo.

echo [1/5] Build site...
python -m mkdocs build --strict
if errorlevel 1 goto :fail

echo.
echo [2/5] Commit source...
git -c core.autocrlf=false add -A
if errorlevel 1 goto :fail
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "update articles %date% %time%"
    if errorlevel 1 goto :fail
) else (
    echo No source changes, skip commit.
)

echo.
echo [3/5] Push master...
if "%NO_PUSH%"=="1" (
    echo [skip] push master
) else (
    git -c http.proxy=%PROXY% -c https.proxy=%PROXY% push origin master
    if errorlevel 1 goto :fail
)

echo.
echo [4/5] Update main...
if exist "%DEPLOY%" (
    git worktree remove "%DEPLOY%" --force >nul 2>nul
    rmdir /s /q "%DEPLOY%" >nul 2>nul
)
git worktree add "%DEPLOY%" main
if errorlevel 1 goto :fail

git -C "%DEPLOY%" rm -rf . >nul
if errorlevel 1 goto :fail

xcopy "site\*" "%DEPLOY%\" /E /H /Y >nul
if errorlevel 1 goto :fail

type nul > "%DEPLOY%\.nojekyll"

git -C "%DEPLOY%" -c core.autocrlf=false add -A
if errorlevel 1 goto :fail
git -C "%DEPLOY%" commit -m "site %date% %time%"
if errorlevel 1 (
    echo No site changes, skip commit.
)

if "%NO_PUSH%"=="1" (
    echo [skip] push main
) else (
    git -C "%DEPLOY%" -c http.proxy=%PROXY% -c https.proxy=%PROXY% push origin main
    if errorlevel 1 goto :fail
)

git worktree remove "%DEPLOY%" --force >nul 2>nul

echo.
echo [5/5] Done.
echo https://monoheart.shop/
echo If the page is not updated, wait 1-2 minutes and press Ctrl+F5.
pause
exit /b 0

:fail
echo.
echo Publish failed. Check:
echo   1. Is the proxy running at 127.0.0.1:7897?
echo   2. The error message above.
echo.
pause
exit /b 1
