# fix_teacher_apis_simple.py
with open('teacher_apis.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 只修复路径，不改变函数结构
content = content.replace("base = os.path.realpath('templates')", "base = os.path.realpath(os.path.join(EXE_DIR, 'templates'))")
content = content.replace("base = os.path.realpath(os.path.join('templates', target_teacher))", "base = os.path.realpath(os.path.join(EXE_DIR, 'templates', target_teacher))")

with open('teacher_apis.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('OK: Fixed')
