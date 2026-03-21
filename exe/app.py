# app.py - 完整的课堂互动教学评测系统后端（带自动恢复与GUI启动）
# 修改说明：
# ...（前面注释省略，但实际文件应包含所有历史说明）
# 新增：验证码接口 /api/captcha，登录增加验证码和失败次数限制
# 新增：所有 print 输出重定向到 GUI 日志区域和按天日志文件
# 新增：全局变量 gui_logged_user_info，记录 GUI 登录用户信息。
# 新增：API /api/gui-user 返回 GUI 登录用户信息。
# 新增：API /api/upgrade-to-qfuser 将当前 Web 用户升级为 QF_user。

from flask import Flask, send_from_directory, jsonify, g, request, send_file, session
from flask_cors import CORS
import os
import uuid
import time
import json
import socket
import webbrowser
import threading
import sys
import shutil
import requests
import base64
import io
import random
from collections import defaultdict
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from waitress import serve

# 新增验证码库
try:
    from captcha.image import ImageCaptcha
    CAPTCHA_AVAILABLE = True
except ImportError:
    print("⚠️ 验证码库未安装，请执行: pip install captcha")
    CAPTCHA_AVAILABLE = False

# 导入数据管理模块
from data_manager import (
    load_teacher_data_to_memory, get_teacher_data, manual_save_teacher,
    start_auto_save, ensure_directories, load_teachers, load_shared_data_to_memory,
    get_shared_data, update_shared_data, get_current_teacher, is_admin,
    generate_sms_code, generate_reset_token, is_valid_phone, is_valid_email,
    load_accounts, save_accounts, get_teacher_name_by_username,
    get_all_teachers, create_teacher_account, get_teacher_data_dir,
    export_teacher_data, import_teacher_data, import_class_template,
    get_all_students, get_all_classes, add_student, update_student, delete_student,
    batch_update_students, add_class, update_class, delete_class,
    get_students_by_teacher, get_classes_for_teacher, get_all_classes_with_details,
    get_students_by_class, get_teacher_info, save_teachers, delete_teacher,
    get_all_teachers_data, sms_codes, reset_tokens, current_users,
    cleanup_expired_data, get_file_icon, get_file_type_text,
    get_classes_for_teacher, get_teacher_data, load_teacher_data_to_memory,
    batch_delete_students, get_students_by_ids, delete_class,
    get_assignment_file_dir, save_assignment_file, cleanup_assignment_files,
    get_public_tasks,
    load_private_students, set_current_user,
    find_teacher_by_user_key
)
from sms_service import send_sms_verification, generate_sms_code, verify_phone_format
from ai_services import load_prompt_template, DEFAULT_AI_CONFIG

# 导入各个蓝图
from ai_services import ai_bp, get_ai_config, save_ai_config, set_logged_user_key
from teacher_apis import teacher_bp
from student_apis import student_bp
from assignment import assignment_bp

import queue
import tkinter as tk
from tkinter import scrolledtext

# 全局队列，用于将日志消息从非 GUI 线程传递到 GUI 线程
log_queue = queue.Queue()
# 日志文件对象
log_file = None
# 原始 stdout/stderr 保存
original_stdout = sys.stdout
original_stderr = sys.stderr

class Tee:
    """将输出同时写入原始流、日志文件和队列"""
    def __init__(self, name, file):
        self.name = name
        self.file = file
        self.original = sys.stdout if name == 'stdout' else sys.stderr

    def write(self, message):
        if message.strip():
            # 写入原始流（控制台）
            self.original.write(message)
            self.original.flush()
            # 写入日志文件（增加空检查和异常捕获）
            if self.file is not None:
                try:
                    self.file.write(message)
                    self.file.flush()
                except Exception:
                    # 文件写入失败时静默忽略，避免程序崩溃
                    pass
            # 放入队列供 GUI 显示
            log_queue.put(message)

    def flush(self):
        self.original.flush()
        if self.file is not None:
            try:
                self.file.flush()
            except Exception:
                pass

# ---------- 登录失败限制 ----------
login_failures = defaultdict(lambda: {'count': 0, 'last_fail': 0})
FAIL_LIMIT = 5
FAIL_BLOCK_SECONDS = 900  # 15分钟

# 验证码存储
captcha_codes = {}  # {token: {'code': str, 'expires_at': timestamp}}

# ---------- 确定可执行文件所在目录 ----------
if getattr(sys, 'frozen', False):
    EXE_DIR = os.path.dirname(sys.executable)
else:
    EXE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- 基础路径 ----------
TEMPLATE_FOLDER = os.path.join(EXE_DIR, 'templates') 
UPLOAD_FOLDER = os.path.join(EXE_DIR, 'uploads')
DATA_FOLDER = os.path.join(EXE_DIR, 'data') 
TEACH_FOLDER = os.path.join(TEMPLATE_FOLDER, 'teach')
LOGS_FOLDER = os.path.join(EXE_DIR, 'logs')

# ---------- 资源路径函数 ----------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# ---------- 自动恢复默认文件夹 ----------
def initialize_folders():
    exposed_folders = [
        ('uploads', UPLOAD_FOLDER),
        ('data', DATA_FOLDER),      
        ('templates/teach', TEACH_FOLDER),
        ('logs', LOGS_FOLDER),
    ]
    for rel_path, target_dir in exposed_folders:
        os.makedirs(target_dir, exist_ok=True)
        src_dir = resource_path(rel_path)
        if not os.path.exists(src_dir):
            continue
        for root, dirs, files in os.walk(src_dir):
            rel_root = os.path.relpath(root, src_dir)
            if rel_root == '.':
                rel_root = ''
            dest_root = os.path.join(target_dir, rel_root)
            os.makedirs(dest_root, exist_ok=True)
            for file in files:
                src_file = os.path.join(root, file)
                dest_file = os.path.join(dest_root, file)
                if not os.path.exists(dest_file):
                    shutil.copy2(src_file, dest_file)

# ---------- GUI 相关导入 ----------
try:
    import tkinter as tk
    from tkinter import messagebox, font, simpledialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ---------- Flask 应用配置 ----------
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')  # 请改为环境变量
CORS(app, resources={r"/api/*": {"origins": "*"}})

app.register_blueprint(ai_bp, url_prefix='/api')
app.register_blueprint(teacher_bp, url_prefix='/api')
app.register_blueprint(student_bp, url_prefix='/api')

TEMPLATE_ATTACHMENT_FOLDER = os.path.join(EXE_DIR, 'uploads', 'template_attachments')
os.makedirs(TEMPLATE_ATTACHMENT_FOLDER, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg'}
ALLOWED_ATTACHMENT_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'txt', 'zip', 'rar', '7z', 'tar', 'gz',
    'xls', 'xlsx', 'ppt', 'pptx', 'mp3', 'mp4', 'wav',
    'html', 'htm', 'xhtml', 'css', 'js', 'json', 'xml', 'csv',
    'md', 'rtf'
}
ALLOWED_TESTDATA_EXTENSIONS = {'in', 'out', 'txt'}

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def create_upload_response(success, message, **kwargs):
    response = {'success': success, 'message': message}
    response.update(kwargs)
    return jsonify(response)

@app.before_request
def before_request():
    current_teacher = get_current_teacher()
    if current_teacher:
        load_teacher_data_to_memory(current_teacher)
        g.current_teacher = current_teacher

# ==================== 统一静态文件路由 ====================

@app.route('/')
def index():
    config = get_ai_config()
    version = config.get('site_setup', {}).get('quickforge_version', '')
    current_teacher = get_current_teacher()

    # 基础版且未登录时，显示 public.html
    if version == 'basic' and not current_teacher:
        return send_from_directory(resource_path('statics'), 'public.html')
    else:
        # 其他情况显示登录页
        return send_from_directory(resource_path('statics'), 'login.html')

     
