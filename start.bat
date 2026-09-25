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
REM 2. Tao / kiem tra virtual environment
REM    Quan trong: .venv dong bo qua OneDrive tu MAY KHAC se hong
REM    (pyvenv.cfg tro ve duong dan Python may cu). Vi vay khong chi
REM    kiem tra ton tai thu muc - phai chay thu; hong thi tao lai.
REM ---------------------------------------------------------------
if not exist ".venv\Scripts\python.exe" goto :venv_create
".venv\Scripts\python.exe" -c "import sys" >nul 2>nul
if errorlevel 1 goto :venv_broken
echo [1/7] Virtual environment - OK.
goto :venv_done

:venv_broken
echo [1/7] .venv hong (co the do dong bo tu may khac) - tao lai...
rmdir /s /q ".venv" >nul 2>nul
goto :venv_make

:venv_create
echo [1/7] Tao virtual environment...

:venv_make
%PY_CMD% -m venv .venv
if errorlevel 1 (
    echo [LOI] Tao venv that bai.
    pause
    exit /b 1
)

:venv_done
set VENV_PY=.venv\Scripts\python.exe

REM ---------------------------------------------------------------
REM 3. Cai dependencies (requirements.txt + goi cua DigiAds Kit)
REM    Chay moi lan start - pip tu bo qua goi da du, nen nhanh.
REM ---------------------------------------------------------------
echo [2/7] Kiem tra / cai dependencies...
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
echo [3/7] uv - OK.
goto :uv_done

:install_uv
echo [3/7] Chua co uv - dang cai qua winget...
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
REM 5. Build WebUI (chua build, HOAC ma nguon webui moi hon ban build -
REM    vd. vua cap nhat tu upstream / sua giao dien kit)
REM ---------------------------------------------------------------
if not exist "api\webui\index.html" goto :webui_build
"%VENV_PY%" -c "import pathlib,sys; b=pathlib.Path('api/webui/index.html').stat().st_mtime; w=pathlib.Path('webui'); fs=[f for f in w.joinpath('src').rglob('*') if f.is_file()]+[w/n for n in ('index.html','package.json','vite.config.ts') if (w/n).exists()]; sys.exit(1 if any(f.stat().st_mtime>b for f in fs) else 0)"
if errorlevel 1 goto :webui_rebuild
goto :webui_ready

:webui_rebuild
echo [4/7] Ma nguon WebUI moi hon ban build - build lai...
goto :webui_run

:webui_build
echo [4/7] Build WebUI (lan dau, can vai chuc giay)...

:webui_run
where npm >nul 2>nul
if errorlevel 1 goto :webui_no_npm
pushd webui
call npm install
if errorlevel 1 goto :webui_build_failed
call npm run build
if errorlevel 1 goto :webui_build_failed
popd
goto :webui_done

:webui_build_failed
popd
echo [CANH BAO] Build WebUI that bai - WebUI co the la ban cu. Xem loi npm ben tren.
goto :webui_done

:webui_no_npm
echo [CANH BAO] Chua co Node.js/npm - bo qua build WebUI.
echo            Cai Node 18+ tu https://nodejs.org roi chay lai file nay neu can WebUI.
goto :webui_done

:webui_ready
echo [4/7] WebUI - da build, bo qua.

:webui_done

REM ---------------------------------------------------------------
REM 6. Tao .env tu .env.example (neu chua co)
REM ---------------------------------------------------------------
if exist ".env" goto :env_ready
echo [5/7] Tao .env tu .env.example - dien API key thuc te vao .env neu dung tinh nang AI/Supabase.
copy /y ".env.example" ".env" >nul
goto :env_done

:env_ready
echo [5/7] .env - da co, bo qua.

:env_done

REM ---------------------------------------------------------------
REM 7. ffmpeg (tuy chon) - bo tai media moi cua upstream dung ffmpeg de
REM    ghep hinh+tieng Bilibili (DASH, chat luong cao). Khong co ffmpeg
REM    van chay, chi tu ha xuong link mp4 chat luong thap. Khong tu cai.
REM ---------------------------------------------------------------
where ffmpeg >nul 2>nul
if errorlevel 1 goto :no_ffmpeg
echo [6/7] ffmpeg - OK.
goto :ffmpeg_done

:no_ffmpeg
echo [6/7] [TUY CHON] Chua co ffmpeg - tai video Bilibili se o chat luong thap.
echo       Muon chat luong cao: winget install --id Gyan.FFmpeg  (roi mo lai cua so)

:ffmpeg_done

REM ---------------------------------------------------------------
REM 8. Lay dia chi Tailscale (chi de hien thi, khong bat buoc)
REM ---------------------------------------------------------------
set TS_IP=
where tailscale >nul 2>nul
if errorlevel 1 goto :no_tailscale
for /f "delims=" %%i in ('tailscale ip -4') do set TS_IP=%%i

:no_tailscale
echo [7/7] Khoi dong server tren cong 8080 (0.0.0.0 - cho phep may khac vao qua Tailscale)...
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

echo.
echo ============================================================
echo   Server da dung (nhan Ctrl+C hoac gap loi ben tren).
echo   Neu vua thay dong loi mau do, doc ky va bao lai cho nguoi ho tro.
echo ============================================================
pause

endlocal
