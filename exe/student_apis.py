# student_apis.py - 学生端API
from flask import Blueprint, request, jsonify, g
import os
from datetime import datetime

from data_manager import (
    load_private_students, get_student_accessible_folders, check_student_folder_access,
    load_task_meta, get_current_teacher, is_admin
)

student_bp = Blueprint('student', __name__)

# 用于存储当前登录学生的信息（可改用session或token）
current_students = {}

def get_current_student():
    """获取当前登录的学生信息"""
    return current_students.get('current_student')

def set_current_student(student_info):
    """设置当前登录的学生"""
    current_students['current_student'] = student_info

# ==================== 学生登录接口 ====================
# 已在 app.py 中实现 /api/login/private-student，此处不再重复

# ==================== 学生可访问文件夹列表 ====================
@student_bp.route('/student/accessible-folders', methods=['GET'])
def get_accessible_folders():
    """获取当前学生可访问的文件夹列表"""
    student = get_current_student()
    if not student:
        return jsonify({'success': False, 'message': '未登录'}), 401

    teacher = student.get('teacher')
    if not teacher:
        return jsonify({'success': False, 'message': '学生所属教师信息缺失'}), 400

    folders = get_student_accessible_folders(teacher, student.get('id'))
    return jsonify({'success': True, 'folders': folders})

# ==================== 学生浏览文件夹内容 ====================
@student_bp.route('/student/folder-content', methods=['GET'])
def student_folder_content():
    """学生浏览指定文件夹内容，需要权限验证"""
    student = get_current_student()
    if not student:
        return jsonify({'success': False, 'message': '未登录'}), 401

    path = request.args.get('path', '')
    if not path:
        return jsonify({'success': False, 'message': '缺少路径参数'}), 400

    parts = path.split('/')
    if len(parts) < 2:
        return jsonify({'success': False, 'message': '路径格式错误'}), 400

    teacher, folder_name = parts[0], parts[1]
    subpath = '/'.join(parts[2:]) if len(parts) > 2 else ''

    # 验证学生所属教师是否匹配
    if teacher != student.get('teacher'):
        return jsonify({'success': False, 'message': '无权访问其他教师的文件夹'}), 403

    # 验证文件夹权限
    if not check_student_folder_access(teacher, folder_name, student.get('id')):
        return jsonify({'success': False, 'message': '无权访问该文件夹'}), 403

    # 安全拼接路径
    from teacher_apis import safe_join_path
    target_dir = safe_join_path(teacher, os.path.join(folder_name, subpath), target_teacher=teacher)
    if not target_dir or not os.path.isdir(target_dir):
        return jsonify({'success': False, 'message': '目录不存在'}), 404

    # 列出内容
    items = []
    for name in os.listdir(target_dir):
        if name.startswith('.') or name.endswith('.task.json'):
            continue
        full = os.path.join(target_dir, name)
        stat = os.stat(full)
        is_dir = os.path.isdir(full)
        item = {
            'name': name,
            'type': 'dir' if is_dir else 'file',
            'size': stat.st_size if not is_dir else 0,
            'modified': stat.st_mtime,
            'path': f'{teacher}/{folder_name}/{subpath}/{name}' if subpath else f'{teacher}/{folder_name}/{name}'
        }
        items.append(item)

    items.sort(key=lambda x: (x['type'] != 'dir', x['name']))
    return jsonify({'success': True, 'items': items, 'currentPath': path})