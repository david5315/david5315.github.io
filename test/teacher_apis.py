# teacher_apis.py - 教师核心教学业务功能 + 文件管理API（支持管理员维护templates下所有文件和目录）
from flask import Blueprint, request, jsonify, send_file
from datetime import datetime
import os
import time
import shutil
import zipfile
import uuid
import tempfile
import json
import re
from data_manager import secure_filename

from data_manager import (
    secure_filename,
    get_teacher_data, update_teacher_data, get_shared_data, update_shared_data,
    load_teachers, save_teachers, get_all_teachers_data,
    export_teacher_data, import_teacher_data, import_class_template,
    get_teacher_data_dir, load_teacher_data_to_memory,
    get_students_by_teacher, get_classes_for_teacher, get_all_classes_with_details,
    load_accounts, get_students_by_class, get_teacher_name_by_username,
    get_teacher_info, get_assignment_file_dir, save_assignment_file,
    get_file_icon, get_file_type_text, get_current_teacher, is_admin,
    save_task_meta, load_task_meta, get_all_public_folders,
    cleanup_assignment_files,
    load_private_students, save_private_students
)

teacher_bp = Blueprint('teacher', __name__)

# ==================== 工具函数 ====================

def safe_join_path(current_teacher, subpath, target_teacher=None):
    """
    安全拼接路径，防止路径遍历。
    如果 target_teacher 为空且当前用户是管理员，则基础为 templates 目录。
    否则基础为 templates/target_teacher 或 templates/current_teacher。
    """
    if is_admin() and not target_teacher:
        base = os.path.realpath('templates')
    else:
        if not target_teacher:
            target_teacher = current_teacher
        base = os.path.realpath(os.path.join('templates', target_teacher))
    
    target = os.path.realpath(os.path.join(base, subpath))
    if not target.startswith(base):
        return None
    return target

def is_in_templates(path):
    """判断绝对路径是否在 templates 目录下"""
    templates_dir = os.path.realpath('templates')
    return path.startswith(templates_dir)

# ==================== 文件管理API ====================

@teacher_bp.route('/teacher/files', methods=['GET'])
def list_files():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    path = request.args.get('path', '')
    target_teacher = request.args.get('teacher', current_teacher)
    is_admin_user = is_admin()

    if not target_teacher and not is_admin_user:
        return jsonify({'success': False, 'message': '无权访问根目录'}), 403

    target_dir = safe_join_path(current_teacher, path, target_teacher=target_teacher)
    if not target_dir:
        return jsonify({'success': False, 'message': '无效的路径'}), 400

    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    if not os.path.isdir(target_dir):
        stat = os.stat(target_dir)
        return jsonify({
            'success': True,
            'type': 'file',
            'name': os.path.basename(target_dir),
            'size': stat.st_size,
            'modified': stat.st_mtime,
            'path': path
        })

    items = []
    for name in os.listdir(target_dir):
        if name.endswith('.task.json'):
            continue
        if not target_teacher and name.startswith('.'):
            continue
        full = os.path.join(target_dir, name)
        stat = os.stat(full)
        is_dir = os.path.isdir(full)
        item = {
            'name': name,
            'type': 'dir' if is_dir else 'file',
            'size': stat.st_size if not is_dir else 0,
            'modified': stat.st_mtime,
            'path': os.path.join(path, name).replace('\\', '/')
        }
        if is_dir:
            if not target_teacher:
                if path and path.count('/') >= 1:
                    parts = path.split('/')
                    if len(parts) >= 2:
                        teacher_in_path = parts[1]
                        if teacher_in_path and os.path.exists(os.path.join('templates', teacher_in_path)):
                            meta = load_folder_meta(teacher_in_path, name)
                            item['public'] = meta.get('public', False)
                            item['allowOtherTeachers'] = meta.get('allowOtherTeachers', False)
                            item['allowPrivateStudents'] = meta.get('allowPrivateStudents', False)
                            item['allowGlobalStudents'] = meta.get('allowGlobalStudents', False)
            else:
                meta = load_folder_meta(target_teacher, name)
                item['public'] = meta.get('public', False)
                item['allowOtherTeachers'] = meta.get('allowOtherTeachers', False)
                item['allowPrivateStudents'] = meta.get('allowPrivateStudents', False)
                item['allowGlobalStudents'] = meta.get('allowGlobalStudents', False)
        items.append(item)

    items.sort(key=lambda x: (x['type'] != 'dir', x['name']))
    return jsonify({'success': True, 'items': items, 'currentPath': path})

@teacher_bp.route('/teacher/files/download', methods=['GET'])
def download_file():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    path = request.args.get('path', '')
    target_teacher = request.args.get('teacher', current_teacher)
    if target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权访问其他教师目录'}), 403

    target = safe_join_path(current_teacher, path, target_teacher=target_teacher)
    if not target or not os.path.isfile(target):
        return jsonify({'success': False, 'message': '文件不存在'}), 404

    return send_file(target, as_attachment=True, download_name=os.path.basename(target))

@teacher_bp.route('/assignment-templates', methods=['GET'])
def get_assignment_templates():
    current = get_current_teacher()
    if not current:
        return jsonify({'success': False, 'message': '未登录'}), 401
    shared = get_shared_data()
    return jsonify({'success': True, 'assignmentTemplates': shared.get('assignmentTemplates', [])})

@teacher_bp.route('/prompt-templates', methods=['GET'])
def get_prompt_templates():
    current = get_current_teacher()
    if not current:
        return jsonify({'success': False, 'message': '未登录'}), 401
    shared = get_shared_data()
    return jsonify({'success': True, 'promptTemplates': shared.get('promptTemplates', [])})

