@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ============================================================
REM  Sinh cau hinh MCP cho Claude Code TREN MAY NAY (portable).
REM  Tu dò duong dan tuyet doi cua thu muc + venv python, ghi .mcp.json
REM  va in lenh `claude mcp add`. Chay 1 lan sau khi copy thu muc sang
REM  may moi (duong dan bat ky deu duoc).
REM ============================================================

echo ============================================================
echo   Setup MCP cho Claude Code - MediaCrawler x DigiAds
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua co .venv. Chay start.bat truoc de tao moi truong roi chay lai.
    pause
    exit /b 1
)

set ROOT=%CD%
set PY=%ROOT%\.venv\Scripts\python.exe
set SCRIPT=%ROOT%\kit\mcp\mcp_mediacrawler.py

REM --- Ghi .mcp.json (project-scoped, duong dan tuyet doi may nay) ---
REM  JSON can dau \ escape thanh \\ -> dung python cho chac chan.
"%PY%" -c "import json,sys; py,script=sys.argv[1],sys.argv[2]; open('.mcp.json','w',encoding='utf-8').write(json.dumps({'mcpServers':{'mediacrawler':{'command':py,'args':[script],'env':{'MEDIACRAWLER_API':'http://127.0.0.1:8080'}}}}, ensure_ascii=False, indent=2))" "%PY%" "%SCRIPT%"

if errorlevel 1 (
    echo [LOI] Khong ghi duoc .mcp.json
    pause
    exit /b 1
)

echo [OK] Da ghi .mcp.json tai: %ROOT%\.mcp.json
echo.
echo   Neu mo Claude Code TAI thu muc nay, no se tu nhan MCP 'mediacrawler'
echo   (bam approve khi duoc hoi). Khong can lam gi them.
echo.
echo ------------------------------------------------------------
echo   HOAC dang ky thu cong (chay bat ky dau) - LOCAL stdio:
echo.
echo     claude mcp add mediacrawler -- "%PY%" "%SCRIPT%"
echo.
echo ------------------------------------------------------------
echo   REMOTE qua Tailscale (may khac ket noi vao may nay):
echo     1) Tren may nay chay:  start_mcp.bat        (mo HTTP 8765)
echo     2) Tren may khac chay:
echo        claude mcp add --transport http mediacrawler http://[TAILSCALE_IP]:8765/mcp
echo ------------------------------------------------------------
echo.
echo   NHO: MCP goi REST API cong 8080 - phai bat start.bat truoc khi dung.
echo ============================================================
pause
endlocal
