# ai_services.py - AI 服务模块，配置完全硬编码在内存中，不再读写文件
# 优化版本：改进提示词模板和参考文件处理逻辑
from flask import Blueprint, request, jsonify
import base64
import io
import time
import re
import json
import requests
import ssl
from urllib3 import poolmanager
from datetime import datetime
import subprocess
import tempfile
import os
import sys
import uuid
import copy

from data_manager import (
    get_current_teacher, get_teacher_data, update_teacher_data,
    get_assignment_file_dir, save_task_meta, get_current_user_info,
    decrease_remaining_uses, get_shared_data, update_shared_data,
    is_admin
)

ai_bp = Blueprint('ai', __name__)

# 全局配置缓存（内存中）
_ai_config = None

# ==================== 硬编码的默认配置 ====================
DEFAULT_AI_CONFIG = {
    "master_key": "",
    "temp_key": "sk-81d5a28abec94bc6bd9dbbe27342980f",
    "temp_key_expiry": "",
    "remote_key": "quickforgeclient-00001",
    "expiry_date": "",
    "remaining_uses": 19,
    "text_model": {
        "api_key": "",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen3.5-flash",
        "available_models": [
            "deepseek-v3.2", 
            "qwen-vl-max-latest",
            "qwen3.5-plus",
            "qwen3.5-Plus-2026-02-15",
            "Qwen-Omni-Turbo",
            "Qwen-Omni-Turbo-Latest"
        ]
    },
    "image_model": {
        "api_key": "",
        "base_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        "model": "qwen-image-plus",
        "available_models": [
            "Qwen-Image-Plus"
        ]
    },
    "site_setup": {
        "quickforge_URL": "http://ai.njschool.cn:9992",
        "public_file_for_teacher": "true",
        "quickforge_version": "quickforge"
    },
    "logged_user_key": ""
}

# ==================== 从环境变量读取敏感配置并覆盖默认值 ====================
_env_master_key = os.environ.get('AI_MASTER_KEY', '')
_env_temp_key = os.environ.get('AI_TEMP_KEY', '')
_env_remote_key = os.environ.get('AI_REMOTE_KEY', '')
_env_temp_key_expiry = os.environ.get('AI_TEMP_KEY_EXPIRY', '')

if _env_master_key:
    DEFAULT_AI_CONFIG['master_key'] = _env_master_key
if _env_temp_key:
    DEFAULT_AI_CONFIG['temp_key'] = _env_temp_key
if _env_remote_key:
    DEFAULT_AI_CONFIG['remote_key'] = _env_remote_key
if _env_temp_key_expiry:
    DEFAULT_AI_CONFIG['temp_key_expiry'] = _env_temp_key_expiry

_env_version = os.environ.get('AI_QUICKFORGE_VERSION', '')
if _env_version:
    DEFAULT_AI_CONFIG['site_setup']['quickforge_version'] = _env_version

# ==================== 优化后的提示词模板（方案 1） ====================
DEFAULT_PROMPT_TEMPLATE = '''你是一个专业的教育网页开发助手。你的任务是根据用户要求和参考文件，生成或修改一个完整的、可直接运行的 HTML 网页。

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
formData.append('student_id', studentId); // 从输入框或登录信息获取

// 添加其他数据
formData.append('answer1', 'A');
formData.append('score', '100');

// 添加文件（如果有）
for (let file of fileInput.files) {
    formData.append('files', file);
}

// 提交
await fetch('/api/submit', { method: 'POST', body: formData });
```

**纯 JSON 提交示例**（无文件上传时）：
```javascript
await fetch('/api/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        teacher: teacher,
        activity_id: activityId,
        student_id: studentId,
        answer1: 'A',
        score: 100
    })
});
```

### 2. 数据查询接口（如果需要展示统计）
**接口**：`/api/submissions`
**方法**：GET
**参数**：
- `teacher`（必选）：教师用户名
- `activity_id`（可选）：筛选指定活动
- `student_id`（可选）：筛选指定学生
- `limit`（可选）：返回条数（默认 100）
- `offset`（可选）：分页偏移（默认 0）

**响应格式**：
```json
{
  "success": true,
  "total": 200,
  "submissions": [
    {
      "teacher": "张三",
      "activity_id": "course_001",
      "student_id": "S001",
      "answer1": "A",
      "_server_timestamp": "2025-03-21T14:30:00"
    }
  ]
}
```

### 3. 文件访问
上传的文件可通过 `/templates/{teacher}/{filename}` 直接访问。

## 生成要求

### 页面结构
1. **必须包含的元素**：
   - 清晰的标题
   - 学生身份输入（学号输入框或登录功能）
   - 数据提交表单（如果有交互）
   - 提交结果反馈（成功/失败提示）

2. **自动获取路径信息**（必须实现）：
```javascript
// 页面加载时自动获取 teacher 和 activity_id
const pathParts = window.location.pathname.split('/').filter(p => p);
const teacher = decodeURIComponent(pathParts[1] || '');
const activityId = decodeURIComponent(pathParts[2] || '');
```

3. **样式要求**：
   - 使用简洁的 CSS（可内联）
   - 响应式布局，适配手机和电脑
   - 不要引入外部 CSS/JS 库（除非必要）

4. **交互要求**：
   - 提交前验证必填字段
   - 提交时显示加载状态
   - 提交后显示成功/失败提示
   - 错误处理友好

## 参考文件内容

{{ref_content}}

## 用户具体要求

{{prompt}}

## 输出格式

**只返回完整的 HTML 代码**，不要包含任何解释文字。代码结构：
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>页面标题</title>
    <style>
        /* 内联 CSS */
    </style>
</head>
<body>
    <!-- 页面内容 -->
    <script>
        // JavaScript 代码
    </script>
</body>
</html>
```

## 重要提醒

1. **必须确保表单能正确提交数据到 `/api/submit`**
2. **必须包含 `teacher`、`activity_id`、`student_id` 三个字段**
3. **从 URL 路径自动获取 teacher 和 activity_id，不要硬编码**
4. **保持代码简洁，不要添加用户未要求的功能**
5. **如果参考文件中有表单，优先参考其结构**
'''

