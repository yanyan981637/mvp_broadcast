@echo off
chcp 65001 >nul
REM 這個批次檔會在當前資料夾執行 live_broadcast_keyword.py
REM 自動啟動互動模式（不帶任何參數）
python live_broadcast_keyword.py
pause
