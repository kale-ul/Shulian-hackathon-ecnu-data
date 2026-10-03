@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo   AI Big-Data Platform  -  One-Click Launcher
echo ============================================================
echo.

REM ---- 0. check we are fully extracted (not running inside zip preview) ----
if not exist "%~dp0requirements_clean.txt" goto :noextract

REM ---- 1. check python ----
python --version >nul 2>&1
if errorlevel 1 goto :nopython
echo   [1/3] Python found:
python --version

REM ---- 2. venv / install ----
if exist "%~dp0.venv\Scripts\python.exe" goto :venvready
echo.
echo   [2/3] First run: creating venv, installing deps (2-4 min)...
echo.
python -m venv "%~dp0.venv"
if errorlevel 1 goto :venvfail
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1

REM try multiple mirrors in order; official PyPI last (most reliable)
echo.
echo     Install [2/3] trying Tencent mirror ...
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements_clean.txt" --index-url https://mirrors.cloud.tencent.com/pypi/simple
if not errorlevel 1 goto :venvready
echo     Tencent failed, trying Aliyun ...
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements_clean.txt" --index-url https://mirrors.aliyun.com/pypi/simple
if not errorlevel 1 goto :venvready
echo     Aliyun failed, trying official PyPI ...
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements_clean.txt"
if not errorlevel 1 goto :venvready
goto :instfail

:venvready
echo   [2/3] Environment ready.

REM ---- 3. start services in background ----
echo.
echo   [3/3] Starting platform, please wait (first run 30-60s)...
echo.

REM start Streamlit console (port 8603) in background
start "platform-streamlit" /min cmd /c ""%~dp0.venv\Scripts\python.exe" -m streamlit run "%~dp0app\console.py" --server.port 8603 --server.headless true --server.enableXsrfProtection=false --server.enableCORS=false"

REM start unified gateway (port 8610: human + machine)
start "platform-gateway" /min cmd /c ""%~dp0.venv\Scripts\python.exe" -m aiplatform.gateway"

REM start MCP streamable-http (port 8602, proxied by gateway under /mcp)
start "platform-mcp" /min cmd /c ""%~dp0.venv\Scripts\python.exe" aiplatform\mcp_server.py --http --port 8602"

REM ---- wait until console is ready (max 90s), then open browser ----
echo.
echo   Waiting for services to be ready...
set /a tries=0
:waitloop
timeout /t 3 /nobreak >nul
curl -s -o nul http://127.0.0.1:8603 >nul 2>&1
if not errorlevel 1 goto :open
set /a tries+=1
if %tries% lss 30 goto :waitloop

echo   [Warning] Console not responding after 90s. Opening browser anyway...
goto :open

:open
echo.
echo   ============================================================
echo     Platform is UP — 统一入口(人面+机面同域)：
echo     Console:  http://localhost:8610
echo     AI API  :  http://localhost:8610/v1/...   (llms.txt 自举: /llms.txt)
echo   ============================================================
echo.
REM Force-open browser via Edge absolute path (most reliable on Windows)
set "BROWSER=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%BROWSER%" set "BROWSER=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not exist "%BROWSER%" set "BROWSER=start \"\" http://localhost:8610"
if exist "%BROWSER%" start "" "%BROWSER%" "http://localhost:8610"
echo.
echo   If your browser did not open, copy this into your browser:
echo   ------------------------------------------------------------------
echo      http://localhost:8610
echo   ------------------------------------------------------------------
echo.
echo   (You can now close this launcher window. To STOP the platform,
echo    close the two small minimized windows.)
timeout /t 8 /nobreak >nul
echo   Launcher done. You can close this window anytime.
pause>nul
goto :end

:nopython
echo   [ERROR] Python not found. Install Python 3.10+ from https://python.org
echo           and check "Add Python to PATH".
pause
goto :end

:noextract
echo.
echo   [ERROR] This launcher is running INSIDE the compressed archive.
echo.
echo   You opened the .zip without extracting it first (360zip preview mode).
echo.
echo   Please do these 3 steps:
echo     1. Right-click the .zip  -^>  "Extract to current folder"
echo        (解压到当前文件夹 / 解压到指定文件夹)
echo     2. Open the EXTRACTED folder  (NOT the zip)
echo     3. Double-click 启动平台.bat  inside it
echo.
echo   Do NOT double-click the .bat while the zip is still a .zip file.
echo.
pause
goto :end

:venvfail
echo   [ERROR] Failed to create virtual environment.
pause
goto :end

:instfail
echo   [ERROR] Failed to install dependencies. Check your network.
pause
goto :end

:end
exit /b
