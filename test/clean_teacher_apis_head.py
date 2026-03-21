# 修复 teacher_apis.py 的 safe_join_path 函数

with open('teacher_apis.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 safe_join_path 函数开始
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if 'def safe_join_path(' in line:
        start_idx = i
    if start_idx is not None and line.strip().startswith('def ') and 'safe_join_path' not in line:
        end_idx = i
        break

if start_idx is None:
    print('Error: safe_join_path function not found')
    exit(1)

# 新的 safe_join_path 函数
new_func = '''def safe_join_path(current_teacher, subpath, target_teacher=None):
    """
    安全拼接路径，防止路径遍历。
    如果 target_teacher 为空且当前用户是管理员，则基础为 templates 目录。
    否则基础为 templates/target_teacher 或 templates/current_teacher。
    """
    templates_base = os.path.join(EXE_DIR, 'templates')
    if is_admin() and not target_teacher:
        base = os.path.realpath(templates_base)
    else:
        if not target_teacher:
            target_teacher = current_teacher
        base = os.path.realpath(os.path.join(templates_base, target_teacher))
    
    target = os.path.realpath(os.path.join(base, subpath))
    if not target.startswith(base):
        return None
    return target

'''

# 替换函数
if end_idx:
    new_lines = lines[:start_idx] + [new_func] + lines[end_idx:]
else:
    new_lines = lines[:start_idx] + [new_func]

with open('teacher_apis.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('OK: safe_join_path fixed')