# ==================== 辅助函数：安全文件名 ====================
def safe_filename(filename, default='unnamed'):
    """
    生成安全的文件名，保留中文、字母、数字、下划线、连字符和点，
    并防止路径遍历。
    """
    filename = os.path.basename(filename)
    filename = re.sub(r'[^\w\u4e00-\u9fa5.-]', '_', filename)
    filename = filename.lstrip('.')
    if not filename:
        filename = default
    return filename


# ==================== 方案 2：智能提取参考文件关键信息 ====================
def extract_html_key_info(html_content, filename):
    """
    从 HTML 文件中提取关键信息，避免 AI 被大量代码淹没
    """
    key_info = {
        'filename': filename,
        'has_form': False,
        'form_count': 0,
        'input_count': 0,
        'forms': [],
        'scripts': [],
        'styles': [],
        'title': ''
    }
    
    # 提取标题
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
    if title_match:
        key_info['title'] = title_match.group(1).strip()
    
    # 提取所有表单
    forms = re.findall(r'<form[^>]*>.*?</form>', html_content, re.IGNORECASE | re.DOTALL)
    key_info['form_count'] = len(forms)
    key_info['has_form'] = len(forms) > 0
    
    for i, form in enumerate(forms):
        form_info = {
            'index': i,
            'action': '',
            'method': '',
            'inputs': [],
            'code_preview': ''
        }
        
        # 提取 action 和 method
        action_match = re.search(r'action=["\']([^"\']*)["\']', form, re.IGNORECASE)
        if action_match:
            form_info['action'] = action_match.group(1)
        
        method_match = re.search(r'method=["\']([^"\']*)["\']', form, re.IGNORECASE)
        if method_match:
            form_info['method'] = method_match.group(1).upper()
        
        # 提取所有输入字段
        inputs = re.findall(r'<input[^>]*>', form, re.IGNORECASE)
        selects = re.findall(r'<select[^>]*>.*?</select>', form, re.IGNORECASE | re.DOTALL)
        textareas = re.findall(r'<textarea[^>]*>.*?</textarea>', form, re.IGNORECASE | re.DOTALL)
        
        for inp in inputs:
            inp_type = re.search(r'type=["\']([^"\']*)["\']', inp, re.IGNORECASE)
            inp_name = re.search(r'name=["\']([^"\']*)["\']', inp, re.IGNORECASE)
            inp_id = re.search(r'id=["\']([^"\']*)["\']', inp, re.IGNORECASE)
            inp_placeholder = re.search(r'placeholder=["\']([^"\']*)["\']', inp, re.IGNORECASE)
            
            form_info['inputs'].append({
                'type': inp_type.group(1) if inp_type else 'text',
                'name': inp_name.group(1) if inp_name else '',
                'id': inp_id.group(1) if inp_id else '',
                'placeholder': inp_placeholder.group(1) if inp_placeholder else ''
            })
        
        form_info['inputs'].extend([{'type': 'select', 'name': '', 'id': ''}] * len(selects))
        form_info['inputs'].extend([{'type': 'textarea', 'name': '', 'id': ''}] * len(textareas))
        form_info['input_count'] = len(form_info['inputs'])
        
        # 保存表单代码预览（前 500 字符）
        form_info['code_preview'] = form[:500] + ('...' if len(form) > 500 else '')
        
        key_info['forms'].append(form_info)
    
    # 统计 input 总数（包括表单外的）
    all_inputs = re.findall(r'<input[^>]*>', html_content, re.IGNORECASE)
    key_info['input_count'] = len(all_inputs) + len(selects) + len(textareas)
    
    # 提取 script 标签数量
    scripts = re.findall(r'<script[^>]*>.*?</script>', html_content, re.IGNORECASE | re.DOTALL)
    key_info['scripts'] = [{'length': len(s), 'has_fetch': 'fetch' in s or 'ajax' in s.lower()} for s in scripts]
    
    # 提取 style 标签数量
    styles = re.findall(r'<style[^>]*>.*?</style>', html_content, re.IGNORECASE | re.DOTALL)
    key_info['styles'] = [{'length': len(s)} for s in styles]
    
    return key_info

