# fix_api_template_type.py - 修改 API 接收 templateType 参数

with open('ai_services.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 修改 ai_generate_page 函数，接收 templateType 参数
old_code = '''        data = request.json
        prompt = data.get('prompt', '')
        target_folder = data.get('targetFolder', '').strip()
        file_name = data.get('fileName', '').strip()
        reference_files = data.get('referenceFiles', [])'''

new_code = '''        data = request.json
        prompt = data.get('prompt', '')
        target_folder = data.get('targetFolder', '').strip()
        file_name = data.get('fileName', '').strip()
        reference_files = data.get('referenceFiles', [])
        template_type = data.get('templateType', 'new')  # 新增：模板类型'''

content = content.replace(old_code, new_code)

# 修改调用 load_prompt_template 的地方
old_load = '''        # ==================== 方案 1：使用优化后的提示词模板 ====================
        template = load_prompt_template()'''

new_load = '''        # ==================== 根据类型选择提示词模板 ====================
        template = load_prompt_template(template_type)  # 传入模板类型'''

content = content.replace(old_load, new_load)

# 写入文件
with open('ai_services.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('OK: Modified API to accept templateType')
