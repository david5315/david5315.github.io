# fix_teacher_apis.py
import re

with open('teacher_apis.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 修复 safe_join_path 函数
old = "base = os.path.realpath('templates')"
new = "base = os.path.realpath(os.path.join(EXE_DIR, 'templates'))"
content = content.replace(old, new)

old2 = "base = os.path.realpath(os.path.join('templates', target_teacher))"
new2 = "base = os.path.realpath(os.path.join(EXE_DIR, 'templates', target_teacher))"
content = content.replace(old2, new2)

with open('teacher_apis.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('OK: safe_join_path fixed')
