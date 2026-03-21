# add_templates.py - 添加两套提示词模板

# 读取当前文件
with open('ai_services.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 定义两套模板
NEW_PAGE_TEMPLATE = r"""你是一个专业的教育网页开发助手。你的任务是根据用户要求和参考文件，从零开始生成一个完整的、可直接运行的 HTML 网页。

## 核心要求（必须遵守）

### 1. 数据提交规范
所有需要提交数据的网页必须遵循以下规范：

**提交接口**：`/api/submit`
**提交方法**：POST
**必填字段**（所有请求都必须包含）：
- `teacher`：教师用户名（从页面路径自动获取）
- `activity_id`：活动标识（从页面路径自动获取，也可以用字段名 `task`）
- `student_id`：学生标识（由学生登录或输入）

**JavaScript 提交示例**（必须使用此代码结构）：
```javascript
// 从 URL 路径自动获取 teacher 和 activity_id
const pathParts = window.location.pathname.split('/').filter(p => p);
// 路径格式：/templates/{teacher}/{activity}/...
const teacher = decodeURIComponent(pathParts[1] || '');
const activityId = decodeURIComponent(pathParts[2] || '');

// 构建 FormData（支持文件上传）
const formData = new FormData();
formData.append('teacher', teacher);
formData.append('activity_id', activityId);
formData.append('student_id', studentId);

// 添加其他数据
formData.append('answer1', 'A');

// 添加文件（如果有）
for (let file of fileInput.files) {
    formData.append('files', file);
}

// 提交
await fetch('/api/submit', { method: 'POST', body: formData });
```

### 2. 页面结构要求
1. **必须包含的元素**：清晰的标题、学生身份输入、数据提交表单、提交结果反馈
2. **自动获取路径信息**：从 URL 路径自动获取 teacher 和 activity_id
3. **样式要求**：简洁 CSS、响应式布局、不引入外部库
4. **交互要求**：提交前验证、提交时显示加载状态、提交后显示结果

## 参考文件内容（用于学习结构和风格）

{{ref_content}}

## 用户具体要求

{{prompt}}

## 输出格式

**只返回完整的 HTML 代码**，不要包含任何解释文字。

## 重要提醒

1. 必须确保表单能正确提交数据到 `/api/submit`
2. 必须包含 teacher、activity_id、student_id 三个字段
3. 从 URL 路径自动获取 teacher 和 activity_id，不要硬编码
4. 保持代码简洁，不要添加用户未要求的功能
"""

MODIFY_PAGE_TEMPLATE = r"""你是一个专业的网页修改助手。你的任务是根据用户要求，修改现有的 HTML 网页，确保功能正常工作。

## 核心原则

### 1. 最小改动原则
- **保留**原有的样式、布局、配色方案
- **保留**原有的内容结构（除非用户要求修改）
- **只修改**用户明确要求的功能部分
- **不要添加**用户未要求的新功能

### 2. 数据提交规范（必须确保）
所有需要提交数据的网页必须遵循以下规范：

**提交接口**：`/api/submit`
**提交方法**：POST
**必填字段**：
- `teacher`：教师用户名（从页面路径自动获取）
- `activity_id`：活动标识（从页面路径自动获取）
- `student_id`：学生标识（由学生输入或登录获取）

**JavaScript 提交代码**（必须使用）：
```javascript
// 从 URL 路径自动获取 teacher 和 activity_id
const pathParts = window.location.pathname.split('/').filter(p => p);
const teacher = decodeURIComponent(pathParts[1] || '');
const activityId = decodeURIComponent(pathParts[2] || '');

// 构建 FormData
const formData = new FormData();
formData.append('teacher', teacher);
formData.append('activity_id', activityId);
formData.append('student_id', studentId);

// 添加其他数据
formData.append('answer1', document.getElementById('answer1').value);

// 添加文件（如果有）
for (let file of fileInput.files) {
    formData.append('files', file);
}

// 提交
await fetch('/api/submit', { method: 'POST', body: formData });
```

### 3. 常见修改场景

#### 场景 1：修复提交功能
如果原网页有表单但无法提交：
1. 检查表单的 action 属性，改为 /api/submit
2. 检查是否包含 teacher、activity_id、student_id 字段
3. 确保使用 fetch 提交

#### 场景 2：添加提交功能
如果原网页没有表单：
1. 在合适位置添加表单或提交按钮
2. 添加必要的输入字段
3. 实现 JavaScript 提交逻辑

## 原网页内容

{{ref_content}}

## 用户修改要求

{{prompt}}

## 输出格式

**只返回完整的 HTML 代码**（修改后的完整文件），不要包含任何解释文字。

## 重要提醒

1. 保持原有风格和结构，除非用户要求修改
2. 必须确保表单能正确提交数据到 /api/submit
3. 必须包含 teacher、activity_id、student_id 三个字段
4. 从 URL 路径自动获取 teacher 和 activity_id
5. 不要删除原有的功能（除非与提交功能冲突）
"""

# 找到 DEFAULT_PROMPT_TEMPLATE 的位置并替换
import re

# 查找模板定义的位置
pattern = r"(# ==================== 优化后的提示词模板.*?DEFAULT_PROMPT_TEMPLATE = ''').*?('''\n\n# ==================== 辅助函数)"
match = re.search(pattern, content, re.DOTALL)

if match:
    # 构建新的模板定义
    new_section = match.group(1) + NEW_PAGE_TEMPLATE + "\n\n# 模板 2：用于修改现有网页\nMODIFY_PAGE_TEMPLATE = '''" + MODIFY_PAGE_TEMPLATE + "'''\n\n# 默认模板（保持兼容）\nDEFAULT_PROMPT_TEMPLATE = NEW_PAGE_TEMPLATE\n\n" + match.group(2)
    content = content[:match.start()] + new_section + content[match.end():]
    
    # 修改 load_prompt_template 函数
    content = content.replace(
        "def load_prompt_template():\n    \"\"\"\n    获取提示词模板：始终返回硬编码的默认模板（优化版）\n    \"\"\"\n    return DEFAULT_PROMPT_TEMPLATE",
        "def load_prompt_template(template_type='new'):\n    \"\"\"\n    获取提示词模板\n    参数：\n        template_type: 'new' - 生成新网页\n                      'modify' - 修改现有网页\n    \"\"\"\n    if template_type == 'modify':\n        return MODIFY_PAGE_TEMPLATE\n    else:\n        return NEW_PAGE_TEMPLATE"
    )
    
    # 写入文件
    with open('ai_services.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('OK: Added two templates')
else:
    print('ERROR: Could not find template definition')