def extract_file_key_info(file_path, content):
    """
    根据文件类型提取关键信息
    """
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()
    
    if ext == '.html' or ext == '.htm':
        # HTML 文件：提取结构信息
        key_info = extract_html_key_info(content, filename)
        
        result = f"""
=== 文件：{filename} ===
类型：HTML 网页
标题：{key_info['title'] or '无标题'}
表单数量：{key_info['form_count']}
输入字段总数：{key_info['input_count']}
"""
        
        if key_info['has_form']:
            result += "\n--- 表单详情 ---\n"
            for form in key_info['forms']:
                result += f"表单 {form['index'] + 1}:\n"
                result += f"  - 提交地址：{form['action'] or '未设置'}\n"
                result += f"  - 提交方法：{form['method'] or 'GET'}\n"
                result += f"  - 输入字段数：{form['input_count']}\n"
                if form['inputs']:
                    result += f"  - 字段列表：{', '.join([f\"{i['type']}:{i['name'] or i['id']}\" for i in form['inputs'][:5]])}\n"
                result += f"  - 代码预览:\n{form['code_preview']}\n"
        else:
            result += "\n⚠️ 此 HTML 文件没有表单，可能需要添加数据提交功能\n"
        
        if key_info['scripts']:
            has_fetch = any(s.get('has_fetch') for s in key_info['scripts'])
            result += f"\n脚本数量：{len(key_info['scripts'])}（{'包含' if has_fetch else '不包含'}网络请求）\n"
        
        result += f"\n--- 完整 HTML 代码（供参考）---\n{content}\n"
        return result
    
    elif ext == '.js':
        # JS 文件：只取前 2000 字符 + 函数列表
        functions = re.findall(r'function\s+(\w+)\s*\([^)]*\)', content)
        result = f"""
=== 文件：{filename} ===
类型：JavaScript 脚本
文件大小：{len(content)} 字符
函数列表：{', '.join(functions[:10])}{'...' if len(functions) > 10 else ''}

--- 代码内容（前 2000 字符）---
{content[:2000]}{'...' if len(content) > 2000 else ''}
"""
        return result
    
    elif ext == '.css':
        # CSS 文件：只取前 1000 字符
        result = f"""
=== 文件：{filename} ===
类型：样式表
文件大小：{len(content)} 字符

--- 样式内容（前 1000 字符）---
{content[:1000]}{'...' if len(content) > 1000 else ''}
"""
        return result
    
    else:
        # 其他文件：直接返回内容
        return f"""
=== 文件：{filename} ===
类型：{ext or '未知'}

--- 文件内容 ---
{content}
"""


# ==================== 配置管理函数 ====================
def load_ai_config():
    """初始化或获取内存中的配置"""
    global _ai_config
    if _ai_config is not None:
        return _ai_config
    
    config = copy.deepcopy(DEFAULT_AI_CONFIG)
    _ai_config = config
    print("✅ 使用硬编码的 AI 配置")
    return _ai_config

def get_ai_config():
    """获取当前配置"""
    return load_ai_config()

def save_ai_config(config):
    """保存配置到内存"""
    global _ai_config
    _ai_config = config
    return True

def set_logged_user_key(user_key):
    """将当前登录用户的 user_key 保存到内存配置中"""
    config = get_ai_config()
    config['logged_user_key'] = user_key
    save_ai_config(config)

def get_master_key():
    config = get_ai_config()
    return config.get('master_key', '')

