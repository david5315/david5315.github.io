@echo off
chcp 65001
title 课堂教学和作业系统启动服务 
echo 正在安装依赖包...
c:\python38\python.exe -m pip install --upgrade pip
C:\Python38\Scripts\pip install -r requirements38.txt
echo 正在启动Web服务...
C:\Python38\python app.py

echo  服务启动完成！
echo 按任意键停止服务...

pause >nul

taskkill /f /im python.exe >nul 2>&1

echo 服务已停止。