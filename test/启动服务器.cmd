@echo off
chcp 65001 >nul
echo ========================================
echo 课堂互动教学评测系统 - 启动脚本
echo ========================================
echo.

cd /d "%~dp0"

echo 正在启动服务器...
echo.
python app.py

pause
