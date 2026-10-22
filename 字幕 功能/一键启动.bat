@echo off
chcp 65001 >nul
title 拼音歌词字幕大师

cd /d "%~dp0"

echo ========================================================
echo        🎵 正在启动 拼音歌词字幕大师...
echo ========================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python！
    pause
    exit /b
)

python app.py
if %errorlevel% neq 0 (
    echo.
    echo 应用程序异常退出，请查看上方错误信息。
    pause
)
