@echo off
REM Connects your website's Agents section to the agents on this computer.
REM Keep this window open while you use it. Close it to stop.
cd /d "%~dp0"
start "" /min cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8765/"
python agent-server.py