def check_ai_quota():
    """
    检查 AI 使用配额，返回 (can_use, message, api_key, using_master)
    """
    config = get_ai_config()
    user_info = get_current_user_info()
    if not user_info:
        return False, '请先登录', None, False

    expiry = user_info.get('expiry_date')
    if expiry:
        try:
            expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date()
            if datetime.now().date() > expiry_date:
                return False, '账号已过期', None, False
        except:
            pass

    remaining = user_info.get('remaining_uses', 0)
    if remaining <= 0:
        return False, '剩余使用次数不足', None, False

    temp_key = config.get('temp_key')
    if not temp_key:
        return False, '系统未配置临时密钥', None, False

    temp_key_expiry = config.get('temp_key_expiry')
    if temp_key_expiry:
        try:
            exp = datetime.strptime(temp_key_expiry, '%Y-%m-%d %H:%M:%S')
            if datetime.now() > exp:
                return False, '临时密钥已过期', None, False
        except:
            pass

    return True, '', temp_key, False


# ==================== TLS 适配器（忽略证书验证） ====================
class TLSAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.poolmanager = poolmanager.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_version=ssl.PROTOCOL_TLS,
            ssl_context=ctx)


def create_ai_analyzer():
    """创建 AI 分析器实例"""
    try:
        session = requests.Session()
        session.mount('https://', TLSAdapter())
        return session
    except Exception as e:
        print(f"❌ 创建 AI 分析器失败：{e}")
        return None


def extract_html_from_response(ai_response):
    """从 AI 响应中提取 HTML 代码"""
    patterns = [
        r'(<!DOCTYPE html>.*?</html>)',
        r'(<html>.*?</html>)',
    ]
    for pattern in patterns:
        match = re.search(pattern, ai_response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1)
    return ai_response


def safe_join_teacher_path(teacher_username, subpath):
    """安全拼接教师目录下的路径，防止路径遍历"""
    base = os.path.realpath(os.path.join('templates', teacher_username))
    target = os.path.realpath(os.path.join(base, subpath))
    if not target.startswith(base):
        return None
    return target


# ==================== 加载提示词模板 ====================
def load_prompt_template():
    """
    获取提示词模板：始终返回硬编码的默认模板（优化版）
    """
    return DEFAULT_PROMPT_TEMPLATE


# ==================== AI 配置管理 API ====================
@ai_bp.route('/ai/config', methods=['GET'])
def get_ai_config_api():
    """获取 AI 配置（隐藏密钥敏感部分）"""
    config = get_ai_config()
    if config.get('text_model', {}).get('api_key'):
        key = config['text_model']['api_key']
        if len(key) > 8:
            config['text_model']['api_key'] = key[:4] + '*' * (len(key)-8) + key[-4:]
    if config.get('image_model', {}).get('api_key'):
        key = config['image_model']['api_key']
        if len(key) > 8:
            config['image_model']['api_key'] = key[:4] + '*' * (len(key)-8) + key[-4:]
    return jsonify({'success': True, 'config': config})

