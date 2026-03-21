# Rebuild teacher_apis.py
import re

# 读取当前文件
with open('teacher_apis.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 safe_join_path 函数并修复
new_lines = []
skip_until_next_def = False
templates_base_added = False

for i, line in enumerate(lines):
    # 检测是否进入 safe_join_path 函数
    if 'def safe_join_path(' in line:
        new_lines.append(line)
        templates_base_added = False
        continue
    
    # 在函数文档字符串后添加 templates_base
    if not templates_base_added and '"""' in line and len(new_lines) > 0 and 'safe_join_path' in ''.join(new_lines[-5:]):
        new_lines.append(line)
        new_lines.append("    templates_base = os.path.join(EXE_DIR, 'templates')\n")
        templates_base_added = True
        continue
    
    # 跳过重复的 templates_base 行
    if 'templates_base = os.path.join(EXE_DIR' in line:
        continue
    
    # 修复路径
    if "base = os.path.realpath('templates')" in line:
        line = line.replace("base = os.path.realpath('templates')", "base = os.path.realpath(templates_base)")
    
    if "base = os.path.realpath(os.path.join('templates', target_teacher))" in line:
        line = line.replace("base = os.path.realpath(os.path.join('templates', target_teacher))", "base = os.path.realpath(os.path.join(templates_base, target_teacher))")
    
    new_lines.append(line)

# 写入修复后的文件
with open('teacher_apis.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('OK: Rebuilt')