# 允许的静态文件扩展名白名单（增加 woff2）
ALLOWED_STATIC_EXTENSIONS = {'html', 'htm', 'css', 'js', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'ico', 'txt', 'pdf', 'webp', 'bmp', 'woff2', 'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'zst' } # 添加压缩文件}

@app.route('/<path:filename>')
def serve_static(filename):
    # 防止路径遍历
    if '..' in filename or filename.startswith('.') or '/.' in filename:
        return jsonify({'success': False, 'message': '访问被拒绝'}), 403

    # 检查文件扩展名是否允许
    if '.' not in filename:
        return jsonify({'success': False, 'message': '访问被拒绝'}), 403
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_STATIC_EXTENSIONS:
        return jsonify({'success': False, 'message': '访问被拒绝'}), 403

    # 直接从打包内的 statics 目录提供
    statics_dir = resource_path('statics')
    file_path = os.path.join(statics_dir, filename)
    if os.path.exists(file_path):
        return send_from_directory(statics_dir, filename)

    # 文件不存在
    return jsonify({'success': False, 'message': '文件不存在'}), 404

# ==================== 其他静态文件路由（必须完整保留）====================
@app.route('/data/<path:filename>')
def serve_data_files(filename):
    return send_from_directory('data', filename)

@app.route('/uploads/<path:filename>')
def serve_upload_files(filename):
    return send_from_directory('uploads', filename)

@app.route('/templates/<path:filename>')
def serve_templates(filename):
    parts = filename.split('/')
    for part in parts:
        if part.startswith('.'):
            return jsonify({'success': False, 'message': '访问被拒绝'}), 403
    return send_from_directory('templates', filename)

@app.route('/data/teacher_<teacher_username>/temp_question_images/<path:filename>')
def serve_teacher_temp_images(teacher_username, filename):
    try:
        temp_dir = os.path.join('data', f'teacher_{teacher_username}', 'temp_question_images')
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
        return send_from_directory(temp_dir, filename)
    except Exception as e:
        print(f"❌ 提供教师临时图片失败: {e}")
        return jsonify({'success': False, 'message': '文件不存在'}), 404

@app.route('/data/teacher_<teacher_username>/assignments/<assignment_id>/<file_type>/<path:filename>')
def serve_assignment_file(teacher_username, assignment_id, file_type, filename):
    try:
        file_dir = get_assignment_file_dir(teacher_username, assignment_id, file_type)
        return send_from_directory(file_dir, filename)
    except Exception as e:
        return jsonify({'success': False, 'message': '文件不存在'}), 404

@app.route('/data/teacher_<teacher_username>/assignments/<assignment_id>/<file_type>/<question_index>/<path:filename>')
def serve_assignment_question_file(teacher_username, assignment_id, file_type, question_index, filename):
    try:
        file_dir = os.path.join(get_assignment_file_dir(teacher_username, assignment_id, file_type), question_index)
        return send_from_directory(file_dir, filename)
    except Exception as e:
        return jsonify({'success': False, 'message': '文件不存在'}), 404

@app.route('/data/teacher_<teacher_username>/assignments/<assignment_id>/questions/<path:filename>')
def serve_assignment_question_images(teacher_username, assignment_id, filename):
    try:
        file_dir = os.path.join('data', f'teacher_{teacher_username}', 'assignments', assignment_id, 'questions')
        return send_from_directory(file_dir, filename)
    except Exception as e:
        return jsonify({'success': False, 'message': '文件不存在'}), 404

@app.route('/data/teacher_<teacher_username>/assignments/<assignment_id>/student/<student_id>/<path:filename>')
def serve_student_assignment_file(teacher_username, assignment_id, student_id, filename):
    try:
        file_dir = os.path.join(
            'data',
            f'teacher_{teacher_username}',
            "assignments",
            assignment_id,
            "student",
            student_id
        )
        return send_from_directory(file_dir, filename)
    except Exception as e:
        return jsonify({'success': False, 'message': '文件不存在'}), 404

@app.route('/data/teacher_<teacher_username>/assignments/<assignment_id>/student/<student_id>/question_<question_index>/<path:filename>')
def serve_student_question_file(teacher_username, assignment_id, student_id, question_index, filename):
    try:
        file_dir = os.path.join(
            'data',
            f'teacher_{teacher_username}',
            "assignments",
            assignment_id,
            "student",
            student_id,
            f"question_{question_index}"
        )
        return send_from_directory(file_dir, filename)
    except Exception as e:
        return jsonify({'success': False, 'message': '文件不存在'}), 404


@app.route('/api/data/<user_key>/<task_name>/alldata', methods=['GET'])
def get_task_data_with_prompt(user_key, task_name):
    """
    返回组合提示词：内置提示词 + 所有提交数据 + 指令
    """
    try:
        # 1. 获取数据（复用原有函数）
        from app import get_task_data_by_user_key  # 假设该函数已存在且可用
        data_response = get_task_data_by_user_key(user_key, task_name)
        if not data_response[0].json['success']:  # 注意：实际需根据返回结构处理
            return jsonify({'success': False, 'message': '获取数据失败'}), 400
        submissions = data_response[0].json.get('submissions', [])

        # 2. 获取内置提示词（可从 ai_services 中导入 DEFAULT_PROMPT_TEMPLATE）
        from ai_services import DEFAULT_PROMPT_TEMPLATE
        prompt_template = DEFAULT_PROMPT_TEMPLATE

        # 3. 构建返回文本
        data_str = json.dumps(submissions, ensure_ascii=False, indent=2)
        full_text = f"{prompt_template}\n\n以上是已提交的全部数据：\n{data_str}\n\n请按用户要求进行分析，生成一个分析报告网页。"

        # 4. 返回文本（注意 Content-Type）
        return Response(full_text, mimetype='text/plain; charset=utf-8')
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/uploads/template_attachments/<path:filename>')
def serve_template_attachment(filename):
    try:
        file_path = os.path.join(TEMPLATE_ATTACHMENT_FOLDER, filename)
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': '文件不存在'}), 404
        file_ext = os.path.splitext(filename)[1].lower()
        mime_types = {
            '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp',
            '.svg': 'image/svg+xml', '.html': 'text/html', '.htm': 'text/html',
            '.xhtml': 'application/xhtml+xml', '.pdf': 'application/pdf',
            '.doc': 'application/msword', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.ppt': 'application/vnd.ms-powerpoint', '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.txt': 'text/plain', '.md': 'text/markdown', '.rtf': 'application/rtf',
            '.csv': 'text/csv', '.zip': 'application/zip', '.rar': 'application/x-rar-compressed',
            '.7z': 'application/x-7z-compressed', '.tar': 'application/x-tar', '.gz': 'application/gzip'
        }
        mimetype = mime_types.get(file_ext, 'application/octet-stream')
        download_name = None
        shared_data = get_shared_data()
        for template_type in ['promptTemplates', 'interactiveTemplates', 'assignmentTemplates']:
            for template in shared_data.get(template_type, []):
                if 'attachment' in template and template['attachment'].get('unique_filename') == filename:
                    download_name = template['attachment'].get('filename', filename)
                    break
            if download_name:
                break
        if not download_name:
            download_name = filename
        previewable_extensions = [
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg',
            '.html', '.htm', '.xhtml', '.pdf', '.txt', '.md', '.csv'
        ]
        is_previewable = file_ext in previewable_extensions
        if is_previewable:
            response = send_file(file_path, mimetype=mimetype)
            if file_ext in ['.html', '.htm', '.xhtml', '.pdf', '.txt', '.md', '.csv']:
                response.headers['Content-Disposition'] = f'inline; filename="{download_name}"'
            return response
        else:
            return send_file(file_path, as_attachment=True, download_name=download_name, mimetype=mimetype)
    except Exception as e:
        print(f"❌ 提供模板附件失败: {e}")
        return jsonify({'success': False, 'message': '文件不存在或无法访问'}), 404



@app.route('/api/captcha', methods=['GET'])
def get_captcha():
    """生成验证码图片，返回图片 base64 和 token"""
    if not CAPTCHA_AVAILABLE:
        return jsonify({'success': False, 'message': '验证码服务未安装'}), 500

    token = uuid.uuid4().hex
    code = ''.join([str(random.randint(0, 9)) for _ in range(4)])  # 4位数字
    captcha_codes[token] = {
        'code': code,
        'expires_at': time.time() + 300  # 5分钟有效期
    }

    # 获取自定义字体路径（兼容开发环境和打包后）
    font_path = None
    try:
        # 尝试从 fonts 目录加载字体
        base_path = resource_path('statics/webfonts')
        font_path = os.path.join(base_path, 'arial.ttf')
        if not os.path.exists(font_path):
            font_path = None
    except:
        font_path = None

    try:
        if font_path:
            # 使用自定义字体创建 ImageCaptcha 实例
            image = ImageCaptcha(width=160, height=60, fonts=[font_path])
        else:
            # 无自定义字体，使用默认（可能因缺少系统字体而失败）
            image = ImageCaptcha(width=160, height=60)
        data = image.generate(code)
        img_base64 = base64.b64encode(data.getvalue()).decode('utf-8')
        return jsonify({
            'success': True,
            'token': token,
            'image': f'data:image/png;base64,{img_base64}'
        })
    except Exception as e:
        print(f"⚠️ 自定义字体验证码生成失败，使用备用方法: {e}")
        # 备用方法：使用 PIL 内置位图字体生成（保证不崩溃）
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new('RGB', (160, 60), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            font = ImageFont.load_default()  # 内置位图字体，永远可用
            # 计算文本位置居中
            bbox = draw.textbbox((0, 0), code, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (160 - text_width) // 2
            y = (60 - text_height) // 2
            draw.text((x, y), code, fill=(0, 0, 0), font=font)
            # 添加干扰线
            for _ in range(3):
                x1 = random.randint(0, 160)
                y1 = random.randint(0, 60)
                x2 = random.randint(0, 160)
                y2 = random.randint(0, 60)
                draw.line((x1, y1, x2, y2), fill=(128,128,128), width=1)
            img_io = io.BytesIO()
            img.save(img_io, format='PNG')
            img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
            return jsonify({
                'success': True,
                'token': token,
                'image': f'data:image/png;base64,{img_base64}'
            })
        except Exception as e2:
            print(f"❌ 备用验证码也失败: {e2}")
            return jsonify({'success': False, 'message': '验证码生成失败'}), 500
# ==================== 教师登录和基础API ====================
@app.route('/api/login/teacher', methods=['POST'])
def teacher_login():
    """Web登录：增加验证码验证和失败次数限制"""
    try:
        # 获取客户端 IP
        client_ip = request.remote_addr
        # 检查失败次数
        fail_data = login_failures[client_ip]
        if fail_data['count'] >= FAIL_LIMIT:
            if time.time() - fail_data['last_fail'] < FAIL_BLOCK_SECONDS:
                return jsonify({'success': False, 'message': '登录失败次数过多，请15分钟后再试'})
            else:
                # 重置计数
                fail_data['count'] = 0

        # 验证码校验
        captcha_token = request.json.get('captcha_token')
        captcha_code = request.json.get('captcha_code')
        if not captcha_token or not captcha_code:
            return jsonify({'success': False, 'message': '请输入验证码'})

        captcha_info = captcha_codes.get(captcha_token)
        if not captcha_info or time.time() > captcha_info['expires_at']:
            captcha_codes.pop(captcha_token, None)
            return jsonify({'success': False, 'message': '验证码已过期，请刷新'})
        if captcha_info['code'].lower() != captcha_code.lower():
            # 验证码错误，不计数（防止因验证码错误锁定用户）
            return jsonify({'success': False, 'message': '验证码错误'})
        # 验证通过后立即删除验证码
        captcha_codes.pop(captcha_token, None)

        username = request.json.get('username')
        password = request.json.get('password')
        print(f"🔐 Web登录尝试: username={username}, ip={client_ip}")

        if not username or not password:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'})

        teachers_data = load_teachers()
        teacher = next((t for t in teachers_data['teachers'] if t['username'] == username and t['password'] == password), None)

        if teacher:
            # 登录成功，清除失败计数
            login_failures.pop(client_ip, None)
            accounts_data = load_accounts()
            teacher_full = next((t for t in accounts_data['teachers'] if t['username'] == username), None)
            if teacher_full:
                current_users['current_teacher'] = username
                set_current_user(username, {
                    'username': username,
                    'name': teacher_full.get('name', ''),
                    'subject': teacher_full.get('subject', ''),
                    'role': teacher_full.get('role', 'teacher'),
                    'expiry_date': teacher_full.get('expiry_date', ''),
                    'remaining_uses': teacher_full.get('remaining_uses', 0),
                    'user_key': teacher_full.get('user_key', ''),
                    'user_key_expiry': teacher_full.get('user_key_expiry', '')
                })

                load_teacher_data_to_memory(username)
                teacher_name = teacher.get('name', username)
                teacher_subject = teacher.get('subject', '未设置')
                print(f"✅ Web登录成功: {username} (角色: {teacher.get('role', 'teacher')})")

                user_info = {
                    'type': 'teacher',
                    'username': username,
                    'name': teacher_name,
                    'subject': teacher_subject,
                    'role': teacher.get('role', 'teacher'),
                    'expiry_date': teacher_full.get('expiry_date', ''),
                    'remaining_uses': teacher_full.get('remaining_uses', 0)
                }
                if teacher.get('role') == 'admin':
                    user_info['isAdmin'] = True
                return jsonify({'success': True, 'user': user_info})
            else:
                return jsonify({'success': False, 'message': '教师信息不完整'})
        else:
            # 登录失败，增加计数
            fail_data['count'] += 1
            fail_data['last_fail'] = time.time()
            return jsonify({'success': False, 'message': '用户名或密码错误'})
    except Exception as e:
        print(f"💥 Web登录异常: {str(e)}")
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

@app.route('/api/login/private-student', methods=['POST'])
def private_student_login():
    try:
        data = request.json
        teacher_phone = data.get('teacherPhone')
        student_id = data.get('studentId')
        password = data.get('password')
        if not teacher_phone or not student_id or not password:
            return jsonify({'success': False, 'message': '请填写完整信息'})
        accounts_data = load_accounts()
        teacher = None
        for t in accounts_data['teachers']:
            if t.get('phone') == teacher_phone or t.get('username') == teacher_phone:
                teacher = t
                break
        if not teacher:
            return jsonify({'success': False, 'message': '教师不存在'})
        teacher_username = teacher['username']
        from data_manager import load_private_students
        students = load_private_students(teacher_username)
        student = next((s for s in students if s['id'] == student_id and s['password'] == password), None)
        if student:
            return jsonify({
                'success': True,
                'user': {
                    'type': 'private-student',
                    'id': student['id'],
                    'name': student['name'],
                    'teacher': teacher_username,
                    'teacherName': teacher.get('name', teacher_username)
                }
            })
        else:
            return jsonify({'success': False, 'message': '学号或密码错误'})
    except Exception as e:
        print(f"❌ 私有学生登录异常: {e}")
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

@app.route('/api/login/guest', methods=['POST'])
def guest_login():
    try:
        tasks = get_public_tasks()
        return jsonify({'success': True, 'tasks': tasks})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/public/tasks', methods=['GET'])
def get_public_tasks_api():
    try:
        tasks = get_public_tasks()
        return jsonify({'success': True, 'tasks': tasks})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/current', methods=['GET'])
def get_current_user():
    try:
        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401
        teachers_data = load_teachers()
        teacher = next((t for t in teachers_data['teachers'] if t['username'] == current_teacher), None)
        if teacher:
            return jsonify({
                'success': True,
                'teacher': current_teacher,
                'name': teacher.get('name', current_teacher),
                'role': teacher.get('role', 'teacher'),
                'subject': teacher.get('subject', '')
            })
        else:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def teacher_logout():
    try:
        current_teacher = get_current_teacher()
        if current_teacher:
            if 'current_teacher' in current_users:
                del current_users['current_teacher']
            if 'teacher_info' in current_users:
                del current_users['teacher_info']
            print(f"✅ 用户退出登录: {current_teacher}")
        return jsonify({'success': True, 'message': '退出登录成功'})
    except Exception as e:
        print(f"❌ 退出登录失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ==================== 个人资料管理API ====================
@app.route('/api/account/profile', methods=['GET'])
def get_profile():
    try:
        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401
        accounts_data = load_accounts()
        teacher_info = None
        for teacher in accounts_data['teachers']:
            if teacher['username'] == current_teacher:
                teacher_info = teacher.copy()
                break
        if not teacher_info:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
        if 'password' in teacher_info:
            del teacher_info['password']
        return jsonify({'success': True, 'profile': teacher_info})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取失败: {str(e)}'}), 500

@app.route('/api/account/profile', methods=['POST'])
def update_profile():
    try:
        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': '没有提供数据'})
        accounts_data = load_accounts()
        teacher_found = False
        for i, teacher in enumerate(accounts_data['teachers']):
            if teacher['username'] == current_teacher:
                if 'name' in data:
                    accounts_data['teachers'][i]['name'] = data['name'].strip()
                if 'subject' in data:
                    accounts_data['teachers'][i]['subject'] = data['subject'].strip()
                if 'phone' in data:
                    phone = data['phone'].strip()
                    if phone and not is_valid_phone(phone):
                        return jsonify({'success': False, 'message': '手机号格式不正确'})
                    accounts_data['teachers'][i]['phone'] = phone
                if 'email' in data:
                    email = data['email'].strip()
                    if email and not is_valid_email(email):
                        return jsonify({'success': False, 'message': '邮箱格式不正确'})
                    accounts_data['teachers'][i]['email'] = email
                teacher_found = True
                break
        if not teacher_found:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
        if save_accounts(accounts_data):
            return jsonify({'success': True, 'message': '个人资料更新成功'})
        else:
            return jsonify({'success': False, 'message': '保存失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500

@app.route('/api/account/password', methods=['POST'])
def change_password():
    try:
        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401
        data = request.json
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        if not old_password or not new_password or not confirm_password:
            return jsonify({'success': False, 'message': '请填写所有密码字段'})
        if new_password != confirm_password:
            return jsonify({'success': False, 'message': '两次输入的新密码不一致'})
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': '新密码长度至少为6位'})
        accounts_data = load_accounts()
        teacher_found = False
        for i, teacher in enumerate(accounts_data['teachers']):
            if teacher['username'] == current_teacher:
                if teacher.get('password') != old_password:
                    return jsonify({'success': False, 'message': '当前密码不正确'})
                accounts_data['teachers'][i]['password'] = new_password
                teacher_found = True
                break
        if not teacher_found:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
        if save_accounts(accounts_data):
            return jsonify({'success': True, 'message': '密码修改成功'})
        else:
            return jsonify({'success': False, 'message': '保存失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'修改失败: {str(e)}'}), 500

# ==================== 短信验证码API ====================
@app.route('/api/account/sms/send-code', methods=['POST'])
def send_sms_code():
    try:
        data = request.json
        username = data.get('username')
        phone = data.get('phone')
        if not username or not phone:
            return jsonify({'success': False, 'message': '请提供用户名和手机号'})
        if not verify_phone_format(phone):
            return jsonify({'success': False, 'message': '手机号格式不正确'})
        accounts_data = load_accounts()
        user_found = False
        user_phone = None
        for teacher in accounts_data['teachers']:
            if teacher['username'] == username:
                user_found = True
                user_phone = teacher.get('phone')
                break
        if not user_found:
            return jsonify({'success': False, 'message': '用户不存在'})
        if user_phone and user_phone != phone:
            return jsonify({'success': False, 'message': '手机号与账号不匹配'})
        sms_code = generate_sms_code()
        sms_codes[phone] = {
            'code': sms_code,
            'username': username,
            'expires_at': time.time() + 300
        }
        print(f"📱 正在发送短信验证码到 {phone}: {sms_code}")
        success, message = send_sms_verification(phone, sms_code, "5")
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': True, 'message': f'模拟发送: 验证码{sms_code}', 'simulation': True, 'code': sms_code})
    except Exception as e:
        return jsonify({'success': False, 'message': f'发送失败: {str(e)}'}), 500

@app.route('/api/account/sms/verify-code', methods=['POST'])
def verify_sms_code():
    try:
        data = request.json
        username = data.get('username')
        phone = data.get('phone')
        code = data.get('code')
        if not username or not phone or not code:
            return jsonify({'success': False, 'message': '请提供完整信息'})
        if phone not in sms_codes:
            return jsonify({'success': False, 'message': '验证码不存在或已过期'})
        sms_info = sms_codes[phone]
        if time.time() > sms_info['expires_at']:
            del sms_codes[phone]
            return jsonify({'success': False, 'message': '验证码已过期'})
        if sms_info['username'] != username or sms_info['code'] != code:
            return jsonify({'success': False, 'message': '验证码不正确'})
        reset_token = generate_reset_token()
        reset_tokens[reset_token] = {
            'username': username,
            'phone': phone,
            'expires_at': time.time() + 600
        }
        del sms_codes[phone]
        return jsonify({'success': True, 'message': '验证码验证成功', 'reset_token': reset_token})
    except Exception as e:
        return jsonify({'success': False, 'message': f'验证失败: {str(e)}'}), 500

@app.route('/api/account/sms/reset-password', methods=['POST'])
def reset_password_with_sms():
    try:
        data = request.json
        username = data.get('username')
        phone = data.get('phone')
        new_password = data.get('new_password')
        reset_token = data.get('reset_token')
        if not username or not phone or not new_password or not reset_token:
            return jsonify({'success': False, 'message': '请提供完整信息'})
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': '密码长度至少为6位'})
        if reset_token not in reset_tokens:
            return jsonify({'success': False, 'message': '重置令牌无效'})
        token_info = reset_tokens[reset_token]
        if time.time() > token_info['expires_at']:
            del reset_tokens[reset_token]
            return jsonify({'success': False, 'message': '重置令牌已过期'})
        if token_info['username'] != username or token_info['phone'] != phone:
            return jsonify({'success': False, 'message': '用户信息不匹配'})
        accounts_data = load_accounts()
        password_updated = False
        for i, teacher in enumerate(accounts_data['teachers']):
            if teacher['username'] == username:
                if teacher.get('phone') and teacher['phone'] != phone:
                    return jsonify({'success': False, 'message': '手机号与账号不匹配'})
                accounts_data['teachers'][i]['password'] = new_password
                password_updated = True
                break
        if not password_updated:
            return jsonify({'success': False, 'message': '用户不存在'})
        if save_accounts(accounts_data):
            del reset_tokens[reset_token]
            return jsonify({'success': True, 'message': '密码重置成功'})
        else:
            return jsonify({'success': False, 'message': '保存失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'重置失败: {str(e)}'}), 500

# ==================== 新增注册API（修改默认值）====================
@app.route('/api/register', methods=['POST'])
def register():
    """用户注册，默认有效期1年，剩余次数30次"""
    try:
        data = request.json
        phone = data.get('phone', '').strip()
        code = data.get('code', '').strip()
        password = data.get('password', '')
        organization = data.get('organization', '').strip()
        name = data.get('name', '').strip() or phone
        username = data.get('username', '').strip()

        if not phone or not code or not password:
            return jsonify({'success': False, 'message': '手机号、验证码和密码不能为空'})
        if not organization:
            return jsonify({'success': False, 'message': '请填写学校名称或行业类型'})
        if not verify_phone_format(phone):
            return jsonify({'success': False, 'message': '手机号格式不正确'})

        if phone not in sms_codes:
            return jsonify({'success': False, 'message': '验证码不存在或已过期'})
        sms_info = sms_codes[phone]
        if time.time() > sms_info['expires_at']:
            del sms_codes[phone]
            return jsonify({'success': False, 'message': '验证码已过期'})
        if sms_info['code'] != code:
            return jsonify({'success': False, 'message': '验证码错误'})

        accounts_data = load_accounts()
        if any(t.get('phone') == phone for t in accounts_data['teachers']):
            return jsonify({'success': False, 'message': '该手机号已注册'})

        if not username:
            username = phone
        else:
            if any(t['username'] == username for t in accounts_data['teachers']):
                return jsonify({'success': False, 'message': '用户名已存在'})

        # 生成用户密钥和有效期
        user_key = uuid.uuid4().hex
        expiry_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
        user_key_expiry = expiry_date

        success, message = create_teacher_account(
            username=username,
            password=password,
            name=name,
            phone=phone,
            role='teacher',
            subject='',
            email='',
            organization=organization,
            expiry_date=expiry_date,
            remaining_uses=30,           # 默认30次
            user_key=user_key,
            user_key_expiry=user_key_expiry
        )

        if success:
            del sms_codes[phone]
            return jsonify({'success': True, 'message': '注册成功', 'username': username})
        else:
            return jsonify({'success': False, 'message': message}), 500

    except Exception as e:
        print(f"❌ 注册异常: {e}")
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

# ==================== 新增数据获取API ====================
@app.route('/api/data/<user_key>/<task_name>/all', methods=['GET'])
def get_task_data_by_user_key(user_key, task_name):
    """根据 user_key 获取指定任务的所有提交数据和附件"""
    try:
        teacher = find_teacher_by_user_key(user_key)
        if not teacher:
            return jsonify({'success': False, 'message': '无效的 user_key'}), 404

        teacher_username = teacher['username']
        teacher_base = safe_teacher_path(teacher_username)
        if not teacher_base:
            return jsonify({'success': False, 'message': '教师目录无效'}), 500

        data_dir = os.path.join(teacher_base, 'data', task_name)
        if not os.path.isdir(data_dir):
            return jsonify({'success': True, 'submissions': []})

        submissions = []
        for fname in os.listdir(data_dir):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(data_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    submission = json.load(f)
                if '_files' in submission:
                    for file_info in submission['_files']:
                        if 'url' not in file_info:
                            saved_name = file_info.get('saved_name', '')
                            file_info['url'] = f'/templates/{teacher_username}/uploads/{saved_name}'
                submissions.append(submission)
            except Exception as e:
                print(f"⚠️ 读取提交文件 {fname} 失败: {e}")
                continue

        return jsonify({'success': True, 'submissions': submissions})

    except Exception as e:
        print(f"❌ 获取任务数据失败: {e}")
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

# ==================== 新增：DeepSeek 信息接口 ====================
@app.route('/api/deepseek-info', methods=['GET'])
def deepseek_info():
    """根据 user_key 返回教师用户名和内置提示词模板"""
    user_key = request.args.get('user_key')
    if not user_key:
        return jsonify({'success': False, 'message': '缺少 user_key'}), 400
    teacher = find_teacher_by_user_key(user_key)
    if not teacher:
        return jsonify({'success': False, 'message': '无效的 user_key'}), 404
    username = teacher['username']
    template = load_prompt_template()
    return jsonify({
        'success': True,
        'teacher': username,
        'prompt_template': template
    })

# ==================== 新增：获取 GUI 登录用户信息 ====================
# 全局变量存储 GUI 登录用户信息（仅在内存中）
gui_logged_user_info = None

@app.route('/api/gui-user', methods=['GET'])
def get_gui_user():
    """返回当前 GUI 登录用户的信息（用于 Web 端显示）"""
    if gui_logged_user_info:
        return jsonify({
            'success': True,
            'user': {
                'username': gui_logged_user_info.get('username'),
                'name': gui_logged_user_info.get('name'),
                'role': gui_logged_user_info.get('role'),
                'remaining_uses': gui_logged_user_info.get('remaining_uses', 0),
                'expiry_date': gui_logged_user_info.get('expiry_date', '')
            }
        })
    else:
        return jsonify({'success': False, 'message': 'GUI 未登录'})

# ==================== 新增：将当前 Web 用户升级为 QF_user ====================
@app.route('/api/upgrade-to-qfuser', methods=['POST'])
def upgrade_to_qfuser():
    """将当前 Web 登录用户升级为 QF_user，并设置初始额度（模拟支付成功）"""
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    accounts_data = load_accounts()
    for i, teacher in enumerate(accounts_data['teachers']):
        if teacher['username'] == current_teacher:
            accounts_data['teachers'][i]['role'] = 'QF_user'
            accounts_data['teachers'][i]['remaining_uses'] = 100  # 初始额度 100 次
            accounts_data['teachers'][i]['expiry_date'] = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
            accounts_data['teachers'][i]['updatedAt'] = datetime.now().isoformat()
            break
    else:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    if save_accounts(accounts_data):
        if 'teacher_info' in current_users and current_users['teacher_info'].get('username') == current_teacher:
            current_users['teacher_info']['role'] = 'QF_user'
            current_users['teacher_info']['remaining_uses'] = 100
            current_users['teacher_info']['expiry_date'] = accounts_data['teachers'][i]['expiry_date']
        return jsonify({'success': True, 'message': '升级成功，您已成为 QF_user'})
    else:
        return jsonify({'success': False, 'message': '保存失败'}), 500

# ==================== 管理员账号管理API（扩展）====================
@app.route('/api/admin/teachers', methods=['GET'])
def admin_get_teachers():
    try:
        if not is_admin():
            return jsonify({'success': False, 'message': '权限不足'}), 403
        teachers_data = load_teachers()
        teachers = [t for t in teachers_data['teachers'] if t.get('role') == 'teacher']
        for teacher in teachers:
            if 'subject' not in teacher:
                teacher['subject'] = ''
        return jsonify({'success': True, 'teachers': teachers})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/teachers', methods=['POST'])
def admin_create_teacher():
    try:
        if not is_admin():
            return jsonify({'success': False, 'message': '权限不足'}), 403
        data = request.json
        username = data.get('username')
        password = data.get('password')
        name = data.get('name', '')
        phone = data.get('phone', '')
        subject = data.get('subject', '')
        organization = data.get('organization', '')
        expiry_date = data.get('expiry_date', '')
        remaining_uses = data.get('remaining_uses', 0)
        user_key = data.get('user_key', '')
        user_key_expiry = data.get('user_key_expiry', '')
        role = data.get('role', 'teacher')

        if not username or not password:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'})

        success, message = create_teacher_account(
            username=username,
            password=password,
            name=name,
            phone=phone,
            role=role,
            subject=subject,
            email='',
            organization=organization,
            expiry_date=expiry_date,
            remaining_uses=remaining_uses,
            user_key=user_key,
            user_key_expiry=user_key_expiry
        )
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

@app.route('/api/admin/teachers/<username>', methods=['PUT'])
def admin_update_teacher(username):
    try:
        if not is_admin():
            return jsonify({'success': False, 'message': '权限不足'}), 403
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': '没有提供数据'})

        accounts_data = load_accounts()
        teacher_found = False
        for i, teacher in enumerate(accounts_data['teachers']):
            if teacher['username'] == username:
                updatable_fields = ['name', 'subject', 'phone', 'password', 'organization',
                                    'expiry_date', 'remaining_uses', 'user_key', 'user_key_expiry', 'role']
                for field in updatable_fields:
                    if field in data and (field != 'password' or data['password']):
                        accounts_data['teachers'][i][field] = data[field].strip() if isinstance(data[field], str) else data[field]
                teacher_found = True
                break

        if not teacher_found:
            return jsonify({'success': False, 'message': '教师账号不存在'}), 404

        if save_accounts(accounts_data):
            return jsonify({'success': True, 'message': '教师信息更新成功'})
        else:
            return jsonify({'success': False, 'message': '保存失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500

@app.route('/api/admin/teachers/<username>', methods=['DELETE'])
def admin_delete_teacher(username):
    try:
        if not is_admin():
            return jsonify({'success': False, 'message': '权限不足'}), 403
        current_teacher = get_current_teacher()
        if username == current_teacher:
            return jsonify({'success': False, 'message': '不能删除自己的账号'})
        teachers_data = load_teachers()
        original_count = len(teachers_data['teachers'])
        teachers_data['teachers'] = [t for t in teachers_data['teachers'] if t['username'] != username]
        if len(teachers_data['teachers']) < original_count:
            if save_teachers(teachers_data):
                teacher_dir = get_teacher_data_dir(username)
                if os.path.exists(teacher_dir):
                    shutil.rmtree(teacher_dir)
                return jsonify({'success': True, 'message': '教师账号删除成功'})
            else:
                return jsonify({'success': False, 'message': '保存教师列表失败'})
        else:
            return jsonify({'success': False, 'message': '教师账号不存在'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

@app.route('/api/account/check-admin', methods=['GET'])
def check_admin():
    try:
        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'isAdmin': False, 'message': '未登录'}), 401
        teachers_data = load_teachers()
        teacher = next((t for t in teachers_data['teachers'] if t['username'] == current_teacher), None)
        is_admin_user = teacher and teacher.get('role') == 'admin'
        return jsonify({'isAdmin': is_admin_user, 'username': current_teacher, 'role': teacher.get('role') if teacher else 'unknown'})
    except Exception as e:
        return jsonify({'isAdmin': False, 'message': str(e)}), 500

# ==================== 班级管理API ====================
@app.route('/api/classes', methods=['GET'])
def get_classes():
    try:
        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401
        teachers_data = load_teachers()
        teacher_info = next((t for t in teachers_data['teachers'] if t['username'] == current_teacher), None)
        if not teacher_info:
            return jsonify({'success': False, 'message': '教师信息不存在'}), 404
        teacher_name = teacher_info.get('name', current_teacher)
        if is_admin():
            classes = get_all_classes_with_details()
        else:
            classes = get_classes_for_teacher(current_teacher)
            if not classes:
                return jsonify({'success': True, 'classes': [], 'message': '您还没有被分配任教的班级，请联系管理员'})
        formatted_classes = []
        for class_item in classes:
            if isinstance(class_item.get('subjectTeachers'), str):
                subject_teachers = [t.strip() for t in class_item['subjectTeachers'].split(',') if t.strip()]
                class_item['subjectTeachers'] = subject_teachers
            elif 'subjectTeachers' not in class_item:
                class_item['subjectTeachers'] = []
            if 'headTeacher' not in class_item:
                class_item['headTeacher'] = '未设置'
            if 'id' not in class_item:
                class_item['id'] = f"class_{id(class_item)}"
            formatted_classes.append(class_item)
        return jsonify({'success': True, 'classes': formatted_classes, 'currentTeacher': current_teacher, 'teacherName': teacher_name, 'isAdmin': teacher_info.get('role') == 'admin'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/classes', methods=['POST'])
def create_class():
    try:
        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401
        if not is_admin():
            return jsonify({'success': False, 'message': '权限不足，只有管理员可以创建班级'}), 403
        class_data = request.json
        if not class_data or 'name' not in class_data:
            return jsonify({'success': False, 'message': '无效的班级数据'})
        success, message = add_class(class_data)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

@app.route('/api/classes/<class_name>', methods=['PUT'])
def update_class_api(class_name):
    try:
        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401
        if not is_admin():
            return jsonify({'success': False, 'message': '权限不足，只有管理员可以更新班级'}), 403
        class_data = request.json
        if not class_data or 'name' not in class_data:
            return jsonify({'success': False, 'message': '无效的班级数据'})
        success, message = update_class(class_name, class_data)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

@app.route('/api/classes/<class_name>', methods=['DELETE'])
def delete_single_class_api(class_name):
    try:
        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401
        if not is_admin():
            return jsonify({'success': False, 'message': '权限不足，只有管理员可以删除班级'}), 403
        success, message = delete_class(class_name)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

@app.route('/api/classes/batch-delete', methods=['DELETE'])
def batch_delete_classes_api():
    try:
        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401
        if not is_admin():
            return jsonify({'success': False, 'message': '权限不足，只有管理员可以批量删除班级'}), 403
        data = request.json
        if not data or 'classNames' not in data:
            return jsonify({'success': False, 'message': '缺少班级名称列表'})
        class_names = data['classNames']
        if not isinstance(class_names, list) or len(class_names) == 0:
            return jsonify({'success': False, 'message': '无效的班级名称列表'})
        success_count = 0
        error_count = 0
        errors = []
        for class_name in class_names:
            try:
                success, message = delete_class(class_name)
                if success:
                    success_count += 1
                else:
                    errors.append(f"班级 {class_name}: {message}")
                    error_count += 1
            except Exception as e:
                errors.append(f"班级 {class_name}: {str(e)}")
                error_count += 1
        if success_count > 0:
            result_message = f"成功删除 {success_count} 个班级"
            if error_count > 0:
                result_message += f"，失败 {error_count} 个"
            return jsonify({'success': True, 'message': result_message, 'successCount': success_count, 'errorCount': error_count})
        else:
            error_message = "删除失败"
            if errors:
                error_message += ": " + "; ".join(errors[:3])
            return jsonify({'success': False, 'message': error_message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

# ==================== 学生管理API ====================
@app.route('/api/students', methods=['GET'])
def get_students():
    try:
        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401
        if is_admin():
            students = get_all_students()
            return jsonify({'success': True, 'students': students})
        else:
            students = get_students_by_teacher(current_teacher)
            return jsonify({'success': True, 'students': students})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/students', methods=['POST'])
def add_student_api():
    try:
        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401
        if not is_admin():
            return jsonify({'success': False, 'message': '权限不足，只有管理员可以添加学生'}), 403
        student_data = request.json
        if not student_data or 'id' not in student_data:
            return jsonify({'success': False, 'message': '无效的学生数据'})
        success, message = add_student(student_data)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

@app.route('/api/students/batch', methods=['POST'])
def batch_add_students():
    try:
        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401
        if not is_admin():
            return jsonify({'success': False, 'message': '权限不足，只有管理员可以批量添加学生'}), 403
        students_data = request.json
        if not isinstance(students_data, list):
            return jsonify({'success': False, 'message': '无效的数据格式'})
        success, message = batch_update_students(students_data)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

@app.route('/api/students/<student_id>', methods=['DELETE'])
def delete_student_api(student_id):
    try:
        current_teacher = get_current_teacher()
        if not current_teacher:
            return jsonify({'success': False, 'message': '未登录'}), 401
        if not is_admin():
            return jsonify({'success': False, 'message': '权限不足，只有管理员可以删除学生'}), 403
        success, message = delete_student(student_id)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

# ==================== 站点配置接口 ====================
@app.route('/api/site-setup', methods=['GET'])
def get_site_setup():
    try:
        config = get_ai_config()
        site_setup = config.get('site_setup', {})
        return jsonify({'success': True, 'site_setup': site_setup})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ==================== 通用数据提交接口 ====================
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'zip', 'ppt', 'pptx', 'xls', 'xlsx', 'rar'}

def safe_teacher_path(teacher):
    # 禁止路径遍历字符
    if '..' in teacher or '/' in teacher or '\\' in teacher:
        return None
    # 可选：限制只允许中文、字母、数字、下划线、连字符
    # import re
    # if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9_\-]+$', teacher):
    #     return None
    base = os.path.realpath(os.path.join(TEMPLATE_FOLDER, teacher))
    templates_real = os.path.realpath(TEMPLATE_FOLDER)
    if not base.startswith(templates_real):
        return None
    return base

@app.route('/api/submit', methods=['POST'])
def api_submit():
    try:
        teacher = None
        activity_id = None
        student_id = None
        extra_data = {}
        files = []
        if request.files:
            teacher = request.form.get('teacher')
            activity_id = request.form.get('activity_id') or request.form.get('task')
            student_id = request.form.get('student_id')
            data_str = request.form.get('data')
            if data_str:
                try:
                    data_json = json.loads(data_str)
                    if not teacher and 'teacher' in data_json:
                        teacher = data_json['teacher']
                    if not activity_id and ('activity_id' in data_json or 'task' in data_json):
                        activity_id = data_json.get('activity_id') or data_json.get('task')
                    if not student_id and 'student_id' in data_json:
                        student_id = data_json['student_id']
                    for k, v in data_json.items():
                        if k not in ['teacher', 'activity_id', 'task', 'student_id']:
                            extra_data[k] = v
                except json.JSONDecodeError:
                    return jsonify({'success': False, 'message': 'data 字段 JSON 解析失败'}), 400
            for file in request.files.getlist('files'):
                if file and file.filename:
                    if not allowed_file(file.filename, ALLOWED_EXTENSIONS):
                        return jsonify({'success': False, 'message': f'文件类型不允许: {file.filename}'}), 400
                    files.append(file)
        else:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': '无效的 JSON 数据'}), 400
            teacher = data.get('teacher')
            activity_id = data.get('activity_id') or data.get('task')
            student_id = data.get('student_id')
            for k, v in data.items():
                if k not in ['teacher', 'activity_id', 'task', 'student_id']:
                    extra_data[k] = v
        if not teacher or not activity_id or not student_id:
            return jsonify({'success': False, 'message': '缺少必要字段: teacher, activity_id/task, student_id'}), 400
        teacher_base = safe_teacher_path(teacher)
        if not teacher_base:
            return jsonify({'success': False, 'message': '无效的教师用户名'}), 400
        data_dir = os.path.join(teacher_base, 'data', activity_id)
        upload_dir = os.path.join(teacher_base, 'uploads')
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(upload_dir, exist_ok=True)
        file_infos = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        for file in files:
            original_filename = file.filename
            if '.' in original_filename:
                ext = original_filename.rsplit('.', 1)[-1].lower()
            else:
                ext = ''
            saved_name = f"{timestamp}_{uuid.uuid4().hex[:8]}"
            if ext:
                saved_name += f".{ext}"
            filepath = os.path.join(upload_dir, saved_name)
            file.save(filepath)
            file_infos.append({
                'original_name': original_filename,
                'saved_name': saved_name,
                'size': os.path.getsize(filepath),
                'url': f'/templates/{teacher}/uploads/{saved_name}'
            })
        submission = {
            'teacher': teacher,
            'activity_id': activity_id,
            'student_id': student_id,
            '_server_timestamp': datetime.now().isoformat(),
            '_files': file_infos,
            **extra_data
        }
        json_filename = f"{timestamp}_{student_id}_{uuid.uuid4().hex[:8]}.json"
        json_path = os.path.join(data_dir, json_filename)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(submission, f, ensure_ascii=False, indent=2)
        return jsonify({'success': True, 'message': '提交成功', 'filename': json_filename, 'file_count': len(file_infos)}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

@app.route('/api/submissions', methods=['GET'])
def api_get_submissions():
    try:
        teacher = request.args.get('teacher')
        activity_id = request.args.get('activity_id')
        student_id = request.args.get('student_id')
        limit = request.args.get('limit', default=100, type=int)
        offset = request.args.get('offset', default=0, type=int)
        if limit > 500:
            limit = 500
        if not teacher:
            return jsonify({'success': False, 'message': '缺少必要参数: teacher'}), 400
        teacher_base = safe_teacher_path(teacher)
        if not teacher_base:
            return jsonify({'success': False, 'message': '无效的教师用户名'}), 400
        if activity_id:
            search_dir = os.path.join(teacher_base, 'data', activity_id)
            if not os.path.isdir(search_dir):
                return jsonify({'success': True, 'total': 0, 'offset': offset, 'limit': limit, 'submissions': []})
            walk_dirs = [(search_dir, [])]
        else:
            data_root = os.path.join(teacher_base, 'data')
            if not os.path.isdir(data_root):
                return jsonify({'success': True, 'total': 0, 'offset': offset, 'limit': limit, 'submissions': []})
            walk_dirs = []
            for root, dirs, files in os.walk(data_root):
                if root != data_root:
                    walk_dirs.append((root, []))
                dirs.clear()
        all_submissions = []
        for dirpath, _ in walk_dirs:
            for fname in os.listdir(dirpath):
                if not fname.endswith('.json'):
                    continue
                fpath = os.path.join(dirpath, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    continue
                if activity_id and data.get('activity_id') != activity_id:
                    continue
                if student_id and data.get('student_id') != student_id:
                    continue
                data['_meta'] = {'filename': fname, 'path': fpath}
                all_submissions.append(data)
        all_submissions.sort(key=lambda x: x.get('_server_timestamp', ''), reverse=True)
        total = len(all_submissions)
        paginated = all_submissions[offset:offset+limit]
        return jsonify({'success': True, 'total': total, 'offset': offset, 'limit': limit, 'submissions': paginated})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

# ==================== 远程同步 API（使用 remote_key 验证）====================
@app.route('/api/remote/user-info', methods=['GET'])
def remote_user_info():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': '未授权'}), 401
    token = auth_header.split(' ')[1]
    config = get_ai_config()
    if token != config.get('remote_key'):
        return jsonify({'success': False, 'message': '无效的授权'}), 403
    username = request.args.get('username')
    if not username:
        return jsonify({'success': False, 'message': '缺少用户名'}), 400
    accounts_data = load_accounts()
    for teacher in accounts_data['teachers']:
        if teacher['username'] == username:
            global_temp_key = config.get('temp_key', '')
            global_temp_key_expiry = config.get('temp_key_expiry', '')
            user_info = {
                'username': teacher['username'],
                'name': teacher.get('name', ''),
                'subject': teacher.get('subject', ''),
                'role': teacher.get('role', 'teacher'),
                'phone': teacher.get('phone', ''),
                'expiry_date': teacher.get('expiry_date', ''),
                'remaining_uses': teacher.get('remaining_uses', 0),
                'user_key': teacher.get('user_key', ''),
                'user_key_expiry': teacher.get('user_key_expiry', ''),
                'temp_key': global_temp_key,
                'temp_key_expiry': global_temp_key_expiry
            }
            return jsonify({'success': True, 'user': user_info})
    return jsonify({'success': False, 'message': '用户不存在'}), 404

@app.route('/api/remote/update-user', methods=['POST'])
def remote_update_user():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': '未授权'}), 401
    token = auth_header.split(' ')[1]
    config = get_ai_config()
    if token != config.get('remote_key'):
        return jsonify({'success': False, 'message': '无效的授权'}), 403
    data = request.json
    username = data.get('username')
    if not username:
        return jsonify({'success': False, 'message': '缺少用户名'}), 400
    accounts_data = load_accounts()
    updated = False
    for teacher in accounts_data['teachers']:
        if teacher['username'] == username:
            if 'remaining_uses' in data:
                teacher['remaining_uses'] = data['remaining_uses']
                updated = True
            if 'user_key' in data:
                teacher['user_key'] = data['user_key']
                updated = True
            if 'user_key_expiry' in data:
                teacher['user_key_expiry'] = data['user_key_expiry']
                updated = True
            if 'expiry_date' in data:
                teacher['expiry_date'] = data['expiry_date']
                updated = True
            break
    if updated:
        if save_accounts(accounts_data):
            return jsonify({'success': True, 'message': '更新成功'})
        else:
            return jsonify({'success': False, 'message': '保存失败'}), 500
    else:
        return jsonify({'success': False, 'message': '用户不存在或无更新'}), 404

# ==================== GUI 启动界面 ====================
def get_local_ips():
    ips = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith('127.'):
                ips.append(ip)
        if not ips:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ips.append(s.getsockname()[0])
            s.close()
    except Exception:
        ips = ['无法获取 IP']
    return ips

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def generate_access_url(ip, port):
    return f"http://{ip}" if port == 80 else f"http://{ip}:{port}"

def run_server(port):
    print(f"🚀 启动生产服务器 (Waitress)，端口 {port}")
    serve(app, host='0.0.0.0', port=port, threads=16, connection_limit=1000)

def load_and_resize_image(file_name, max_width=120):
    file_path = resource_path(file_name)
    if not os.path.exists(file_path):
        return None
    try:
        if PIL_AVAILABLE:
            pil_img = Image.open(file_path)
            w_percent = max_width / float(pil_img.size[0])
            h_size = int(float(pil_img.size[1]) * w_percent)
            pil_img = pil_img.resize((max_width, h_size), Image.LANCZOS)
            img = ImageTk.PhotoImage(pil_img)
            return img
        else:
            img = tk.PhotoImage(file=file_path)
            return img
    except Exception as e:
        print(f"❌ 加载图片 {file_name} 失败: {e}")
        return None

def clear_temp_key():
    config = get_ai_config()
    config['temp_key'] = ''
    config['temp_key_expiry'] = ''
    save_ai_config(config)
    print("🔑 本地 temp_key 已清空")

def mask_key(key):
    if not key:
        return "未设置"
    if not isinstance(key, str):
        key = str(key)
    if len(key) <= 8:
        return key
    return key[:4] + '*' * (len(key) - 8) + key[-4:]

def get_special_accounts():
    accounts_data = load_accounts()
    special_roles = ['admin', 'QF_school', 'QF_user']
    accounts = []
    for teacher in accounts_data['teachers']:
        role = teacher.get('role', '').strip()
        if role in special_roles:
            accounts.append(f"用户名: {teacher['username']} (姓名: {teacher.get('name', '')}) 角色: {role}")
    return accounts

def get_config_display():
    config = get_ai_config()
    lines = []
    lines.append(f"master_key: {mask_key(config.get('master_key', ''))}")
    lines.append(f"remote_key: {mask_key(config.get('remote_key', ''))}")
    lines.append(f"temp_key: {mask_key(config.get('temp_key', ''))}")
    lines.append(f"temp_key_expiry: {config.get('temp_key_expiry', '')}")
    lines.append(f"文本模型: {config.get('text_model', {}).get('model', '')}")
    lines.append(f"图像模型: {config.get('image_model', {}).get('model', '')}")
    lines.append(f"quickforge_URL: {config.get('site_setup', {}).get('quickforge_URL', '')}")
    return "\n".join(lines)

def create_gui(ips, port, description):
    global gui_logged_user_info, log_queue

    window = tk.Tk()
    
    config = get_ai_config()
    site_setup = config.get('site_setup', {})
    # 当前版本 = 运行中的版本
    current_version = site_setup.get('quickforge_version', '').strip()
    # 内置版本 = 默认配置中的版本（不受登录影响）
    builtin_version = DEFAULT_AI_CONFIG['site_setup']['quickforge_version'].strip()
    
    # 窗口标题去掉版本名称
    window.title("快铸网站AI生成发布系统")
    window.geometry("900x1000")
    window.resizable(False, False)

    default_font = font.nametofont("TkDefaultFont")
    default_font.configure(size=10)
    title_font = font.Font(size=12, weight="bold")
    small_font = font.Font(size=9)

    main_frame = tk.Frame(window)
    main_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

    # 登录框架，左右布局
    login_frame = tk.LabelFrame(main_frame, text="用户登录", font=title_font, padx=10, pady=10)
    login_frame.pack(fill=tk.X)

    # 左侧：登录表单 + 模型 + 地址
    left_frame = tk.Frame(login_frame)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

    quickforge_url = site_setup.get('quickforge_URL', '').strip()

    # 服务器地址
    addr_line = tk.Frame(left_frame)
    addr_line.pack(fill=tk.X, pady=2)
    tk.Label(addr_line, text="服务器地址:", font=default_font, width=10, anchor='w').pack(side=tk.LEFT)
    addr_label = tk.Label(addr_line, text="www.quickforge.cn", font=default_font, fg="blue", cursor="hand2")
    addr_label.pack(side=tk.LEFT, padx=5)
    if quickforge_url:
        addr_label.bind("<Button-1>", lambda e: webbrowser.open(quickforge_url))

    # 用户名
    user_line = tk.Frame(left_frame)
    user_line.pack(fill=tk.X, pady=2)
    tk.Label(user_line, text="用户名:", font=default_font, width=10, anchor='w').pack(side=tk.LEFT)
    username_entry = tk.Entry(user_line, font=default_font, width=25)
    username_entry.pack(side=tk.LEFT, padx=5)

    # 密码
    pass_line = tk.Frame(left_frame)
    pass_line.pack(fill=tk.X, pady=2)
    tk.Label(pass_line, text="密码:", font=default_font, width=10, anchor='w').pack(side=tk.LEFT)
    password_entry = tk.Entry(pass_line, font=default_font, width=25, show="*")
    password_entry.pack(side=tk.LEFT, padx=5)

    # ========== 新增：验证码区域（仅在配置远程地址时显示）==========
    captcha_frame = None
    current_captcha_token = None
    if quickforge_url:
        captcha_frame = tk.Frame(left_frame)
        captcha_frame.pack(fill=tk.X, pady=5)

        # 验证码图片显示标签（可显示文本和图像）
        captcha_image_label = tk.Label(captcha_frame, bg='white', text='加载验证码...', fg='gray')
        captcha_image_label.pack(side=tk.LEFT, padx=5)

        # 验证码输入框
        captcha_entry = tk.Entry(captcha_frame, font=default_font, width=10)
        captcha_entry.pack(side=tk.LEFT, padx=5)

        # 刷新验证码按钮
        refresh_btn = tk.Button(captcha_frame, text="刷新", command=lambda: load_captcha())
        refresh_btn.pack(side=tk.LEFT, padx=5)
    # =====================================

    # 按钮框架
    button_frame = tk.Frame(left_frame)
    button_frame.pack(pady=10)

    # 文本模型选择
    model_line = tk.Frame(left_frame)
    model_line.pack(fill=tk.X, pady=5)
    tk.Label(model_line, text="文本模型:", font=default_font, width=10, anchor='w').pack(side=tk.LEFT)
    model_var = tk.StringVar()
    model_dropdown = tk.OptionMenu(model_line, model_var, ())
    model_dropdown.config(state=tk.DISABLED, width=25)
    model_dropdown.pack(side=tk.LEFT, padx=5)

    def on_model_change(*args):
        selected_model = model_var.get()
        if selected_model:
            config = get_ai_config()
            config['text_model']['model'] = selected_model
            save_ai_config(config)
            print(f"✅ 文本模型已切换为: {selected_model}")

    model_var.trace('w', on_model_change)

    # 访问地址列表
    addr_desc_label = tk.Label(left_frame, text="内网访问地址：", font=default_font, anchor='w')
    addr_desc_label.pack(side=tk.LEFT)

    ip_frame = tk.Frame(left_frame)
    ip_frame.pack(side=tk.LEFT, padx=5)
    for ip in ips:
        url = generate_access_url(ip, port)
        link = tk.Label(ip_frame, text=url, fg="blue", cursor="hand2", font=default_font)
        link.pack(anchor='w')
        link.bind("<Button-1>", lambda e, url=url: webbrowser.open(url))

    # 右侧：特殊账号列表 + 配置信息 + 版本角色信息
    right_frame = tk.Frame(login_frame)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

    # 用户信息标签（显示登录用户）
    user_info_label = tk.Label(right_frame, text="未登录", font=small_font, fg="gray")
    user_info_label.pack(anchor='w', pady=2)

    # 登录类型标签
    login_type_label = tk.Label(right_frame, text="", font=small_font, fg="purple")
    login_type_label.pack(anchor='w', pady=2)

    # ===== 新增：版本与角色显示区域 =====
    version_role_label = tk.Label(right_frame, text="", font=small_font, fg="darkblue", justify=tk.LEFT)
    version_role_label.pack(anchor='w', pady=5)

    # 特殊账号列表
    special_accounts_label = tk.Label(right_frame, text="", font=small_font, fg="blue", justify=tk.LEFT)
    special_accounts_label.pack(anchor='w', pady=5)

    # 配置信息
    config_info_label = tk.Label(right_frame, text="", font=small_font, fg="darkgreen", justify=tk.LEFT)
    config_info_label.pack(anchor='w', pady=5)

    # 角色提示标签（放在整个login_frame下方）
    role_tip_label = tk.Label(main_frame, text="", font=small_font, fg="blue", wraplength=780, justify=tk.LEFT)
    role_tip_label.pack(pady=5)

    # ---------- 验证码加载函数 ----------
    def load_captcha():
        nonlocal current_captcha_token
        if not quickforge_url or captcha_frame is None:
            return  # 无远程地址时不加载验证码
        try:
            resp = requests.get(f"{quickforge_url.rstrip('/')}/api/captcha", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('success'):
                    current_captcha_token = data['token']
                    # 将 base64 图片显示到 GUI
                    img_data = base64.b64decode(data['image'].split(',')[1])
                    img = Image.open(io.BytesIO(img_data))
                    img.thumbnail((120, 40))
                    photo = ImageTk.PhotoImage(img)
                    captcha_image_label.config(image=photo, text='')  # 清除文本，显示图片
                    captcha_image_label.image = photo  # 保持引用
                    return
            # 请求失败或返回错误
            raise Exception("验证码服务返回错误")
        except Exception as e:
            print(f"加载验证码失败: {e}")
            # 在图片标签上显示错误提示
            captcha_image_label.config(image='', text='验证码加载失败', fg='red', font=small_font)
            current_captcha_token = None
    # ----------------------------------

    # ---------- 更新版本与角色显示 ---------- 
    def update_version_role_display():
        # 动态获取当前配置
        config = get_ai_config()
        site_setup = config.get('site_setup', {})
        current_disp = site_setup.get('quickforge_version', '').strip() or "未设置"
        # 内置版本始终从默认配置获取
        builtin_disp = DEFAULT_AI_CONFIG['site_setup']['quickforge_version'].strip() or "未设置"

        remote_role_disp = "未登录"
        local_role_disp = "未登录"
        if gui_logged_user_info:
            remote_role_disp = gui_logged_user_info.get('role', '未知')
            username = gui_logged_user_info.get('username')
            if username:
                accounts_data = load_accounts()
                teacher = next((t for t in accounts_data['teachers'] if t['username'] == username), None)
                local_role_disp = teacher.get('role', '未知') if teacher else '未知'

        text = (f"内置版本: {builtin_disp}\n"
                f"当前版本: {current_disp}\n"
                f"远程角色: {remote_role_disp}\n"
                f"本地角色: {local_role_disp}")
        version_role_label.config(text=text)
        # 同时更新角色提示标签
        update_role_tip_label()

    # ---------- 更新角色提示标签（根据登录状态和配置） ----------
    def update_role_tip_label():
        config = get_ai_config()
        site_setup = config.get('site_setup', {})
        current_version = site_setup.get('quickforge_version', 'basic')

        if gui_logged_user_info:
            role = gui_logged_user_info.get('role', '')
            # 根据远程角色或本地角色显示不同文本
            if role == 'school':
                text = "此用户已获校园版授权，可管理全校教师、全校学生、私有学生，全校教师可发布各自的网站，有设置公开和共享网站权限。"
            elif role == 'teacher':
                text = "此用户已获个人版授权，是个人版管理员，可登录管理私有学生账号，在个人账号目录内发布网站，有设置公开网站权限。"
            elif role == 'admin':
                text = f"此用户是远程系统管理员，本机当前授权为：{current_version}"
            else:
                # 本地登录可能无远程角色，根据当前版本显示
                if current_version == 'quickforge':
                    text = "本机当前授权为quickforge官网。"
                elif current_version == 'school':
                    text = "本机当前授权为校园版，可管理全校教师、全校学生、私有学生，全校教师可发布各自的网站，有设置公开和共享网站权限。"
                elif current_version == 'personal':
                    text = "本机当前授权为个人版，可登录管理私有学生账号，在个人账号目录内发布网站，有设置公开网站权限。"
                else:
                    text = "本机当前授权为基础版，可在pulblic目录下发布网站，支持交互网页以及数据采集和分析。内网首页为免登录游客页面，适合给学生上课使用。"
        else:
            # 未登录时显示基础版说明
            text = "本机当前授权为：{current_version}，软件未远程登录无法使用AI功能，登录后可切换为个人版，校园版。基础版只可在public目录下发布网站，支持交互网页以及数据采集和分析。内网首页为免登录游客页面，适合给学生上课使用。"

        role_tip_label.config(text=text, fg="blue")
    # -------------------------------------

    # 登录和注销按钮定义
    def gui_do_login():
        global gui_logged_user_info
        username = username_entry.get().strip()
        password = password_entry.get()
        if not username or not password:
            messagebox.showerror("登录错误", "用户名和密码不能为空")
            return

        config = get_ai_config()
        remote_url = config.get('site_setup', {}).get('quickforge_URL', '').strip()
        DEFAULT_VERSION = os.environ.get('AI_QUICKFORGE_VERSION', 'quickforge')  # 内置默认版本

        login_type = None

        # 如果配置了远程地址且验证码区域存在，则尝试远程登录
        if remote_url and captcha_frame is not None:
            # 获取验证码信息
            captcha_token = current_captcha_token
            captcha_code = captcha_entry.get().strip()
            if not captcha_token or not captcha_code:
                messagebox.showerror("错误", "请先获取验证码并输入")
                return

            try:
                login_resp = requests.post(
                    f"{remote_url.rstrip('/')}/api/login/teacher",
                    json={
                        'username': username,
                        'password': password,
                        'captcha_token': captcha_token,
                        'captcha_code': captcha_code
                    },
                    timeout=10
                )
                if login_resp.status_code == 200:
                    login_data = login_resp.json()
                    if login_data.get('success'):
                        login_type = "远程"
                        remote_user = login_data.get('user', {})
                        remote_username = remote_user.get('username')
                        if remote_username != username:
                            messagebox.showerror("登录失败", "远程返回的用户名不匹配")
                            return

                        remote_key = config.get('remote_key', '')
                        full_info = {}
                        if remote_key:
                            try:
                                info_resp = requests.get(
                                    f"{remote_url.rstrip('/')}/api/remote/user-info",
                                    params={'username': username},
                                    headers={'Authorization': f'Bearer {remote_key}'},
                                    timeout=5
                                )
                                if info_resp.status_code == 200:
                                    info_data = info_resp.json()
                                    if info_data.get('success'):
                                        full_info = info_data.get('user', {})
                            except Exception as e:
                                print(f"⚠️ 获取完整用户信息失败: {e}")

                        if not full_info:
                            full_info = {
                                'role': remote_user.get('role', ''),
                                'expiry_date': remote_user.get('expiry_date', ''),
                                'remaining_uses': remote_user.get('remaining_uses', 0),
                                'user_key': remote_user.get('user_key', ''),
                                'temp_key': remote_user.get('temp_key', ''),
                                'temp_key_expiry': remote_user.get('temp_key_expiry', '')
                            }

                        role = full_info.get('role', '')

                        # 权限检查：仅允许 school、admin、teacher 登录
                        if role not in ['school', 'admin', 'teacher']:
                            messagebox.showerror("登录失败", "您无权登录此系统（仅允许 school、admin、teacher）")
                            return

                        # ===== 根据角色更新系统版本 =====
                        if role == 'school':
                            config['site_setup']['quickforge_version'] = 'school'
                        elif role == 'teacher':
                            config['site_setup']['quickforge_version'] = 'personal'
                        elif role == 'admin':
                            config['site_setup']['quickforge_version'] = DEFAULT_VERSION
                        save_ai_config(config)
                        # ===== 版本更新结束 =====

                        expiry_date = full_info.get('expiry_date', '')
                        remaining_uses = full_info.get('remaining_uses', 0)
                        user_key = full_info.get('user_key', '')
                        remote_temp_key = full_info.get('temp_key', '')

                        # 根据角色处理临时密钥和配额
                        if role == 'school':
                            # 校园版：使用远程返回的 temp_key
                            valid = True
                            if expiry_date:
                                try:
                                    exp = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                                    if datetime.now().date() > exp:
                                        valid = False
                                except:
                                    pass
                            if remaining_uses <= 0:
                                valid = False

                            if valid:
                                config['temp_key'] = remote_temp_key
                                config['temp_key_expiry'] = full_info.get('temp_key_expiry', '')
                                config['expiry_date'] = expiry_date
                                config['remaining_uses'] = remaining_uses
                                save_ai_config(config)
                                accounts_data = load_accounts()
                                for teacher in accounts_data['teachers']:
                                    if teacher['username'] == username:
                                        teacher['expiry_date'] = expiry_date
                                        teacher['remaining_uses'] = remaining_uses
                                        break
                                save_accounts(accounts_data)
                                print("✅ school 有效，已更新 temp_key 和配额")
                            else:
                                config['expiry_date'] = expiry_date
                                config['remaining_uses'] = remaining_uses
                                save_ai_config(config)
                                accounts_data = load_accounts()
                                for teacher in accounts_data['teachers']:
                                    if teacher['username'] == username:
                                        teacher['expiry_date'] = expiry_date
                                        teacher['remaining_uses'] = remaining_uses
                                        break
                                save_accounts(accounts_data)
                                messagebox.showwarning("登录警告", "用户已过期或额度已用完，无法使用 AI 功能")
                                return

                        elif role == 'teacher':
                            # 个人版：使用 user_key
                            valid = True
                            if expiry_date:
                                try:
                                    exp = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                                    if datetime.now().date() > exp:
                                        valid = False
                                except:
                                    pass
                            if remaining_uses <= 0:
                                valid = False

                            if valid:
                                config['temp_key'] = user_key
                                config['temp_key_expiry'] = full_info.get('user_key_expiry', '')
                                config['expiry_date'] = expiry_date
                                config['remaining_uses'] = remaining_uses
                                save_ai_config(config)
                                accounts_data = load_accounts()
                                for teacher in accounts_data['teachers']:
                                    if teacher['username'] == username:
                                        teacher['expiry_date'] = expiry_date
                                        teacher['remaining_uses'] = remaining_uses
                                        break
                                save_accounts(accounts_data)
                                print("✅ teacher 有效，已用 user_key 更新 temp_key")
                            else:
                                config['expiry_date'] = expiry_date
                                config['remaining_uses'] = remaining_uses
                                save_ai_config(config)
                                accounts_data = load_accounts()
                                for teacher in accounts_data['teachers']:
                                    if teacher['username'] == username:
                                        teacher['expiry_date'] = expiry_date
                                        teacher['remaining_uses'] = remaining_uses
                                        break
                                save_accounts(accounts_data)
                                messagebox.showwarning("登录警告", "用户已过期或额度已用完，无法使用 AI 功能")
                                return

                        # admin 角色无需特殊处理密钥，保持原有逻辑

                        # 更新本地 accounts.json
                        accounts_data = load_accounts()
                        teacher_found = False
                        for teacher in accounts_data['teachers']:
                            if teacher['username'] == username:
                                teacher['name'] = remote_user.get('name', teacher.get('name', ''))
                                teacher['subject'] = remote_user.get('subject', teacher.get('subject', ''))
                                teacher['phone'] = remote_user.get('phone', teacher.get('phone', ''))
                                teacher['role'] = 'admin'
                                teacher_found = True
                                break

                        if not teacher_found:
                            new_teacher = {
                                'username': username,
                                'password': password,
                                'name': remote_user.get('name', username),
                                'phone': remote_user.get('phone', ''),
                                'email': '',
                                'role': 'admin',
                                'subject': remote_user.get('subject', ''),
                                'expiry_date': expiry_date,
                                'remaining_uses': remaining_uses,
                                'user_key': user_key,
                                'user_key_expiry': full_info.get('user_key_expiry', ''),
                                'createdAt': datetime.now().isoformat(),
                                'updatedAt': datetime.now().isoformat()
                            }
                            accounts_data['teachers'].append(new_teacher)

                        save_accounts(accounts_data)

                        set_current_user(username, {
                            'username': username,
                            'name': remote_user.get('name', username),
                            'subject': remote_user.get('subject', ''),
                            'role': 'admin',
                            'remote_role': role,
                            'expiry_date': expiry_date,
                            'remaining_uses': remaining_uses,
                            'user_key': user_key,
                            'user_key_expiry': full_info.get('user_key_expiry', '')
                        })

                        set_logged_user_key(user_key)

                        gui_logged_user_info = {
                            'username': username,
                            'name': remote_user.get('name', username),
                            'role': role,  # 远程角色
                            'remaining_uses': remaining_uses,
                            'expiry_date': expiry_date
                        }

                        expiry_display = expiry_date if expiry_date else '无限制'
                        user_info_label.config(text=f"登录用户: {username}  有效期: {expiry_display}")
                        login_type_label.config(text=f"登录类型: {login_type}")
                        special_accounts = get_special_accounts()
                        special_accounts_label.config(text="特殊账号列表:\n" + "\n".join(special_accounts) if special_accounts else "未找到特殊角色的账号", fg="blue")
                        config_info_label.config(text=get_config_display(), fg="darkgreen")

                        available_models = config.get('text_model', {}).get('available_models', [])
                        if available_models:
                            menu = model_dropdown['menu']
                            menu.delete(0, 'end')
                            for model in available_models:
                                menu.add_command(label=model, command=tk._setit(model_var, model))
                            model_var.set(config.get('text_model', {}).get('model', available_models[0]))
                            model_dropdown.config(state=tk.NORMAL)
                        login_btn.config(state=tk.DISABLED)
                        logout_btn.config(state=tk.NORMAL)

                        # 更新角色提示标签
                        update_role_tip_label()
                        load_teacher_data_to_memory(username)
                        # 更新版本与角色显示
                        update_version_role_display()
                        return
                    else:
                        # 登录失败，检查是否为验证码错误
                        msg = login_data.get('message', '')
                        if '验证码' in msg:
                            messagebox.showerror("登录失败", msg)
                            load_captcha()  # 刷新验证码
                            captcha_entry.delete(0, tk.END)
                            return
                        else:
                            # 其他错误，继续尝试本地登录
                            pass
            except Exception as e:
                print(f"⚠️ 远程登录请求异常，将尝试本地验证: {e}")

        # 本地验证
        accounts_data = load_accounts()
        teacher = next((t for t in accounts_data['teachers'] if t['username'] == username and t['password'] == password), None)
        if not teacher:
            messagebox.showerror("登录失败", "用户名或密码错误（本地验证）")
            return

        role = teacher.get('role', '')

        # 本地登录权限检查：仅允许 admin、teacher
        if role not in ['admin', 'teacher']:
            messagebox.showerror("登录失败", "您无权登录此系统（仅允许 admin、teacher）")
            return

        login_type = "本地"
        print(f"✅ 本地验证成功，用户 {username}，角色 {role}")

        # ===== 根据本地角色更新系统版本 =====
        if role == 'admin':
            config['site_setup']['quickforge_version'] = DEFAULT_VERSION
        elif role == 'teacher':
            config['site_setup']['quickforge_version'] = 'basic'
        save_ai_config(config)
        # ===== 版本更新结束 =====

        set_current_user(username, {
            'username': username,
            'name': teacher.get('name', ''),
            'subject': teacher.get('subject', ''),
            'role': teacher.get('role', 'teacher'),
            'expiry_date': teacher.get('expiry_date', ''),
            'remaining_uses': teacher.get('remaining_uses', 0),
            'user_key': teacher.get('user_key', ''),
            'user_key_expiry': teacher.get('user_key_expiry', '')
        })

        if role == 'teacher':
            config['temp_key'] = teacher.get('user_key', '')
            config['temp_key_expiry'] = teacher.get('user_key_expiry', '')
        else:
            config['temp_key'] = ''
            config['temp_key_expiry'] = ''
        save_ai_config(config)

        set_logged_user_key(teacher.get('user_key', ''))

        gui_logged_user_info = {
            'username': username,
            'name': teacher.get('name', ''),
            'role': role,  # 本地角色
            'remaining_uses': teacher.get('remaining_uses', 0),
            'expiry_date': teacher.get('expiry_date', '')
        }

        expiry_display = teacher.get('expiry_date', '') if teacher.get('expiry_date') else '无限制'
        user_info_label.config(text=f"登录用户: {username}  有效期: {expiry_display}")
        login_type_label.config(text=f"登录类型: {login_type}")
        special_accounts = get_special_accounts()
        special_accounts_label.config(text="特殊账号列表:\n" + "\n".join(special_accounts) if special_accounts else "未找到特殊角色的账号", fg="blue")
        config_info_label.config(text=get_config_display(), fg="darkgreen")

        available_models = config.get('text_model', {}).get('available_models', [])
        if available_models:
            menu = model_dropdown['menu']
            menu.delete(0, 'end')
            for model in available_models:
                menu.add_command(label=model, command=tk._setit(model_var, model))
            model_var.set(config.get('text_model', {}).get('model', available_models[0]))
            model_dropdown.config(state=tk.NORMAL)

        login_btn.config(state=tk.DISABLED)
        logout_btn.config(state=tk.NORMAL)

        # 更新角色提示标签
        update_role_tip_label()
        load_teacher_data_to_memory(username)
        # 更新版本与角色显示
        update_version_role_display()

    def gui_logout():
        global gui_logged_user_info
        current_teacher = get_current_teacher()
        if current_teacher:
            if 'current_teacher' in current_users:
                del current_users['current_teacher']
            if 'teacher_info' in current_users:
                del current_users['teacher_info']

        # ===== 新增：注销时版本恢复为基础版 =====
        config = get_ai_config()
        config['site_setup']['quickforge_version'] = 'basic'
        save_ai_config(config)
        # ===== 版本恢复结束 =====

        gui_logged_user_info = None
        user_info_label.config(text="未登录")
        login_type_label.config(text="")
        special_accounts_label.config(text="")
        config_info_label.config(text="")
        model_dropdown.config(state=tk.DISABLED)
        login_btn.config(state=tk.NORMAL)
        logout_btn.config(state=tk.DISABLED)
        clear_temp_key()
        # 更新角色提示标签
        update_role_tip_label()
        # 更新版本与角色显示
        update_version_role_display()
        print("👋 GUI 已退出登录")

    login_btn = tk.Button(button_frame, text="登录", command=gui_do_login, width=10)
    login_btn.pack(side=tk.LEFT, padx=5)

    logout_btn = tk.Button(button_frame, text="注销", command=gui_logout, state=tk.DISABLED, width=10)
    logout_btn.pack(side=tk.LEFT, padx=5)

    # 日志显示区域
    log_frame = tk.LabelFrame(main_frame, text="运行日志", font=title_font)
    log_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

    log_text = scrolledtext.ScrolledText(
        log_frame, height=12, wrap=tk.WORD,
        font=('Consolas', 9), state='normal'
    )
    log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def update_log():
        try:
            while True:
                msg = log_queue.get_nowait()
                log_text.insert(tk.END, msg)
                log_text.see(tk.END)
        except queue.Empty:
            pass
        window.after(100, update_log)

    update_log()

    desc_label = tk.Label(main_frame, text=description, justify=tk.LEFT, wraplength=780, font=small_font)
    desc_label.pack(pady=5, padx=10)
    tk.Frame(main_frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, padx=5, pady=5)
    tk.Label(main_frame, text="请勿关闭此窗口，否则服务将停止。", fg="gray").pack()

    bottom_frame = tk.Frame(main_frame)
    bottom_frame.pack(side=tk.BOTTOM, pady=10)

    left_frame = tk.Frame(bottom_frame)
    left_frame.pack(side=tk.LEFT, padx=30)
    tech_img = load_and_resize_image("statics/img/j.png")
    if tech_img:
        tech_label = tk.Label(left_frame, image=tech_img, cursor="hand2")
        tech_label.image = tech_img
        tech_label.pack()
        tech_label.bind("<Button-1>", lambda e: messagebox.showinfo("技术支持", "电话：13815120911\n微信同号"))
    else:
        tech_label = tk.Label(left_frame, text="技术支持", fg="blue", cursor="hand2", font=default_font)
        tech_label.pack()
        tech_label.bind("<Button-1>", lambda e: messagebox.showinfo("技术支持", "电话：13815120911\n微信同号"))
    tech_text = tk.Label(left_frame, text="技术支持", font=default_font)
    tech_text.pack()

    right_frame = tk.Frame(bottom_frame)
    right_frame.pack(side=tk.LEFT, padx=30)
    open_img = load_and_resize_image("statics/img/k.png")
    if open_img:
        open_label = tk.Label(right_frame, image=open_img, cursor="hand2")
        open_label.image = open_img
        open_label.pack()
        open_label.bind("<Button-1>", lambda e: webbrowser.open("https://gitee.com/xmicai/aiedtech/"))
    else:
        open_label = tk.Label(right_frame, text="开源地址", fg="blue", cursor="hand2", font=default_font)
        open_label.pack()
        open_label.bind("<Button-1>", lambda e: webbrowser.open("https://gitee.com/xmicai/aiedtech/"))
    open_text = tk.Label(right_frame, text="开源地址", font=default_font)
    open_text.pack()

    # 如果配置了远程 URL，自动加载验证码
    if quickforge_url:
        window.after(500, load_captcha)  # 延迟加载，避免窗口卡顿

    # 初始化版本与角色显示
    update_version_role_display()

    def on_closing():
        if messagebox.askokcancel("退出", "确定要停止服务吗？"):
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            if log_file:
                log_file.close()
            os._exit(0)

    window.protocol("WM_DELETE_WINDOW", on_closing)
    window.mainloop()
@app.route('/api/register/send-code', methods=['POST'])
def register_send_code():
    """注册专用：发送短信验证码"""
    try:
        data = request.json
        phone = data.get('phone', '').strip()
        if not phone:
            return jsonify({'success': False, 'message': '手机号不能为空'})

        # 验证手机号格式
        if not verify_phone_format(phone):
            return jsonify({'success': False, 'message': '手机号格式不正确'})

        # 检查手机号是否已被注册
        accounts_data = load_accounts()
        if any(t.get('phone') == phone for t in accounts_data['teachers']):
            return jsonify({'success': False, 'message': '该手机号已注册'})

        # 生成6位验证码
        sms_code = generate_sms_code()
        # 存入内存（有效期5分钟），注册时不需要关联用户名，username 设为 None
        sms_codes[phone] = {
            'code': sms_code,
            'username': None,
            'expires_at': time.time() + 300
        }

        print(f"📱 注册验证码发送到 {phone}: {sms_code}")
        # 调用短信发送服务（如果失败则返回模拟码）
        success, message = send_sms_verification(phone, sms_code, "5")
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            # 模拟模式返回验证码（用于测试环境）
            return jsonify({
                'success': True,
                'message': f'模拟发送: 验证码{sms_code}',
                'simulation': True,
                'code': sms_code
            })
    except Exception as e:
        print(f"❌ 注册发送验证码异常: {e}")
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500
# ==================== 系统初始化与启动降级 ====================
def initialize_role_downgrade():
    config = get_ai_config()
    site_setup = config.get('site_setup', {})
    quickforge_version = site_setup.get('quickforge_version', '').strip()
    accounts_data = load_accounts()
    modified = False

    if quickforge_version == 'personal':
        for teacher in accounts_data['teachers']:
            if teacher.get('role') != 'teacher':
                teacher['role'] = 'teacher'
                modified = True
        if modified:
            save_accounts(accounts_data)
            print("🔽 personal 模式：已将本地所有管理员角色降级为教师")
    elif quickforge_version == 'school':
        admin_exists = any(t.get('role') == 'admin' for t in accounts_data['teachers'])
        if not admin_exists:
            teach_user = next((t for t in accounts_data['teachers'] if t['username'] == 'teach'), None)
            if teach_user:
                teach_user['role'] = 'admin'
                modified = True
                print("🔝 school 模式：已将 teach 用户设置为管理员")
            else:
                if accounts_data['teachers']:
                    accounts_data['teachers'][0]['role'] = 'admin'
                    modified = True
                    print(f"🔝 school 模式：已将 {accounts_data['teachers'][0]['username']} 设置为管理员")
        if modified:
            save_accounts(accounts_data)
    else:
        print(f"ℹ️ 当前模式: {quickforge_version}，角色保持不变")

def initialize_system():
    print("🔧 初始化系统数据...")
    ensure_directories()
    try:
        teachers_data = load_teachers()
        shared_data = load_shared_data_to_memory()
        print("✅ 系统数据初始化成功")
        print(f"👨‍🏫 系统账号:")
        for teacher in teachers_data['teachers']:
            role = teacher.get('role', 'teacher')
            subject = teacher.get('subject', '未设置')
            print(f"  - {teacher['username']} ({'管理员' if role == 'admin' else '教师'}) - 学科: {subject}")
        initialize_role_downgrade()
    except Exception as e:
        print(f"❌ 致命错误: 无法加载 accounts.json，程序将退出。请检查文件或修复后重试。错误: {e}")
        sys.exit(1)

    config = get_ai_config()
    site_setup = config.get('site_setup', {})
    quickforge_version = site_setup.get('quickforge_version', '').strip()
    if quickforge_version == 'school':
        print("🏫 校园版服务已启动")
    elif quickforge_version == 'personal':
        print("🏠 个人版服务已启动")
    elif quickforge_version == 'quickforge':
        print("🌐 官网版服务已启动")
    else:
        print("ℹ️ 基础版服务已启动")
    
    return True

if __name__ == '__main__':
    # 初始化日志目录和文件，如果失败则使用临时目录
    try:
        os.makedirs(LOGS_FOLDER, exist_ok=True)
        log_filename = os.path.join(LOGS_FOLDER, f"app_{datetime.now().strftime('%Y%m%d')}.log")
        log_file = open(log_filename, 'a', encoding='utf-8')
    except Exception as e:
        # 如果日志目录不可写，则使用临时文件
        import tempfile
        log_file = tempfile.NamedTemporaryFile(mode='a', encoding='utf-8', suffix='.log', delete=False)
        log_filename = log_file.name
        print(f"⚠️ 无法写入日志目录 {LOGS_FOLDER}，使用临时文件: {log_filename}")

    sys.stdout = Tee('stdout', log_file)
    sys.stderr = Tee('stderr', log_file)

    try:
        initialize_folders()
        try:
            initialize_system()
            print("✅ 数据初始化成功")
        except Exception as e:
            print(f"❌ 数据初始化失败: {e}")
            # 尝试用消息框显示错误
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror("启动失败", f"数据初始化失败:\n{str(e)}\n\n请检查日志文件: {log_filename}")
                root.destroy()
            except:
                pass
            sys.exit(1)

        auto_save_thread = start_auto_save()

        if not TKINTER_AVAILABLE:
            print("⚠️ tkinter 不可用，将使用控制台模式")
            port = 80
            if is_port_in_use(port):
                port = 8080
            run_server(port)
            sys.exit(0)

        DEFAULT_PORT = 80
        PORT = DEFAULT_PORT
        if is_port_in_use(DEFAULT_PORT):
            print(f"端口 {DEFAULT_PORT} 已被占用，请选择其他端口")
            try:
                root = tk.Tk()
                root.withdraw()
                port_input = simpledialog.askinteger("端口选择", f"端口 {DEFAULT_PORT} 已被占用，请输入自定义端口（例如 8080）:", parent=root, minvalue=1024, maxvalue=65535)
                root.destroy()
                if port_input is None:
                    print("用户取消了操作，程序将退出")
                    sys.exit(0)
                PORT = port_input
            except Exception as e:
                print(f"端口选择对话框失败: {e}，将使用默认端口 8080")
                PORT = 8080

        local_ips = get_local_ips()
        if local_ips:
            main_ip = local_ips[0]
            access_url = generate_access_url(main_ip, PORT)
        else:
            main_ip = "127.0.0.1"
            access_url = generate_access_url(main_ip, PORT)

        description = """一句话生成互动网站，轻松实现作业发布评测、实时教学评价，制作发布网站和聊天一样简单！

一键生成和发布多用户内网数据采集分析、无需配置内置数据库、多套成熟模板、本地化隐私保护。

技术支持：快铸AI课题组  联系：13815120911 （微信同号）  官网地址：www.quickforge.cn"""

        print("\n" + "=" * 60)
        print("课堂互动教学评测系统")
        print("=" * 60)
        print(f"服务已启动，访问地址: {access_url}")
        if PORT != 80:
            print(f"使用端口: {PORT}")
        print("请勿关闭此窗口，否则服务将停止")
        print("=" * 60 + "\n")

        server_thread = threading.Thread(target=run_server, args=(PORT,), daemon=True)
        server_thread.start()

        create_gui(local_ips, PORT, description)
    except Exception as e:
        import traceback
        error_msg = f"程序发生未捕获的异常:\n{traceback.format_exc()}"
        print(error_msg)
        # 尝试用消息框显示错误
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("程序错误", error_msg)
            root.destroy()
        except:
            pass
        sys.exit(1)

app.register_blueprint(assignment_bp, url_prefix='/api')# ---------- 日志重定向与 GUI 日志显示 ----------

