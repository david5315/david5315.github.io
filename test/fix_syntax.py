# fix_syntax.py - 修复语法错误

with open('ai_services.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 修复 f-string 中的反斜杠问题
old_line = '''result += f"  - 字段列表：{', '.join([f\\"{i['type']}:{i['name'] or i['id']}\\" for i in form['inputs'][:5]])}\\n"'''

new_line = '''field_list = ', '.join([f"{i['type']}:{i['name'] or i['id']}" for i in form['inputs'][:5]])
            result += f"  - 字段列表：{field_list}\\n"'''

content = content.replace(old_line, new_line)

# 如果上面的替换没找到，尝试另一种方式
import re
pattern = r"result \+= f\"  - 字段列表：\{', '\.join\(\[f\\\".*?\\\" for i in form\['inputs'\]\[:5\]\]\)\}\\n\""

def replace_func(match):
    return '''field_list = ', '.join([f"{i['type']}:{i['name'] or i['id']}" for i in form['inputs'][:5]])
            result += f"  - 字段列表：{field_list}\\n"'''

content = re.sub(pattern, replace_func, content)

with open('ai_services.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('OK: Fixed syntax error')
