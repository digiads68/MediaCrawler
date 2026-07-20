@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Mo Chrome rieng cho crawl thuc te (CDP debug port 9222)
echo ============================================================
echo.
echo   QUAN TRONG:
echo   - Day la Chrome RIENG (profile trang), KHONG dung Chrome hang ngay
echo     cua ban. Dang nhap/quet QR ngay trong cua so nay khi crawl.
echo   - Neu Chrome bao da chay / khong hien cua so moi: dong HET Chrome
echo     hien tai (Task Manager - End task moi dong chrome.exe), roi chay
echo     lai file nay.
echo   - Chrome mac dinh (profile that) TU CHAN cong debug vi ly do an
echo     toan - phai dung --user-data-dir rieng nhu duoi day thi cong 9222
echo     moi mo duoc.
echo.

set PROFILE_DIR=%~dp0browser_data\cdp_profile
if not exist "%PROFILE_DIR%" mkdir "%PROFILE_DIR%"

set BROWSER_EXE=
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set BROWSER_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe
if "%BROWSER_EXE%"=="" if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set BROWSER_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
if "%BROWSER_EXE%"=="" if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set BROWSER_EXE=%LocalAppData%\Google\Chrome\Application\chrome.exe
if "%BROWSER_EXE%"=="" if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set BROWSER_EXE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe
if "%BROWSER_EXE%"=="" if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set BROWSER_EXE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe

if "%BROWSER_EXE%"=="" (
    echo [LOI] Khong tim thay Chrome hoac Edge. Cai Chrome tu https://google.com/chrome
    echo       roi chay lai file nay.
    pause
    exit /b 1
)

echo   Dung: %BROWSER_EXE%
echo   Profile rieng: %PROFILE_DIR%
echo   Dang mo cong debug 9222 ...
echo.

start "" "%BROWSER_EXE%" --remote-debugging-port=9222 --user-data-dir="%PROFILE_DIR%" --no-first-run --no-default-browser-check

echo   Da mo. Chon 1 profile (hoac "Tiep tuc khong co tai khoan") trong cua so
echo   Chrome vua hien len, roi quay lai WebUI (http://localhost:8080) bam
echo   "Initiate Scan".
echo.
pause
endlocal
