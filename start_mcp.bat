@echo off
setlocal
cd /d "%~dp0"

REM ============================================================
REM  MCP server MediaCrawler - cho AI agent (Claude Code...) goi
REM ============================================================
REM  Cach dung:
REM    start_mcp.bat          -> che do HTTP cho Tailscale/remote (0.0.0.0:8765)
REM    start_mcp.bat local    -> in huong dan cau hinh stdio (khong can chay nen)
REM
REM  LUU Y: MCP goi lai REST API cua MediaCrawler (cong 8080), nen phai
REM  chay start.bat TRUOC (server 8080 dang bat).
REM ============================================================

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua co .venv. Chay start.bat truoc de tao moi truong.
    pause
    exit /b 1
)
set VENV_PY=.venv\Scripts\python.exe

if /I "%~1"=="local" goto :local_info

REM --- Che do HTTP (remote qua Tailscale) ---
set MCP_TRANSPORT=streamable-http
set MCP_HOST=0.0.0.0
set MCP_PORT=8765
if not "%~2"=="" set MCP_PORT=%~2

echo ============================================================
echo   MCP server (HTTP) cho ket noi tu xa qua Tailscale
echo ============================================================
echo   Endpoint MCP : http://0.0.0.0:%MCP_PORT%/mcp
echo   Backend API  : %MEDIACRAWLER_API%
echo   (mac dinh backend http://127.0.0.1:8080 - nho bat start.bat truoc)
echo.
echo   Tren may KHAC (co Tailscale), dang ky vao Claude Code:
for /f "delims=" %%i in ('where tailscale ^>nul 2^>nul ^&^& tailscale ip -4 2^>nul') do set TS_IP=%%i
if not "%TS_IP%"=="" (
    echo     claude mcp add --transport http mediacrawler http://%TS_IP%:%MCP_PORT%/mcp
) else (
    echo     claude mcp add --transport http mediacrawler http://[TAILSCALE_IP]:%MCP_PORT%/mcp
)
echo.
echo   Nhan Ctrl+C de dung.
echo ============================================================
echo.
"%VENV_PY%" kit\mcp\mcp_mediacrawler.py
pause
exit /b 0

:local_info
echo ============================================================
echo   Cau hinh MCP che do LOCAL (stdio) cho Claude Code cung may
echo ============================================================
echo   KHONG can chay nen - Claude Code se tu spawn tien trinh MCP.
echo   Chay setup_mcp.bat de sinh cau hinh (.mcp.json) tu dong,
echo   hoac dang ky thu cong:
echo.
echo     claude mcp add mediacrawler -- "%CD%\.venv\Scripts\python.exe" "%CD%\kit\mcp\mcp_mediacrawler.py"
echo.
echo   (Van can start.bat chay de co API 8080.)
echo ============================================================
pause
endlocal
