import os
import shutil
import zipfile
from datetime import datetime

# 源目录和目标路径
source_dir = r"D:\测试\quickforge3.8\templates\teach"
output_zip = f"C:/Users/Administrator/.openclaw/workspace/QuickForge_Templates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

print("=" * 60)
print("创建部署包用于向日葵传输")
print("=" * 60)

# 检查源目录是否存在
if not os.path.exists(source_dir):
    print(f"[ERROR] 源目录不存在：{source_dir}")
    exit(1)

# 统计文件
files = []
total_size = 0

for root, dirs, filenames in os.walk(source_dir):
    for filename in filenames:
        filepath = os.path.join(root, filename)
        files.append(filepath)
        total_size += os.path.getsize(filepath)

# 创建 ZIP 压缩包
print(f"\n[INFO] 正在打包 {len(files)} 个文件...")
with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for filepath in files:
        # 计算相对路径
        arcname = os.path.relpath(filepath, source_dir)
        zipf.write(filepath, arcname)
        
print(f"\n[OK] 压缩包已创建:")
print(f"     文件：{output_zip}")
print(f"     数量：{len(files)} 个文件")
print(f"     大小：{round(total_size / 1024, 2)} KB")
print(f"     压缩后：约 {round(total_size / 5 / 1024, 2)} KB (预估)")
print(f"\n[INFO] 请使用向日葵将此文件发送到目标机器")
print(f"      并在 Web 发布目录解压")
