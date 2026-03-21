@echo off
chcp 65001
title 课堂教学和作业系统启动服务 
echo 正在安装依赖包...
D:\Users\Administrator\AppData\Local\Programs\Python\Python313\Scripts\pip install -r requirements.txt
echo 正在启动Web服务...
set DASHSCOPE_API_KEY=sk-81d5a28abec94bc6bd9dbbe27342980f
D:\Users\Administrator\AppData\Local\Programs\Python\Python313\python app.py

echo  服务启动完成！
echo 按任意键停止服务...

pause >nul

taskkill /f /im python.exe >nul 2>&1

echo 服务已停止。