@ai_bp.route('/ai/config', methods=['POST'])
def save_ai_config_api():
    """保存 AI 配置到内存"""
    try:
        config = request.json
        if save_ai_config(config):
            return jsonify({'success': True, 'message': '配置已保存'})
        else:
            return jsonify({'success': False, 'message': '保存失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== AI 生成图片 API ====================
@ai_bp.route('/ai/generate-image', methods=['POST'])
def ai_generate_image():
    """AI 生成图片 - 保存到教师指定文件夹"""
    try:
        can_use, msg, api_key, using_master = check_ai_quota()
        if not can_use:
            return jsonify({'success': False, 'message': msg}), 403

        data = request.json
        prompt = data.get('prompt', '')
        target_folder = data.get('targetFolder', '').strip()
        file_name = data.get('fileName', '').strip()
        model = data.get('model', None)

        if not prompt:
            return jsonify({'success': False, 'message': '提示词不能为空'})
        if not target_folder:
            return jsonify({'success': False, 'message': '保存文件夹不能为空'})
        if not file_name:
            return jsonify({'success': False, 'message': '文件名不能为空'})

        safe_file_name = safe_filename(file_name, 'image')
        if not safe_file_name.lower().endswith('.png'):
            safe_file_name += '.png'

        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401

        from teacher_apis import safe_join_path
        target_dir = safe_join_path(current_teacher, target_folder, target_teacher=current_teacher)
        if not target_dir:
            return jsonify({'success': False, 'message': '无效的文件夹路径'}), 400

        os.makedirs(target_dir, exist_ok=True)

        config = get_ai_config()
        img_cfg = config.get('image_model')
        if not img_cfg:
            return jsonify({'success': False, 'message': '图像模型未配置'}), 500

        if not model:
            model = img_cfg.get('model')
            if not model and img_cfg.get('available_models'):
                model = img_cfg['available_models'][0]
        if not model:
            return jsonify({'success': False, 'message': '未指定图像模型'}), 500

        base_url = img_cfg.get('base_url')
        if not base_url:
            return jsonify({'success': False, 'message': '图像模型 base_url 未配置'}), 500

        image_data = generate_image_with_qwen(prompt, model, base_url, api_key)
        if not image_data:
            return jsonify({'success': False, 'message': '图片生成失败'}), 500

        file_path = os.path.join(target_dir, safe_file_name)
        with open(file_path, 'wb') as f:
            f.write(image_data)

        decrease_remaining_uses(current_teacher)

        return jsonify({
            'success': True,
            'imageUrl': f'/templates/{current_teacher}/{target_folder}/{safe_file_name}',
            'message': '图片生成成功'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


def generate_image_with_qwen(prompt, model, base_url, api_key):
    print("使用 qwen-image-plus 模型生成图片")
    try:
        api_url = base_url
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ]
            },
            "parameters": {
                "negative_prompt": "",
                "prompt_extend": True,
                "watermark": False,
                "size": "1328*1328"
            }
        }
        print(f"🚀 发送图片生成请求到模型：{model}")
        session = create_ai_analyzer()
        if not session:
            raise Exception("无法创建 AI 分析会话")
        response = session.post(api_url, headers=headers, json=payload, timeout=300)
        print(f"📡 图片生成 API 响应状态：{response.status_code}")
        if response.status_code == 200:
            response_data = response.json()
            print(f"✅ 图片生成 API 调用成功")
            image_url = None
            if 'output' in response_data and 'choices' in response_data['output']:
                for choice in response_data['output']['choices']:
                    if 'message' in choice and 'content' in choice['message']:
                        for content in choice['message']['content']:
                            if 'image' in content:
                                image_url = content['image']
                                break
                    if image_url:
                        break
            if image_url:
                print(f"🖼️ 图片生成成功，URL: {image_url[:50]}...")
                return download_and_save_image(image_url, 'ai_generated')
            else:
                print(f"⚠️ 未找到图片 URL，响应：{response_data}")
                return None
        else:
            error_msg = f"图片生成 API 请求失败：状态码 {response.status_code}"
            print(f"❌ {error_msg}")
            print(f"响应内容：{response.text}")
            return None
    except Exception as e:
        error_msg = f"调用图片生成 API 失败：{str(e)}"
        print(f"❌ {error_msg}")
        return None


def download_and_save_image(image_url, source_type='ai'):
    """下载图片并保存到服务器，返回二进制数据"""
    try:
        print(f"📥 下载图片")
        response = requests.get(image_url, timeout=30)
        if response.status_code == 200:
            return response.content
        else:
            print(f"❌ 下载图片失败：HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ 下载和保存图片失败：{str(e)}")
        return None


# ==================== AI 生成视频 API（模拟模式）====================
@ai_bp.route('/ai/generate-video', methods=['POST'])
def ai_generate_video():
    """AI 生成视频（模拟模式）"""
    try:
        can_use, msg, api_key, using_master = check_ai_quota()
        if not can_use:
            return jsonify({'success': False, 'message': msg}), 403

        data = request.json
        prompt = data.get('prompt', '')
        activity_name = data.get('activityName', '').strip()
        reference_files = data.get('files', [])

        if not prompt:
            return jsonify({'success': False, 'message': '提示词不能为空'})
        if not activity_name:
            return jsonify({'success': False, 'message': '网站名称不能为空'})

        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401

        from teacher_apis import safe_join_path
        target_dir = safe_join_path(current_teacher, activity_name, target_teacher=current_teacher)
        if not target_dir:
            return jsonify({'success': False, 'message': '无效的文件夹路径'}), 400
        os.makedirs(target_dir, exist_ok=True)

        activity_name_safe = safe_filename(activity_name, 'video')
        file_name = f"{activity_name_safe}.mp4"
        file_path = os.path.join(target_dir, file_name)
        content = f"这是模拟生成的视频文件，实际内容为文本。\n提示词：{prompt}\n生成时间：{datetime.now().isoformat()}"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        decrease_remaining_uses(current_teacher)

        return jsonify({
            'success': True,
            'folder': activity_name,
            'message': '视频生成成功（模拟模式）'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@ai_bp.route('/interactive-templates', methods=['GET'])
def get_interactive_templates():
    current = get_current_teacher()
    if not current:
        return jsonify({'success': False, 'message': '未登录'}), 401
    shared = get_shared_data()
    return jsonify({'success': True, 'templates': shared.get('interactiveTemplates', [])})


# ==================== AI 生成网页 API（优化版 - 方案 1+2） ====================
@ai_bp.route('/ai/generate-page', methods=['POST'])
def ai_generate_page():
    """
    AI 根据参考文件和提示词生成 HTML 页面（优化版）
    改进：
    1. 使用优化后的提示词模板（更清晰、结构化）
    2. 智能提取参考文件关键信息（避免 AI 被大量代码淹没）
    """
    print("\n" + "="*60)
    print("=== 进入 /ai/generate-page (优化版) ===")
    print("="*60)
    
    try:
        data = request.json
        prompt = data.get('prompt', '')
        target_folder = data.get('targetFolder', '').strip()
        file_name = data.get('fileName', '').strip()
        reference_files = data.get('referenceFiles', [])

        print(f"📥 收到请求:")
        print(f"   提示词：'{prompt[:100]}...'")
        print(f"   目标文件夹：'{target_folder}'")
        print(f"   文件名：'{file_name}'")
        print(f"   参考文件数：{len(reference_files)}")

        # 参数验证
        if not prompt:
            print("❌ 提示词为空")
            return jsonify({'success': False, 'message': '提示词不能为空'})
        if not target_folder:
            print("❌ 保存文件夹为空")
            return jsonify({'success': False, 'message': '保存文件夹不能为空'})
        if not file_name:
            print("❌ 文件名为空")
            return jsonify({'success': False, 'message': '文件名不能为空'})

        # 配额检查
        can_use, msg, api_key, using_master = check_ai_quota()
        print(f"🔑 配额检查：can_use={can_use}, msg={msg}")
        if not can_use:
            print(f"❌ 配额检查失败：{msg}")
            return jsonify({'success': False, 'message': msg}), 403

        current_teacher = get_current_teacher()
        if not current_teacher:
            print("❌ 未登录")
            return jsonify({'success': False, 'message': '未登录'}), 401

        # 安全文件名处理
        safe_file_name = safe_filename(file_name, 'page')
        if not safe_file_name.lower().endswith('.html'):
            safe_file_name += '.html'

        # 目标目录检查
        from teacher_apis import safe_join_path
        target_dir = safe_join_path(current_teacher, target_folder, target_teacher=current_teacher)
        if not target_dir:
            print(f"❌ 无效的文件夹路径：target_folder={target_folder}")
            return jsonify({'success': False, 'message': '无效的文件夹路径'}), 400
        os.makedirs(target_dir, exist_ok=True)
        print(f"📁 目标目录：{target_dir}")

        # ==================== 方案 2：智能提取参考文件关键信息 ====================
        ref_contents = []
        for rel_path in reference_files:
            file_full = safe_join_path(current_teacher, rel_path, target_teacher=current_teacher)
            if file_full and os.path.isfile(file_full):
                try:
                    # 尝试 UTF-8 编码读取
                    try:
                        with open(file_full, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except UnicodeDecodeError:
                        # 如果 UTF-8 失败，尝试 GBK
                        with open(file_full, 'r', encoding='gbk') as f:
                            content = f.read()
                    
                    # 智能提取关键信息
                    extracted_info = extract_file_key_info(file_full, content)
                    ref_contents.append(extracted_info)
                    print(f"✅ 提取参考文件关键信息：{os.path.basename(file_full)}")
                    
                except Exception as e:
                    ref_contents.append(f"--- 文件 {os.path.basename(file_full)} (读取失败：{e}) ---")
                    print(f"⚠️ 读取文件失败：{file_full}, 错误：{e}")
            else:
                ref_contents.append(f"--- 文件 {rel_path} (不存在) ---")
                print(f"⚠️ 文件不存在：{rel_path}")

        ref_content = '\n'.join(ref_contents) if ref_contents else '无参考文件'
        print(f"📄 参考文件内容长度：{len(ref_content)} 字符")

        # ==================== 方案 1：使用优化后的提示词模板 ====================
        template = load_prompt_template()
        print(f"📄 使用优化后的提示词模板（长度：{len(template)} 字符）")

        # 拼接完整提示词
        combined_prompt = template.replace('{{prompt}}', prompt) \
                                   .replace('{{ref_content}}', ref_content)

        print("\n" + "="*60)
        print("【DEBUG】完整提示词（前 2000 字符）:")
        print(combined_prompt[:2000])
        print("="*60 + "\n")

        # 模型配置
        config = get_ai_config()
        text_cfg = config.get('text_model')
        if not text_cfg:
            print("❌ 文本模型未配置")
            return jsonify({'success': False, 'message': '文本模型未配置'}), 500

        model = text_cfg.get('model')
        if not model and text_cfg.get('available_models'):
            model = text_cfg['available_models'][0]
        if not model:
            print("❌ 未指定文本模型")
            return jsonify({'success': False, 'message': '未指定文本模型'}), 500

        base_url = text_cfg.get('base_url')
        if not base_url:
            print("❌ 文本模型 base_url 未配置")
            return jsonify({'success': False, 'message': '文本模型 base_url 未配置'}), 500

        print(f"🤖 模型配置：model={model}, base_url={base_url}")

        # 调用 AI 模型
        generated_html = call_ai_model_for_html(combined_prompt, model, base_url, api_key)
        if not generated_html:
            print("❌ AI 模型返回空，生成失败")
            return jsonify({'success': False, 'message': 'AI 生成失败'}), 500

        # 保存文件
        file_path = os.path.join(target_dir, safe_file_name)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(generated_html)
        print(f"✅ 网页已保存至：{file_path}")

        # 扣除使用次数
        decrease_remaining_uses(current_teacher)

        return jsonify({
            'success': True,
            'fileUrl': f'/templates/{current_teacher}/{target_folder}/{safe_file_name}',
            'message': '网页生成成功'
        })
        
    except Exception as e:
        print(f"🔥 生成网页异常：{str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'服务器内部错误：{str(e)}'}), 500


@ai_bp.route('/ai/generate-page-from-folder', methods=['POST'])
def generate_page_from_folder():
    """AI 根据参考文件夹生成 HTML 页面（优化版）"""
    print("\n=== 进入 /ai/generate-page-from-folder (优化版) ===")
    try:
        can_use, msg, api_key, using_master = check_ai_quota()
        if not can_use:
            print(f"❌ 配额检查失败：{msg}")
            return jsonify({'success': False, 'message': msg}), 403

        data = request.json
        folder_path = data.get('folderPath', '')
        selected_files = data.get('selectedFiles', [])
        prompt = data.get('prompt', '').strip()
        target_folder = data.get('targetFolder', '').strip()
        teacher = data.get('teacher', get_current_teacher())

        print(f"📥 收到请求：prompt='{prompt[:50]}...', target_folder='{target_folder}', teacher='{teacher}'")
        print(f"📎 参考文件夹路径：'{folder_path}'，勾选文件数：{len(selected_files)}")

        if not teacher:
            return jsonify({'success': False, 'message': '未指定教师'}), 400
        if not prompt:
            return jsonify({'success': False, 'message': '提示词不能为空'})
        if not target_folder:
            return jsonify({'success': False, 'message': '目标文件夹不能为空'})

        current_teacher = get_current_teacher()
        if teacher != current_teacher and not is_admin():
            return jsonify({'success': False, 'message': '无权操作其他教师目录'}), 403

        # 智能提取参考文件内容
        ref_contents = []
        if selected_files:
            for rel_path in selected_files:
                file_full = safe_join_teacher_path(teacher, rel_path)
                if file_full and os.path.isfile(file_full):
                    try:
                        try:
                            with open(file_full, 'r', encoding='utf-8') as f:
                                content = f.read()
                        except UnicodeDecodeError:
                            with open(file_full, 'r', encoding='gbk') as f:
                                content = f.read()
                        
                        # 智能提取关键信息
                        extracted_info = extract_file_key_info(file_full, content)
                        ref_contents.append(extracted_info)
                    except Exception as e:
                        ref_contents.append(f"--- 文件 {os.path.basename(file_full)} (读取失败：{e}) ---")
                else:
                    ref_contents.append(f"--- 文件 {rel_path} (不存在) ---")
        
        elif folder_path:
            ref_dir = safe_join_teacher_path(teacher, folder_path)
            if not ref_dir or not os.path.isdir(ref_dir):
                return jsonify({'success': False, 'message': '参考文件夹不存在'})
            
            for fname in os.listdir(ref_dir):
                fpath = os.path.join(ref_dir, fname)
                if os.path.isfile(fpath):
                    try:
                        try:
                            with open(fpath, 'r', encoding='utf-8') as f:
                                content = f.read()
                        except UnicodeDecodeError:
                            with open(fpath, 'r', encoding='gbk') as f:
                                content = f.read()
                        
                        extracted_info = extract_file_key_info(fpath, content)
                        ref_contents.append(extracted_info)
                    except:
                        ref_contents.append(f"--- 文件 {fname} (无法读取) ---")
        else:
            ref_contents = []

        ref_content = '\n'.join(ref_contents) if ref_contents else '无参考文件'
        print(f"📄 参考文件内容长度：{len(ref_content)} 字符")

        # 使用优化后的提示词模板
        template = load_prompt_template()
        combined_prompt = template.replace('{{prompt}}', prompt) \
                                   .replace('{{ref_content}}', ref_content) \
                                   .replace('{{teacher}}', teacher) \
                                   .replace('{{task}}', target_folder)

        print(f"🤖 最终发送给 AI 的提示词（前 1000 字符）: {combined_prompt[:1000]}...")

        # 模型配置
        config = get_ai_config()
        text_cfg = config.get('text_model')
        if not text_cfg:
            print("❌ 文本模型未配置")
            return jsonify({'success': False, 'message': '文本模型未配置'}), 500

        model = text_cfg.get('model')
        if not model and text_cfg.get('available_models'):
            model = text_cfg['available_models'][0]
        if not model:
            print("❌ 未指定文本模型")
            return jsonify({'success': False, 'message': '未指定文本模型'}), 500

        base_url = text_cfg.get('base_url')
        if not base_url:
            print("❌ 文本模型 base_url 未配置")
            return jsonify({'success': False, 'message': '文本模型 base_url 未配置'}), 500

        print(f"🤖 模型配置：model={model}, base_url={base_url}")

        # 调用 AI 模型
        generated_html = call_ai_model_for_html(combined_prompt, model, base_url, api_key)
        if not generated_html:
            print("❌ AI 模型返回空，生成失败")
            return jsonify({'success': False, 'message': 'AI 生成失败'}), 500

        # 保存文件
        target_dir = safe_join_teacher_path(teacher, target_folder)
        if not target_dir:
            return jsonify({'success': False, 'message': '目标文件夹路径无效'})
        os.makedirs(target_dir, exist_ok=True)
        print(f"📁 目标目录：{target_dir}")

        import re
        words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', prompt)
        base_name = (words[0] if words else '新页面')[:20]
        base_name = re.sub(r'[^\w\u4e00-\u9fa5-]', '', base_name)
        if not base_name:
            base_name = f"page_{int(time.time())}"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{base_name}_{timestamp}.html"
        counter = 1
        while os.path.exists(os.path.join(target_dir, filename)):
            filename = f"{base_name}_{timestamp}_{counter}.html"
            counter += 1

        filepath = os.path.join(target_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(generated_html)
        print(f"✅ 网页已保存至：{filepath}")

        decrease_remaining_uses(current_teacher)

        return jsonify({
            'success': True,
            'filename': filename,
            'fileUrl': f'/templates/{teacher}/{target_folder}/{filename}',
            'message': f'网页生成成功，已保存到 {target_folder}/{filename}'
        })

    except Exception as e:
        print(f"🔥 生成网页异常：{e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== 调用 AI 模型生成 HTML ====================
def call_ai_model_for_html(prompt, model, base_url, api_key):
    """调用文本模型生成 HTML，返回生成的 HTML 文本或 None"""
    print("--- 进入 call_ai_model_for_html ---")
    try:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是一个专业的网页生成助手，只返回纯 HTML 代码，不要包含任何额外解释。"},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 8000,
            "temperature": 0.7
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        session = create_ai_analyzer()
        if not session:
            raise Exception("无法创建 AI 分析会话")

        full_url = f"{base_url}/chat/completions"
        print(f"📤 发送请求至：{full_url}")
        print(f"📦 请求体摘要：{json.dumps(payload, ensure_ascii=False)[:200]}...")

        response = session.post(
            full_url,
            headers=headers,
            json=payload,
            timeout=300
        )
        print(f"📡 AI API 响应状态码：{response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ AI API 调用成功")
            if 'usage' in data:
                print(f"📊 token 使用：{data['usage']}")
            if 'choices' in data and len(data['choices']) > 0:
                content = data['choices'][0]['message']['content']
                print(f"💬 AI 原始响应长度：{len(content)} 字符")
                html = extract_html_from_response(content)
                print(f"✅ 提取后 HTML 长度：{len(html)} 字符")
                return html
            else:
                print("❌ AI 响应中没有 choices")
                return None
        else:
            print(f"❌ AI API 请求失败，状态码 {response.status_code}")
            print(f"响应内容：{response.text[:500]}")
            return None
    except Exception as e:
        print(f"❌ call_ai_model_for_html 异常：{e}")
        return None