@teacher_bp.route('/teacher/files', methods=['DELETE'])
def delete_file():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.json
    path = data.get('path', '')
    confirm = data.get('confirm', False)
    target_teacher = data.get('teacher', current_teacher)
    if not confirm:
        return jsonify({'success': False, 'message': '请确认删除操作'}), 400

    if not target_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作根目录'}), 403
    if target_teacher and target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作其他教师目录'}), 403

    target = safe_join_path(current_teacher, path, target_teacher=target_teacher)
    if not target or not os.path.exists(target):
        return jsonify({'success': False, 'message': '路径不存在'}), 404

    if not target_teacher and not is_in_templates(target):
        return jsonify({'success': False, 'message': '无权删除此目录外的文件'}), 403

    if os.path.isdir(target):
        teacher_root = os.path.realpath(os.path.join('templates', current_teacher))
        if os.path.dirname(target) == teacher_root:
            basename = os.path.basename(target)
            if basename in ['data', 'uploads', 'ai_website']:
                return jsonify({
                    'success': False,
                    'message': f'禁止删除系统保护文件夹“{basename}”，您只能删除其中的文件'
                }), 403

    try:
        if os.path.isdir(target):
            shutil.rmtree(target)
        else:
            os.remove(target)
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@teacher_bp.route('/teacher/files/batch-delete', methods=['POST'])
def batch_delete_files():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.json
    paths = data.get('paths', [])
    target_teacher = data.get('teacher', current_teacher)
    if not paths:
        return jsonify({'success': False, 'message': '请选择要删除的路径'}), 400

    if not target_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作根目录'}), 403
    if target_teacher and target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作其他教师目录'}), 403

    success_count = 0
    errors = []
    for path in paths:
        target = safe_join_path(current_teacher, path, target_teacher=target_teacher)
        if not target or not os.path.exists(target):
            errors.append(f'{path}: 不存在')
            continue
        if not target_teacher and not is_in_templates(target):
            errors.append(f'{path}: 无权删除此目录外的文件')
            continue
        try:
            if os.path.isdir(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
            success_count += 1
        except Exception as e:
            errors.append(f'{path}: {str(e)}')
    return jsonify({
        'success': success_count > 0,
        'successCount': success_count,
        'errors': errors
    })

@teacher_bp.route('/teacher/upload', methods=['POST'])
def upload_file():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    target_path = request.form.get('path', '')
    target_teacher = request.form.get('teacher', current_teacher)

    if not target_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作根目录'}), 403
    if target_teacher and target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作其他教师目录'}), 403

    target_dir = safe_join_path(current_teacher, target_path, target_teacher=target_teacher)
    if not target_dir:
        return jsonify({'success': False, 'message': '无效的路径'}), 400

    if not target_teacher and not is_in_templates(target_dir):
        return jsonify({'success': False, 'message': '无权上传到此目录'}), 403

    os.makedirs(target_dir, exist_ok=True)

    uploaded_files = request.files.getlist('files')
    if not uploaded_files:
        return jsonify({'success': False, 'message': '没有文件'}), 400

    success_count = 0
    fail_count = 0
    errors = []

    for file in uploaded_files:
        if file.filename == '':
            fail_count += 1
            errors.append('空文件名')
            continue

        raw_filename = file.filename
        parts = raw_filename.replace('\\', '/').split('/')
        safe_parts = []
        for part in parts:
            if not part:
                continue
            safe_part = secure_filename(part)
            if not safe_part:
                safe_part = '_'
            safe_parts.append(safe_part)
        if not safe_parts:
            fail_count += 1
            errors.append(f'无效的文件名: {raw_filename}')
            continue

        *dir_parts, filename = safe_parts
        subdir = os.path.join(*dir_parts) if dir_parts else ''
        dest_subdir = os.path.join(target_dir, subdir)
        os.makedirs(dest_subdir, exist_ok=True)

        dest_file = os.path.join(dest_subdir, filename)
        if os.path.exists(dest_file):
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(os.path.join(dest_subdir, f"{base}_{counter}{ext}")):
                counter += 1
            dest_file = os.path.join(dest_subdir, f"{base}_{counter}{ext}")

        try:
            file.save(dest_file)
            success_count += 1
        except Exception as e:
            fail_count += 1
            errors.append(f'{raw_filename}: {str(e)}')

    return jsonify({
        'success': success_count > 0,
        'message': f'上传完成，成功 {success_count} 个，失败 {fail_count} 个',
        'successCount': success_count,
        'failCount': fail_count,
        'errors': errors
    })

# ==================== 修改：新建文件夹（支持模板和描述）====================
@teacher_bp.route('/teacher/folder', methods=['POST'])
def create_folder():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.json
    path = data.get('path', '')
    name = data.get('name', '').strip()
    template = data.get('template', '')
    description = data.get('description', '')
    target_teacher = data.get('teacher', current_teacher)

    if not name:
        return jsonify({'success': False, 'message': '文件夹名称不能为空'}), 400

    if not target_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作根目录'}), 403
    if target_teacher and target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作其他教师目录'}), 403

    target_dir = safe_join_path(current_teacher, path, target_teacher=target_teacher)
    if not target_dir:
        return jsonify({'success': False, 'message': '无效的路径'}), 400

    if not target_teacher and not is_in_templates(target_dir):
        return jsonify({'success': False, 'message': '无权在此处创建文件夹'}), 403

    new_folder = os.path.join(target_dir, name)
    if os.path.exists(new_folder):
        return jsonify({'success': False, 'message': '文件夹已存在'}), 400

    try:
        os.makedirs(new_folder)
        if target_teacher:
            goal = ''
            if template == 'data_collection':
                goal = '收集用户输入数据并存储到服务器'
            elif template == 'statistics':
                goal = '对已有数据进行统计分析和可视化展示'
            elif template == 'qa':
                goal = '提供互动问答功能，记录学生回答'
            meta = {
                'name': name,
                'createdAt': datetime.now().isoformat(),
                'public': False,
                'allowOtherTeachers': False,
                'allowPrivateStudents': False,
                'allowGlobalStudents': False,
                'creator': current_teacher,
                'template': template,
                'description': description,
                'goal': goal
            }
            save_task_meta(target_teacher, name, meta)
        return jsonify({'success': True, 'message': '文件夹创建成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@teacher_bp.route('/teacher/folder-content', methods=['GET'])
def get_folder_content():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    teacher = request.args.get('teacher')
    path = request.args.get('path', '')

    if not teacher:
        return jsonify({'success': False, 'message': '缺少教师参数'}), 400

    target_dir = safe_join_path(current_teacher, path, target_teacher=teacher)
    if not target_dir or not os.path.isdir(target_dir):
        return jsonify({'success': False, 'message': '目录不存在'}), 404

    if teacher != current_teacher:
        folder_name = path.split('/')[-1] if path else ''
        if folder_name:
            meta = load_folder_meta(teacher, folder_name)
            if not meta.get('public', False):
                return jsonify({'success': False, 'message': '该文件夹未公开，无权访问'}), 403
        elif not path:
            return jsonify({'success': False, 'message': '无法访问根目录'}), 403

    items = []
    for name in os.listdir(target_dir):
        full = os.path.join(target_dir, name)
        stat = os.stat(full)
        is_dir = os.path.isdir(full)
        item = {
            'name': name,
            'type': 'dir' if is_dir else 'file',
            'size': stat.st_size if not is_dir else 0,
            'modified': stat.st_mtime,
            'path': os.path.join(path, name).replace('\\', '/')
        }
        if is_dir:
            meta = load_folder_meta(teacher, os.path.join(path, name))
            item['public'] = meta.get('public', False)
            item['allowOtherTeachers'] = meta.get('allowOtherTeachers', False)
            item['allowPrivateStudents'] = meta.get('allowPrivateStudents', False)
            item['allowGlobalStudents'] = meta.get('allowGlobalStudents', False)
        items.append(item)

    items.sort(key=lambda x: (x['type'] != 'dir', x['name']))
    return jsonify({'success': True, 'items': items})

@teacher_bp.route('/teacher/rename', methods=['POST'])
def rename_file():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.json
    path = data.get('path')
    new_name = data.get('newName')
    target_teacher = data.get('teacher', current_teacher)

    if not path or not new_name:
        return jsonify({'success': False, 'message': '缺少参数'}), 400

    if not target_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作根目录'}), 403
    if target_teacher and target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作其他教师目录'}), 403

    target = safe_join_path(current_teacher, path, target_teacher=target_teacher)
    if not target or not os.path.exists(target):
        return jsonify({'success': False, 'message': '路径不存在'}), 404

    if '/' in new_name or '\\' in new_name:
        return jsonify({'success': False, 'message': '名称不能包含路径分隔符'}), 400

    parent_dir = os.path.dirname(target)
    new_path = os.path.join(parent_dir, new_name)
    if os.path.exists(new_path):
        return jsonify({'success': False, 'message': '目标名称已存在'}), 400

    try:
        os.rename(target, new_path)
        return jsonify({'success': True, 'message': '重命名成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@teacher_bp.route('/teacher/move', methods=['POST'])
def move_files():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.json
    source_paths = data.get('sourcePaths', [])
    dest_path = data.get('destPath')
    target_teacher = data.get('teacher', current_teacher)

    if not source_paths or not dest_path:
        return jsonify({'success': False, 'message': '缺少参数'}), 400

    if not target_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作根目录'}), 403
    if target_teacher and target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作其他教师目录'}), 403

    dest_full = safe_join_path(current_teacher, dest_path, target_teacher=target_teacher)
    if not dest_full or not os.path.isdir(dest_full):
        return jsonify({'success': False, 'message': '目标目录不存在'}), 404

    results = []
    for src_path in source_paths:
        src_full = safe_join_path(current_teacher, src_path, target_teacher=target_teacher)
        if not src_full or not os.path.exists(src_full):
            results.append({'path': src_path, 'success': False, 'message': '源路径不存在'})
            continue

        if src_full == dest_full or dest_full.startswith(src_full + os.sep):
            results.append({'path': src_path, 'success': False, 'message': '不能将父目录移动到子目录内'})
            continue

        base_name = os.path.basename(src_full)
        dest_file = os.path.join(dest_full, base_name)
        if os.path.exists(dest_file):
            name, ext = os.path.splitext(base_name)
            counter = 1
            while os.path.exists(os.path.join(dest_full, f"{name}_{counter}{ext}")):
                counter += 1
            dest_file = os.path.join(dest_full, f"{name}_{counter}{ext}")

        try:
            shutil.move(src_full, dest_file)
            results.append({'path': src_path, 'success': True, 'dest': os.path.basename(dest_file)})
        except Exception as e:
            results.append({'path': src_path, 'success': False, 'message': str(e)})

    return jsonify({'success': True, 'results': results})

@teacher_bp.route('/teacher/copy', methods=['POST'])
def copy_files():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.json
    source_paths = data.get('sourcePaths', [])
    dest_path = data.get('destPath')
    target_teacher = data.get('teacher', current_teacher)

    if not source_paths or not dest_path:
        return jsonify({'success': False, 'message': '缺少参数'}), 400

    if not target_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作根目录'}), 403
    if target_teacher and target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作其他教师目录'}), 403

    dest_full = safe_join_path(current_teacher, dest_path, target_teacher=target_teacher)
    if not dest_full or not os.path.isdir(dest_full):
        return jsonify({'success': False, 'message': '目标目录不存在'}), 404

    results = []
    for src_path in source_paths:
        src_full = safe_join_path(current_teacher, src_path, target_teacher=target_teacher)
        if not src_full or not os.path.exists(src_full):
            results.append({'path': src_path, 'success': False, 'message': '源路径不存在'})
            continue

        base_name = os.path.basename(src_full)
        dest_file = os.path.join(dest_full, base_name)
        if os.path.exists(dest_file):
            name, ext = os.path.splitext(base_name)
            counter = 1
            while os.path.exists(os.path.join(dest_full, f"{name}_{counter}{ext}")):
                counter += 1
            dest_file = os.path.join(dest_full, f"{name}_{counter}{ext}")

        try:
            if os.path.isdir(src_full):
                shutil.copytree(src_full, dest_file)
            else:
                shutil.copy2(src_full, dest_file)
            results.append({'path': src_path, 'success': True, 'dest': os.path.basename(dest_file)})
        except Exception as e:
            results.append({'path': src_path, 'success': False, 'message': str(e)})

    return jsonify({'success': True, 'results': results})

@teacher_bp.route('/teacher/download-zip', methods=['POST'])
def download_zip():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.json
    paths = data.get('paths', [])
    target_teacher = data.get('teacher', current_teacher)
    zip_name = data.get('zipName', 'archive.zip')

    if not paths:
        return jsonify({'success': False, 'message': '请选择要打包的路径'}), 400

    if not target_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作根目录'}), 403
    if target_teacher and target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作其他教师目录'}), 403

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, secure_filename(zip_name))

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for path in paths:
                full = safe_join_path(current_teacher, path, target_teacher=target_teacher)
                if not full or not os.path.exists(full):
                    continue
                if os.path.isdir(full):
                    for root, dirs, files in os.walk(full):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(full))
                            zf.write(file_path, arcname)
                else:
                    zf.write(full, os.path.basename(full))

        return send_file(zip_path, as_attachment=True, download_name=zip_name)
    except Exception as e:
        return jsonify({'success': False, 'message': f'打包失败: {str(e)}'}), 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@teacher_bp.route('/teacher/extract', methods=['POST'])
def extract_zip():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.json
    zip_path = data.get('zipPath')
    target_path = data.get('targetPath', os.path.dirname(zip_path))
    target_teacher = data.get('teacher', current_teacher)

    if not zip_path:
        return jsonify({'success': False, 'message': '缺少ZIP文件路径'}), 400

    if not target_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作根目录'}), 403
    if target_teacher and target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作其他教师目录'}), 403

    zip_full = safe_join_path(current_teacher, zip_path, target_teacher=target_teacher)
    target_full = safe_join_path(current_teacher, target_path, target_teacher=target_teacher)

    if not zip_full or not os.path.isfile(zip_full) or not zip_full.lower().endswith('.zip'):
        return jsonify({'success': False, 'message': 'ZIP文件不存在或格式错误'}), 404
    if not target_full or not os.path.isdir(target_full):
        return jsonify({'success': False, 'message': '目标目录不存在'}), 404

    try:
        with zipfile.ZipFile(zip_full, 'r') as zf:
            zf.extractall(target_full)
        return jsonify({'success': True, 'message': '解压成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'解压失败: {str(e)}'}), 500

@teacher_bp.route('/teacher/search', methods=['GET'])
def search_files():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    keyword = request.args.get('keyword', '').strip()
    scope = request.args.get('scope', 'current')
    current_path = request.args.get('path', '')
    target_teacher = request.args.get('teacher', current_teacher)

    if not keyword:
        return jsonify({'success': False, 'message': '请输入搜索关键词'}), 400

    if not target_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权搜索根目录'}), 403
    if target_teacher and target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权搜索其他教师目录'}), 403

    if scope == 'current':
        base_dir = safe_join_path(current_teacher, current_path, target_teacher=target_teacher)
        if not base_dir or not os.path.isdir(base_dir):
            return jsonify({'success': False, 'message': '当前目录不存在'}), 404
    else:
        if is_admin() and not target_teacher:
            base_dir = os.path.realpath('templates')
        else:
            base_dir = safe_join_path(current_teacher, '', target_teacher=target_teacher)

    results = []
    try:
        for root, dirs, files in os.walk(base_dir):
            rel_root = os.path.relpath(root, base_dir)
            if rel_root == '.':
                rel_root = ''

            for d in dirs:
                if keyword.lower() in d.lower():
                    full_path = os.path.join(root, d)
                    rel_path = os.path.join(rel_root, d) if rel_root else d
                    results.append({
                        'name': d,
                        'type': 'dir',
                        'path': rel_path,
                        'full_path': full_path,
                        'size': 0,
                        'modified': os.path.getmtime(full_path)
                    })

            for f in files:
                if keyword.lower() in f.lower():
                    full_path = os.path.join(root, f)
                    rel_path = os.path.join(rel_root, f) if rel_root else f
                    results.append({
                        'name': f,
                        'type': 'file',
                        'path': rel_path,
                        'full_path': full_path,
                        'size': os.path.getsize(full_path),
                        'modified': os.path.getmtime(full_path)
                    })

        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ==================== 公开/共享文件夹接口 ====================

@teacher_bp.route('/public/folders', methods=['GET'])
def get_public_folders():
    """获取所有公开的文件夹（任何登录用户可访问），返回深度不超过3的目录"""
    try:
        folders = get_all_public_folders()
        filtered = [f for f in folders if f['path'].count('/') <= 2]
        return jsonify({'success': True, 'folders': filtered})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@teacher_bp.route('/teacher/shared-folders', methods=['GET'])
def get_shared_folders():
    """
    获取当前教师可访问的其他教师共享文件夹列表，返回深度不超过3的目录
    """
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    try:
        accounts_data = load_accounts()
        all_teachers = [t['username'] for t in accounts_data.get('teachers', []) if t['username'] != current_teacher]
        shared_folders = []

        for teacher in all_teachers:
            teacher_dir = os.path.join('templates', teacher)
            if not os.path.isdir(teacher_dir):
                continue
            for root, dirs, files in os.walk(teacher_dir):
                for dir_name in dirs:
                    folder_path = os.path.join(root, dir_name)
                    rel_path = os.path.relpath(folder_path, 'templates').replace('\\', '/')
                    depth = rel_path.count('/')
                    if depth > 2:
                        continue
                    meta_path = os.path.join(folder_path, '.task.json')
                    meta = {}
                    if os.path.exists(meta_path):
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                    if meta.get('public', False) or meta.get('allowOtherTeachers', False):
                        shared_folders.append({
                            'teacher': teacher,
                            'folderName': dir_name,
                            'path': rel_path,
                            'meta': meta
                        })
        return jsonify({'success': True, 'folders': shared_folders})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@teacher_bp.route('/public/folder-content', methods=['GET'])
def public_folder_content():
    full_path = request.args.get('path', '')
    if not full_path:
        return jsonify({'success': False, 'message': '缺少路径参数'}), 400

    if not check_path_public(full_path):
        return jsonify({'success': False, 'message': '文件夹未公开或无权访问'}), 403

    parts = full_path.split('/')
    teacher = parts[0]
    subpath = '/'.join(parts[1:])

    base = os.path.realpath(os.path.join('templates', teacher))
    target_dir = os.path.realpath(os.path.join(base, subpath))
    if not target_dir.startswith(base) or not os.path.isdir(target_dir):
        return jsonify({'success': False, 'message': '目录不存在'}), 404

    items = []
    for name in os.listdir(target_dir):
        if name.endswith('.task.json') or name.startswith('.'):
            continue
        full = os.path.join(target_dir, name)
        stat = os.stat(full)
        is_dir = os.path.isdir(full)
        items.append({
            'name': name,
            'type': 'dir' if is_dir else 'file',
            'size': stat.st_size if not is_dir else 0,
            'modified': stat.st_mtime,
            'path': os.path.join(full_path, name).replace('\\', '/')
        })
    items.sort(key=lambda x: (x['type'] != 'dir', x['name']))
    return jsonify({'success': True, 'items': items})

# ==================== 任务元数据管理 ====================

@teacher_bp.route('/teacher/tasks', methods=['GET'])
def get_tasks():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    base = os.path.join('templates', current_teacher)
    if not os.path.exists(base):
        return jsonify({'success': True, 'tasks': []})

    tasks = []
    for name in os.listdir(base):
        task_dir = os.path.join(base, name)
        if not os.path.isdir(task_dir):
            continue
        meta = load_task_meta(current_teacher, name)
        tasks.append({
            'name': name,
            'meta': meta,
            'url': f'/templates/{current_teacher}/{name}/index.html'
        })
    return jsonify({'success': True, 'tasks': tasks})

@teacher_bp.route('/teacher/tasks/<task_name>', methods=['GET'])
def get_task_meta_route(task_name):
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401
    
    target_teacher = request.args.get('teacher', current_teacher)
    if target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权访问'}), 403
    
    if not target_teacher:
        return jsonify({'success': False, 'message': '根目录模式下需要明确指定教师'}), 400
    
    meta = load_task_meta(target_teacher, task_name)
    return jsonify({'success': True, 'meta': meta})

@teacher_bp.route('/teacher/tasks/<task_name>', methods=['PUT'])
def update_task_meta_route(task_name):
    """更新任务元数据"""
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401
    
    target_teacher = request.args.get('teacher')
    if not target_teacher:
        return jsonify({'success': False, 'message': '更新元数据必须指定教师'}), 403
    
    if target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作'}), 403
    
    data = request.json
    old_meta = load_task_meta(target_teacher, task_name)
    
    import json
    config_file = 'ai.json'
    site_setup = {}
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            site_setup = config.get('site_setup', {})
    
    public_for_teacher = site_setup.get('public_file_for_teacher') == 'true'
    
    if not is_admin() and public_for_teacher:
        if 'public' in data:
            old_meta['public'] = data['public']
    else:
        old_meta.update(data)
    
    if not save_task_meta(target_teacher, task_name, old_meta):
        return jsonify({'success': False, 'message': '保存失败'}), 500

    return jsonify({'success': True, 'message': '更新成功'})

@teacher_bp.route('/teacher/tasks/<task_name>', methods=['DELETE'])
def delete_task(task_name):
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    target_dir = safe_join_path(current_teacher, task_name, target_teacher=current_teacher)
    if not target_dir or not os.path.isdir(target_dir):
        return jsonify({'success': False, 'message': '任务不存在'}), 404

    try:
        shutil.rmtree(target_dir)
        return jsonify({'success': True, 'message': '任务删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ==================== 私有学生管理 API ====================

@teacher_bp.route('/teacher/private-students', methods=['GET'])
def get_private_students():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401
    students = load_private_students(current_teacher)
    return jsonify({'success': True, 'students': students})

@teacher_bp.route('/teacher/private-students', methods=['POST'])
def add_private_student():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401
    data = request.json
    student_id = data.get('id')
    name = data.get('name')
    password = data.get('password', '123456')
    if not student_id or not name:
        return jsonify({'success': False, 'message': '学号和姓名不能为空'}), 400
    students = load_private_students(current_teacher)
    if any(s['id'] == student_id for s in students):
        return jsonify({'success': False, 'message': '学号已存在'}), 400
    new_student = {
        'id': student_id,
        'name': name,
        'password': password,
        'class': data.get('class', '')
    }
    students.append(new_student)
    if save_private_students(current_teacher, students):
        return jsonify({'success': True, 'message': '添加成功', 'student': new_student})
    else:
        return jsonify({'success': False, 'message': '保存失败'}), 500

@teacher_bp.route('/teacher/private-students/batch', methods=['POST'])
def batch_add_private_students():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401
    data = request.json
    if not isinstance(data, list):
        return jsonify({'success': False, 'message': '数据格式错误，应为数组'}), 400
    students = load_private_students(current_teacher)
    added = 0
    errors = []
    existing_ids = {s['id'] for s in students}
    for item in data:
        student_id = item.get('id')
        if not student_id:
            errors.append({'id': '未知', 'reason': '缺少学号'})
            continue
        if student_id in existing_ids:
            errors.append({'id': student_id, 'reason': '学号已存在'})
            continue
        name = item.get('name', '')
        if not name:
            name = f'学生{student_id}'
        password = item.get('password', '123456')
        new_student = {
            'id': student_id,
            'name': name,
            'password': password,
            'class': item.get('class', '')
        }
        students.append(new_student)
        existing_ids.add(student_id)
        added += 1
    if added > 0:
        if save_private_students(current_teacher, students):
            return jsonify({'success': True, 'message': f'成功添加 {added} 名学生', 'errors': errors})
        else:
            return jsonify({'success': False, 'message': '保存失败'}), 500
    else:
        return jsonify({'success': False, 'message': '没有可添加的学生', 'errors': errors})

@teacher_bp.route('/teacher/private-students/<student_id>', methods=['PUT'])
def update_private_student(student_id):
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401
    data = request.json
    students = load_private_students(current_teacher)
    for i, s in enumerate(students):
        if s['id'] == student_id:
            if 'name' in data:
                students[i]['name'] = data['name']
            if 'password' in data and data['password']:
                students[i]['password'] = data['password']
            if 'class' in data:
                students[i]['class'] = data['class']
            if save_private_students(current_teacher, students):
                return jsonify({'success': True, 'message': '更新成功'})
            else:
                return jsonify({'success': False, 'message': '保存失败'}), 500
    return jsonify({'success': False, 'message': '学生不存在'}), 404

@teacher_bp.route('/teacher/private-students/<student_id>', methods=['DELETE'])
def delete_private_student(student_id):
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401
    students = load_private_students(current_teacher)
    new_students = [s for s in students if s['id'] != student_id]
    if len(new_students) == len(students):
        return jsonify({'success': False, 'message': '学生不存在'}), 404
    if save_private_students(current_teacher, new_students):
        return jsonify({'success': True, 'message': '删除成功'})
    else:
        return jsonify({'success': False, 'message': '保存失败'}), 500

@teacher_bp.route('/teacher/private-students/batch-delete', methods=['POST'])
def batch_delete_private_students():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401
    data = request.json
    student_ids = data.get('studentIds', [])
    if not student_ids:
        return jsonify({'success': False, 'message': '请选择要删除的学生'}), 400
    students = load_private_students(current_teacher)
    new_students = [s for s in students if s['id'] not in student_ids]
    deleted_count = len(students) - len(new_students)
    if deleted_count == 0:
        return jsonify({'success': False, 'message': '没有找到匹配的学生'}), 404
    if save_private_students(current_teacher, new_students):
        return jsonify({'success': True, 'message': f'成功删除 {deleted_count} 名学生'})
    else:
        return jsonify({'success': False, 'message': '保存失败'}), 500

@teacher_bp.route('/teacher/private-students/reset-password', methods=['POST'])
def reset_private_students_password():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401
    data = request.json
    student_ids = data.get('studentIds', [])
    new_password = data.get('newPassword', '123456')
    students = load_private_students(current_teacher)
    updated = 0
    for s in students:
        if s['id'] in student_ids:
            s['password'] = new_password
            updated += 1
    if updated > 0:
        if save_private_students(current_teacher, students):
            return jsonify({'success': True, 'message': f'成功重置 {updated} 名学生密码'})
        else:
            return jsonify({'success': False, 'message': '保存失败'}), 500
    else:
        return jsonify({'success': False, 'message': '没有找到匹配的学生'}), 404

# ==================== 辅助函数 ====================

def load_folder_meta(teacher, folder_rel_path):
    """加载指定文件夹（可能多级）的元数据，返回 dict"""
    folder_full_path = os.path.join('templates', teacher, folder_rel_path)
    meta_path = os.path.join(folder_full_path, '.task.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def check_path_public(full_path):
    """
    检查完整路径（格式 teacher/folder/subfolder...）是否允许游客访问。
    简化规则：只检查第一级文件夹（teacher/folder）是否公开，若公开则其下所有内容均可访问。
    """
    parts = full_path.split('/')
    if len(parts) < 2:
        return False
    teacher = parts[0]
    first_folder = parts[1]
    meta = load_folder_meta(teacher, first_folder)
    return meta.get('public', False)

def get_all_public_folders_recursive(base_dir='templates'):
    """递归获取所有公开文件夹的完整路径（teacher/folder/subfolder...）"""
    public_folders = []
    if not os.path.exists(base_dir):
        return public_folders
    for teacher in os.listdir(base_dir):
        teacher_dir = os.path.join(base_dir, teacher)
        if not os.path.isdir(teacher_dir):
            continue
        for root, dirs, files in os.walk(teacher_dir):
            for d in dirs:
                folder_path = os.path.join(root, d)
                rel_path = os.path.relpath(folder_path, base_dir).replace('\\', '/')
                meta_path = os.path.join(folder_path, '.task.json')
                meta = {}
                if os.path.exists(meta_path):
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                if meta.get('public', False):
                    public_folders.append({
                        'path': rel_path,
                        'teacher': teacher,
                        'folderName': d,
                        'meta': meta
                    })
    return public_folders

@teacher_bp.route('/teacher/activities', methods=['GET'])
def get_activities():
    """获取当前教师的所有活动文件夹列表"""
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    teacher_dir = os.path.join('templates', current_teacher)
    if not os.path.isdir(teacher_dir):
        return jsonify({'success': True, 'activities': []})

    activities = []
    for item in os.listdir(teacher_dir):
        item_path = os.path.join(teacher_dir, item)
        if os.path.isdir(item_path) and not item.startswith('.') and item not in ['data', 'uploads']:
            activities.append(item)

    return jsonify({'success': True, 'activities': activities})

@teacher_bp.route('/page-templates', methods=['GET'])
def get_page_templates():
    current = get_current_teacher()
    if not current:
        return jsonify({'success': False, 'message': '未登录'}), 401
    shared = get_shared_data()
    return jsonify({'success': True, 'pageTemplates': shared.get('pageTemplates', [])})

@teacher_bp.route('/page-templates', methods=['POST'])
def create_page_template():
    current = get_current_teacher()
    if not current:
        return jsonify({'success': False, 'message': '未登录'}), 401
    if not is_admin():
        return jsonify({'success': False, 'message': '权限不足，仅管理员可创建模板'}), 403

    data = request.json
    required = ['name', 'content']
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'缺少字段 {field}'}), 400

    template = {
        'id': str(uuid.uuid4())[:8],
        'name': data['name'],
        'description': data.get('description', ''),
        'subject': data.get('subject', ''),
        'difficulty': data.get('difficulty', '中等'),
        'category': data.get('category', 'regular'),
        'content': data['content'],
        'creator': current,
        'createdAt': datetime.now().isoformat(),
        'updatedAt': datetime.now().isoformat()
    }

    shared = get_shared_data()
    shared['pageTemplates'].append(template)
    update_shared_data(shared)
    return jsonify({'success': True, 'message': '模板创建成功', 'template': template})

@teacher_bp.route('/page-templates/<template_id>', methods=['PUT'])
def update_page_template(template_id):
    current = get_current_teacher()
    if not current:
        return jsonify({'success': False, 'message': '未登录'}), 401
    if not is_admin():
        return jsonify({'success': False, 'message': '权限不足'}), 403

    data = request.json
    shared = get_shared_data()
    for i, t in enumerate(shared['pageTemplates']):
        if t['id'] == template_id:
            t['name'] = data.get('name', t['name'])
            t['description'] = data.get('description', t['description'])
            t['subject'] = data.get('subject', t['subject'])
            t['difficulty'] = data.get('difficulty', t.get('difficulty', '中等'))
            t['category'] = data.get('category', t.get('category', 'regular'))
            t['content'] = data.get('content', t['content'])
            t['updatedAt'] = datetime.now().isoformat()
            update_shared_data(shared)
            return jsonify({'success': True, 'message': '模板更新成功', 'template': t})
    return jsonify({'success': False, 'message': '模板不存在'}), 404

@teacher_bp.route('/page-templates/<template_id>', methods=['DELETE'])
def delete_page_template(template_id):
    current = get_current_teacher()
    if not current:
        return jsonify({'success': False, 'message': '未登录'}), 401
    if not is_admin():
        return jsonify({'success': False, 'message': '权限不足'}), 403

    shared = get_shared_data()
    original_len = len(shared['pageTemplates'])
    shared['pageTemplates'] = [t for t in shared['pageTemplates'] if t['id'] != template_id]
    if len(shared['pageTemplates']) < original_len:
        update_shared_data(shared)
        return jsonify({'success': True, 'message': '模板删除成功'})
    return jsonify({'success': False, 'message': '模板不存在'}), 404

# ==================== 新增：重命名文件夹后更新内部HTML的活动ID ====================
@teacher_bp.route('/teacher/update-activity-id', methods=['POST'])
def update_activity_id_after_rename():
    """
    当文件夹重命名后，遍历该文件夹下所有 HTML 文件，替换其中的 activity_id 字段为新文件夹名。
    请求体：{ oldPath: "原相对路径", newName: "新文件夹名", teacher: "教师用户名" }
    """
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.json
    old_path = data.get('oldPath')
    new_name = data.get('newName')
    target_teacher = data.get('teacher', current_teacher)

    if not old_path or not new_name:
        return jsonify({'success': False, 'message': '缺少参数'}), 400

    if target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作其他教师目录'}), 403

    # 构造旧文件夹绝对路径
    old_full = safe_join_path(current_teacher, old_path, target_teacher=target_teacher)
    if not old_full or not os.path.isdir(old_full):
        return jsonify({'success': False, 'message': '原文件夹不存在'}), 404

    # 新文件夹的绝对路径（由前端重命名后已存在）
    parent = os.path.dirname(old_full)
    new_full = os.path.join(parent, new_name)
    if not os.path.isdir(new_full):
        return jsonify({'success': False, 'message': '新文件夹不存在，请先完成重命名'}), 400

    # 遍历新文件夹下所有 .html 文件，替换 activity_id 和可能出现的旧文件夹名字符串
    old_folder_name = os.path.basename(old_path)  # 旧文件夹名
    updated_count = 0
    for root, dirs, files in os.walk(new_full):
        for file in files:
            if file.lower().endswith('.html'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 替换常见的 activity_id 字段值（JSON 格式或 URL 中的路径）
                    new_content = content
                    # 替换 JSON 中的 activity_id
                    new_content = re.sub(
                        r'("activity_id"\s*:\s*")' + re.escape(old_folder_name) + r'(")',
                        r'\g<1>' + new_name + r'\g<2>',
                        new_content
                    )
                    # 替换 URL 路径中的文件夹名
                    new_content = re.sub(
                        r'(/templates/' + re.escape(target_teacher) + r'/)' + re.escape(old_folder_name) + r'(/)',
                        r'\g<1>' + new_name + r'\g<2>',
                        new_content
                    )
                    # 如果页面中有隐藏字段 activity_id 为 value="旧文件夹名"，也替换
                    new_content = re.sub(
                        r'(<input[^>]*name=["\']activity_id["\'][^>]*value=["\'])' + re.escape(old_folder_name) + r'(["\'][^>]*>)',
                        r'\g<1>' + new_name + r'\g<2>',
                        new_content
                    )
                    
                    if new_content != content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        updated_count += 1
                except Exception as e:
                    print(f"⚠️ 更新文件 {file_path} 失败: {e}")
                    continue

    return jsonify({'success': True, 'message': f'已更新 {updated_count} 个 HTML 文件的活动ID'})

# ==================== 新增：复制并适配HTML到其他任务 ====================
@teacher_bp.route('/teacher/copy-page-adapt', methods=['POST'])
def copy_page_adapt():
    """
    将源 HTML 文件复制到目标任务文件夹，并替换其中的 teacher 和 activity_id 字段为目标任务的值。
    请求体：{ sourcePath: "原相对路径", targetFolder: "目标任务文件夹路径", teacher: "教师用户名" }
    """
    current_teacher = get_current_teacher()
    if not current_teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.json
    source_path = data.get('sourcePath')
    target_folder = data.get('targetFolder')
    target_teacher = data.get('teacher', current_teacher)

    if not source_path or not target_folder:
        return jsonify({'success': False, 'message': '缺少参数'}), 400

    if target_teacher != current_teacher and not is_admin():
        return jsonify({'success': False, 'message': '无权操作其他教师目录'}), 403

    # 源文件绝对路径
    source_full = safe_join_path(current_teacher, source_path, target_teacher=target_teacher)
    if not source_full or not os.path.isfile(source_full):
        return jsonify({'success': False, 'message': '源文件不存在'}), 404

    # 目标文件夹绝对路径
    target_dir_full = safe_join_path(current_teacher, target_folder, target_teacher=target_teacher)
    if not target_dir_full or not os.path.isdir(target_dir_full):
        return jsonify({'success': False, 'message': '目标任务文件夹不存在'}), 404

    # 读取源文件内容
    try:
        with open(source_full, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return jsonify({'success': False, 'message': f'读取源文件失败: {e}'}), 500

    # 替换 teacher 和 activity_id
    new_activity_id = os.path.basename(target_folder)  # 取最后一级文件夹名
    new_content = re.sub(
        r'("teacher"\s*:\s*")[^"]*(")',
        r'\g<1>' + target_teacher + r'\g<2>',
        content
    )
    new_content = re.sub(
        r'("activity_id"\s*:\s*")[^"]*(")',
        r'\g<1>' + new_activity_id + r'\g<2>',
        new_content
    )
    # 替换 URL 路径中的教师名和活动名
    new_content = re.sub(
        r'(/templates/)[^/]+(/[^/]+/)',
        r'\g<1>' + target_teacher + r'/' + new_activity_id + r'/',
        new_content
    )
    # 替换隐藏字段
    new_content = re.sub(
        r'(<input[^>]*name=["\']teacher["\'][^>]*value=["\'])[^"\']*(["\'])',
        r'\g<1>' + target_teacher + r'\g<2>',
        new_content
    )
    new_content = re.sub(
        r'(<input[^>]*name=["\']activity_id["\'][^>]*value=["\'])[^"\']*(["\'])',
        r'\g<1>' + new_activity_id + r'\g<2>',
        new_content
    )

    # 生成目标文件名（保持原文件名或添加前缀避免覆盖）
    base_name = os.path.basename(source_full)
    name, ext = os.path.splitext(base_name)
    dest_file = os.path.join(target_dir_full, base_name)
    counter = 1
    while os.path.exists(dest_file):
        dest_file = os.path.join(target_dir_full, f"{name}_{counter}{ext}")
        counter += 1

    try:
        with open(dest_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
    except Exception as e:
        return jsonify({'success': False, 'message': f'写入目标文件失败: {e}'}), 500

    return jsonify({
        'success': True,
        'message': '复制并适配成功',
        'newFile': os.path.basename(dest_file)
    })
