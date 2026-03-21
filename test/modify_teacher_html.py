# modify_teacher_html.py - 添加模板类型选择

with open('statics/teacher.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 在模态框中添加模板类型选择（在提示词输入框之前）
modal_addition = '''
                    <div class="mb-3">
                        <label class="form-label">生成类型</label>
                        <select class="form-select" id="generate-page-type">
                            <option value="new">🆕 生成新网页（根据要求创建全新页面）</option>
                            <option value="modify">✏️ 修改现有网页（保留原样式，只修改功能）</option>
                        </select>
                        <div class="form-text">
                            <i class="fas fa-info-circle me-1"></i>
                            选择"生成新网页"会根据参考文件创建全新页面；选择"修改现有网页"会保留原网页的样式和结构
                        </div>
                    </div>
'''

# 找到提示词输入框的位置并插入
prompt_input_marker = '<div class="mb-3">\n                        <label class="form-label">提示词/要求</label>'
if prompt_input_marker in content:
    content = content.replace(prompt_input_marker, modal_addition + '\n                    ' + prompt_input_marker)
    print('OK: Added template selector')
else:
    # 尝试另一种格式
    prompt_input_marker2 = '<div class="mb-3">\n                        <label class="form-label">ʾ/Ҫ</label>'
    if prompt_input_marker2 in content:
        content = content.replace(prompt_input_marker2, modal_addition + '\n                    ' + prompt_input_marker2)
        print('OK: Added template selector (encoded)')
    else:
        print('WARN: Could not find prompt input')

# 修改 JavaScript，添加 templateType 参数到 API 调用
old_api_call = '''const response = await fetch(`${API_BASE}/ai/generate-page`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt, targetFolder, fileName, referenceFiles })
                });'''

new_api_call = '''const templateType = document.getElementById('generate-page-type').value;
                
                const response = await fetch(`${API_BASE}/ai/generate-page`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        prompt, 
                        targetFolder, 
                        fileName, 
                        referenceFiles,
                        templateType  // 新增：模板类型
                    })
                });'''

if old_api_call in content:
    content = content.replace(old_api_call, new_api_call)
    print('OK: Modified API call')
else:
    print('WARN: Could not find API call')

# 写入文件
with open('statics/teacher.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('DONE')
