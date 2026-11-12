@echo off
REM Connects your website's Agents section to the agents on this computer.
REM Keep this window open while you use it. Close it to stop.
cd /d "%~dp0"
start "" "https://jackhovanec07-glitch.github.io/test3/"
python agent-server.py
