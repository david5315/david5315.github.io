import subprocess
import os

# 读取 index.html
path = r'D:\测试\exe\templates\teach\示例网站\课堂练习模式\index.html'
result = subprocess.run(
    ['cmd', '/c', 'type', path],
    capture_output=True,
    encoding='gbk'
)
if result.returncode == 0:
    print("文件内容 (前 3000 字符):")
    print(result.stdout[:3000])
else:
    print(f"错误：{result.stderr}")
