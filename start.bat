@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   MediaCrawler x DigiAds Kit - Local Launcher
echo ============================================================
echo.

REM ---------------------------------------------------------------
REM 1. Tim Python (uu tien lenh python, fallback py -3)
REM ---------------------------------------------------------------
set PY_CMD=
where python >nul 2>nul
if not errorlevel 1 set PY_CMD=python
if not "%PY_CMD%"=="" goto :have_python
where py >nul 2>nul
if not errorlevel 1 set PY_CMD=py -3
if not "%PY_CMD%"=="" goto :have_python
echo [LOI] Khong tim thay Python. Cai Python 3.11+ tu https://python.org
echo       roi chay lai file nay.
pause
exit /b 1

:have_python

REM ---------------------------------------------------------------
REM 2. Tao virtual environment (neu chua co)
REM ---------------------------------------------------------------
if exist ".venv\Scripts\python.exe" goto :venv_ready
echo [1/6] Tao virtual environment...
%PY_CMD% -m venv .venv
if errorlevel 1 (
    echo [LOI] Tao venv that bai.
    pause
    exit /b 1
)
goto :venv_done

:venv_ready
echo [1/6] Virtual environment - OK.

:venv_done
set VENV_PY=.venv\Scripts\python.exe

REM ---------------------------------------------------------------
REM 3. Cai dependencies (requirements.txt + goi cua DigiAds Kit)
REM    Chay moi lan start - pip tu bo qua goi da du, nen nhanh.
REM ---------------------------------------------------------------
echo [2/6] Kiem tra / cai dependencies...
"%VENV_PY%" -m pip install --quiet --upgrade pip
"%VENV_PY%" -m pip install --quiet -r requirements.txt anthropic supabase arq "mcp[cli]"
if errorlevel 1 (
    echo [LOI] Cai dependencies that bai. Kiem tra ket noi mang roi chay lai.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM 4. Cai uv (crawler_manager.py can lenh uv run de khoi dong crawl thuc te)
REM ---------------------------------------------------------------
where uv >nul 2>nul
if errorlevel 1 goto :install_uv
echo [3/6] uv - OK.
goto :uv_done

:install_uv
echo [3/6] Chua co uv - dang cai qua winget...
where winget >nul 2>nul
if errorlevel 1 goto :check_uv_result
winget install --id astral-sh.uv --source winget --silent --accept-package-agreements --accept-source-agreements >nul 2>nul

:check_uv_result
where uv >nul 2>nul
if errorlevel 1 goto :uv_install_failed
echo       uv da cai xong - can mo lai Command Prompt moi de nhan PATH.
goto :uv_done

:uv_install_failed
echo [CANH BAO] Khong tu cai duoc uv. Nut Initiate Scan tren WebUI se loi.
echo            Cai thu cong: https://docs.astral.sh/uv/getting-started/installation/

:uv_done
REM Bat de lenh uv run dung venv co san, khong tu tai Python / sync mirror rieng
set UV_PYTHON_DOWNLOADS=never
set UV_NO_SYNC=1

REM ---------------------------------------------------------------
REM 5. Build WebUI (neu chua build)
REM ---------------------------------------------------------------
if exist "api\webui\index.html" goto :webui_ready
echo [4/6] Build WebUI (lan dau, can vai chuc giay)...
where npm >nul 2>nul
if errorlevel 1 goto :webui_no_npm
pushd webui
call npm install
call npm run build
popd
goto :webui_done

:webui_no_npm
echo [CANH BAO] Chua co Node.js/npm - bo qua build WebUI.
echo            Cai Node 18+ tu https://nodejs.org roi chay lai file nay neu can WebUI.
goto :webui_done

:webui_ready
echo [4/6] WebUI - da build, bo qua.

:webui_done

REM ---------------------------------------------------------------
REM 6. Tao .env tu .env.example (neu chua co)
REM ---------------------------------------------------------------
if exist ".env" goto :env_ready
echo [5/6] Tao .env tu .env.example - dien API key thuc te vao .env neu dung tinh nang AI/Supabase.
copy /y ".env.example" ".env" >nul
goto :env_done

:env_ready
echo [5/6] .env - da co, bo qua.

:env_done

REM ---------------------------------------------------------------
REM 7. Lay dia chi Tailscale (chi de hien thi, khong bat buoc)
REM ---------------------------------------------------------------
set TS_IP=
where tailscale >nul 2>nul
if errorlevel 1 goto :no_tailscale
for /f "delims=" %%i in ('tailscale ip -4') do set TS_IP=%%i

:no_tailscale
echo [6/6] Khoi dong server tren cong 8080 (0.0.0.0 - cho phep may khac vao qua Tailscale)...
echo.
echo   Truy cap local     : http://localhost:8080
if "%TS_IP%"=="" goto :no_ts_ip
echo   Truy cap Tailscale : http://%TS_IP%:8080
goto :ts_ip_done

:no_ts_ip
echo   Tailscale chua phat hien - chay lenh tailscale ip -4 hoac xem Tailscale
echo   admin console de lay dia chi/MagicDNS cho may nay.

:ts_ip_done
echo.
echo   Lan dau tu may khac chua vao duoc? Mo Command Prompt (Run as Administrator)
echo   tren MAY NAY roi chay:
echo     netsh advfirewall firewall add rule name=MediaCrawlerAPI dir=in action=allow protocol=TCP localport=8080
echo.
echo   Muon crawl du lieu THAT (khong chi xem WebUI): mo them start_browser_cdp.bat
echo   (mo Chrome rieng, dang nhap/quet QR o do) TRUOC KHI bam nut Initiate Scan.
echo.
echo   Nhan Ctrl+C de dung server.
echo ============================================================
echo.

"%VENV_PY%" -m uvicorn api.main:app --host 0.0.0.0 --port 8080

endlocal
