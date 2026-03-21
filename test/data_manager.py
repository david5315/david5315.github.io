# data_manager.py - 统一数据管理和账号管理（完整版）
# 修改说明：
# - 使用基于可执行文件所在目录的绝对路径
# - load_accounts 在文件损坏时备份原文件并抛出异常，不再自动覆盖
# - 其他功能保持不变

import json
import os
import time
import copy
import threading
import shutil
import random
import re
import sys
from datetime import datetime

# ==================== 确定可执行文件所在目录 ====================
if getattr(sys, 'frozen', False):
    EXE_DIR = os.path.dirname(sys.executable)
else:
    EXE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==================== 数据文件路径配置（绝对路径）====================
DATA_BASE_DIR = os.path.join(EXE_DIR, 'data')
SHARED_DATA_DIR = os.path.join(DATA_BASE_DIR, 'shared')
TEACHERS_FILE = os.path.join(DATA_BASE_DIR, 'teachers.json')
ACCOUNTS_FILE = os.path.join(DATA_BASE_DIR, 'accounts.json')

# 内存中的数据缓存
teacher_data_cache = {}
shared_data_cache = None
data_modified = {}
data_lock = threading.Lock()

# 短信验证码存储
sms_codes = {}
reset_tokens = {}
current_users = {}

# ==================== 辅助函数 ====================
def get_current_teacher():
    return current_users.get('current_teacher')

def get_current_user_info():
    return current_users.get('teacher_info')

def set_current_user(username, info):
    current_users['current_teacher'] = username
    current_users['teacher_info'] = info

def is_admin():
    current_teacher = get_current_teacher()
    if not current_teacher:
        return False
    teachers_data = load_teachers()
    teacher = next((t for t in teachers_data['teachers'] if t['username'] == current_teacher), None)
    return teacher and teacher.get('role') == 'admin'

def generate_sms_code():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def generate_reset_token():
    import secrets
    return secrets.token_hex(16)

def is_valid_phone(phone):
    pattern = r'^1[3-9]\d{9}$'
    return bool(re.match(pattern, phone))

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def cleanup_expired_data():
    current_time = time.time()
    expired_phones = [p for p, info in sms_codes.items() if current_time > info['expires_at']]
    for phone in expired_phones:
        del sms_codes[phone]
    expired_tokens = [t for t, info in reset_tokens.items() if current_time > info['expires_at']]
    for token in expired_tokens:
        del reset_tokens[token]
    if expired_phones or expired_tokens:
        print(f"🧹 清理过期数据: {len(expired_phones)} 个验证码, {len(expired_tokens)} 个令牌")

def get_file_icon(file_type):
    if file_type.startswith('image/'):
        return 'fas fa-file-image'
    if file_type in ['application/pdf', 'pdf']:
        return 'fas fa-file-pdf'
    if file_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
        return 'fas fa-file-word'
    if file_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
        return 'fas fa-file-excel'
    if file_type in ['application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation']:
        return 'fas fa-file-powerpoint'
    if 'zip' in file_type or 'compressed' in file_type:
        return 'fas fa-file-archive'
    if 'text' in file_type:
        return 'fas fa-file-alt'
    if 'audio' in file_type:
        return 'fas fa-file-audio'
    if 'video' in file_type:
        return 'fas fa-file-video'
    return 'fas fa-file'

def get_file_type_text(file_type):
    if file_type.startswith('image/'):
        return '图片'
    if file_type in ['application/pdf', 'pdf']:
        return 'PDF'
    if file_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
        return 'Word文档'
    if file_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
        return 'Excel表格'
    if file_type in ['application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation']:
        return 'PowerPoint演示文稿'
    if 'zip' in file_type or 'compressed' in file_type:
        return '压缩文件'
    if 'text' in file_type:
        return '文本文件'
    if 'audio' in file_type:
        return '音频文件'
    if 'video' in file_type:
        return '视频文件'
    return '文件'

# ==================== 文件上传辅助函数 ====================
def get_assignment_file_dir(teacher_username, assignment_id, file_type, student_id=None, question_index=None):
    if file_type == "student_attachments" and student_id and question_index is not None:
        student_dir = os.path.join(
            DATA_BASE_DIR, f"teacher_{teacher_username}", "assignments", assignment_id, "student", student_id
        )
        if question_index != "0":
            student_dir = os.path.join(student_dir, f"question_{question_index}")
        os.makedirs(student_dir, exist_ok=True)
        return student_dir
    else:
        assignment_dir = os.path.join(DATA_BASE_DIR, f"teacher_{teacher_username}", "assignments", assignment_id, file_type)
        os.makedirs(assignment_dir, exist_ok=True)
        return assignment_dir

def save_assignment_file(teacher_username, assignment_id, file, file_type="attachments", student_id=None, question_index="0"):
    try:
        if file.filename == '':
            return None, '没有选择文件'
        if file_type == "student_attachments" and student_id:
            file_dir = get_assignment_file_dir(
                teacher_username, assignment_id, file_type, student_id, question_index
            )
        else:
            file_dir = get_assignment_file_dir(teacher_username, assignment_id, file_type)
        if question_index != "0":
            file_dir = os.path.join(file_dir, question_index)
        os.makedirs(file_dir, exist_ok=True)
        original_filename = file.filename
        filename = secure_filename(original_filename)
        base_name, ext = os.path.splitext(filename)
        counter = 1
        final_filename = filename
        filepath = os.path.join(file_dir, final_filename)
        while os.path.exists(filepath):
            final_filename = f"{base_name}_{counter}{ext}"
            filepath = os.path.join(file_dir, final_filename)
            counter += 1
        file.save(filepath)
        if file_type == "student_attachments" and student_id:
            if question_index != "0":
                return_path = f"/data/teacher_{teacher_username}/assignments/{assignment_id}/student/{student_id}/question_{question_index}/{final_filename}"
            else:
                return_path = f"/data/teacher_{teacher_username}/assignments/{assignment_id}/student/{student_id}/{final_filename}"
        else:
            if question_index != "0":
                return_path = f"/data/teacher_{teacher_username}/assignments/{assignment_id}/{file_type}/{question_index}/{final_filename}"
            else:
                return_path = f"/data/teacher_{teacher_username}/assignments/{assignment_id}/{file_type}/{final_filename}"
        return return_path, None
    except Exception as e:
        return None, f'文件保存失败: {str(e)}'

def cleanup_assignment_files(teacher_username, assignment_id):
    try:
        assignment_dir = os.path.join(DATA_BASE_DIR, f"teacher_{teacher_username}", "assignments", assignment_id)
        if os.path.exists(assignment_dir):
            shutil.rmtree(assignment_dir)
            print(f"🗑️ 删除作业文件目录: {assignment_dir}")
            return True
        return True
    except Exception as e:
        print(f"⚠️ 清理作业文件失败: {e}")
        return False

def secure_filename(filename):
    import re
    name, ext = os.path.splitext(filename)
    safe_name = re.sub(r'[^\w\u4e00-\u9fff.-]', '_', name)
    safe_name = safe_name[:100]
    return safe_name + ext

# ==================== 初始化函数 ====================
def ensure_directories():
    os.makedirs(DATA_BASE_DIR, exist_ok=True)
    os.makedirs(SHARED_DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(EXE_DIR, 'uploads', 'template_attachments'), exist_ok=True)
    os.makedirs(os.path.join(EXE_DIR, 'templates'), exist_ok=True)
    os.makedirs(os.path.join(EXE_DIR, 'templates', 'teach'), exist_ok=True)

def get_teacher_data_dir(teacher_username):
    return os.path.join(DATA_BASE_DIR, f"teacher_{teacher_username}")

def get_teacher_data_file(teacher_username, data_type):
    teacher_dir = get_teacher_data_dir(teacher_username)
    return os.path.join(teacher_dir, f"{data_type}.json")

def get_shared_data_file(data_type):
    return os.path.join(SHARED_DATA_DIR, f"{data_type}.json")

def get_teacher_name_by_username(teacher_username):
    accounts_data = load_accounts()
    for teacher in accounts_data['teachers']:
        if teacher['username'] == teacher_username:
            return teacher.get('name', teacher_username)
    return teacher_username

# ==================== 账号数据管理 ====================
def get_empty_accounts_data():
    return {
        "teachers": [
            {
                "username": "teach",
                "name": "教师",
                "password": "123456",
                "role": "teacher",
                "phone": "",
                "subject": "语文",
                "organization": "",
                "expiry_date": "",
                "remaining_uses": 0,
                "user_key": "",
                "user_key_expiry": ""
            }
        ],
        "students": [],
        "classes": []
    }

def get_empty_teacher_data(teacher_username):
    return {
        'assignments': [],
        'submissions': []
    }

def get_empty_shared_data():
    return {
        'promptTemplates': [
            {
                "id": "chinese_reading",
                "name": "语文阅读理解模板",
                "content": "请生成一道高中语文阅读理解题，要求：\n1. 提供一篇500-800字的现代文阅读材料\n2. 设置3-5个理解性问题\n3. 问题类型包括：主旨概括、细节理解、词句赏析、作者观点分析\n4. 提供详细的参考答案和评分标准\n5. 分值设置为15-20分",
                "type": "text",
                "subject": "语文",
                "difficulty": "中等",
                "creator": "admin",
                "createdAt": datetime.now().isoformat()
            }
        ],
        'interactiveTemplates': [
            {
                "id": "chemistry_experiment",
                "name": "化学实验模拟",
                "description": "模拟化学实验的交互式学习",
                "code": "<div class='chemistry-experiment'>化学实验模拟代码...</div>",
                "type": "chemistry",
                "creator": "admin",
                "createdAt": datetime.now().isoformat()
            }
        ],
        'assignmentTemplates': [
            {
                "id": "math_homework",
                "name": "数学作业模板",
                "description": "包含选择题、填空题和计算题的数学作业",
                "content": "请根据以下要求生成数学作业：\n1. 包含5道选择题\n2. 包含5道填空题\n3. 包含3道计算题\n4. 难度适中，适合初中学生",
                "subject": "数学",
                "difficulty": "中等",
                "questionTypes": ["choice", "fill", "text"],
                "estimatedTime": 60,
                "creator": "admin",
                "createdAt": datetime.now().isoformat(),
                "updatedAt": datetime.now().isoformat()
            }
        ],
        'pageTemplates': [  {
    "id": "regular_001",
    "name": "单选题练习",
    "subject": "通用",
    "difficulty": "简单",
    "description": "包含5道单选题，自动评分。",
    "content": "生成一个单选题练习页面，包含5道题目（内容可自定，例如数学、语文等）。每道题提供四个选项，学生点击选择答案。全部答完后点击“提交”按钮，页面会自动计算并显示得分。适合课堂快速测验。",
    "category": "regular"
  },]                  # 新增
    }

def load_accounts():
    """加载统一账号数据 - 若文件损坏则备份并抛出异常，不自动覆盖"""
    ensure_directories()
    
    if not os.path.exists(ACCOUNTS_FILE):
        default_accounts = get_empty_accounts_data()
        save_accounts(default_accounts)
        return default_accounts
    
    try:
        with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
            accounts_data = json.load(f)
            return accounts_data
    except json.JSONDecodeError as e:
        print(f"❌ CRITICAL: accounts.json 文件损坏，无法解析 JSON: {e}")
        backup_name = ACCOUNTS_FILE + '.corrupted.' + datetime.now().strftime('%Y%m%d%H%M%S')
        try:
            shutil.copy2(ACCOUNTS_FILE, backup_name)
            print(f"📁 已备份损坏文件至: {backup_name}")
        except Exception as backup_err:
            print(f"❌ 备份失败: {backup_err}")
        raise  # 抛出异常，让上层处理
    except Exception as e:
        print(f"❌ 加载账号数据失败: {e}")
        raise

def save_accounts(accounts_data):
    """保存账号数据（原子写入）"""
    try:
        temp_file = ACCOUNTS_FILE + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(accounts_data, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, ACCOUNTS_FILE)  # 原子替换
        return True
    except Exception as e:
        print(f"❌ 保存账号数据失败: {e}")
        return False

def load_teachers():
    accounts_data = load_accounts()
    return {'teachers': accounts_data['teachers']}

def save_teachers(teachers_data):
    accounts_data = load_accounts()
    accounts_data['teachers'] = teachers_data['teachers']
    return save_accounts(accounts_data)

def get_all_teachers():
    accounts_data = load_accounts()
    return accounts_data['teachers']

def get_teacher_info(username):
    accounts_data = load_accounts()
    for teacher in accounts_data['teachers']:
        if teacher['username'] == username:
            return teacher
    return None

def update_teacher_info(username, update_data):
    accounts_data = load_accounts()
    for i, teacher in enumerate(accounts_data['teachers']):
        if teacher['username'] == username:
            allowed_keys = ['name', 'phone', 'email', 'subject', 'organization',
                            'expiry_date', 'remaining_uses', 'user_key', 'user_key_expiry']
            for key in allowed_keys:
                if key in update_data:
                    accounts_data['teachers'][i][key] = update_data[key]
            accounts_data['teachers'][i]['updatedAt'] = datetime.now().isoformat()
            if save_accounts(accounts_data):
                return True, '教师信息更新成功'
            else:
                return False, '保存账号数据失败'
    return False, '教师不存在'

def get_teachers_by_subject(subject):
    accounts_data = load_accounts()
    return [t for t in accounts_data['teachers'] 
            if t.get('subject') == subject and t.get('role') == 'teacher']

def get_all_subjects():
    accounts_data = load_accounts()
    subjects = set()
    for teacher in accounts_data['teachers']:
        if teacher.get('subject'):
            subjects.add(teacher['subject'])
    return sorted(list(subjects))

def create_teacher_account(username, password, name='', phone='', role='teacher', subject='', email='',
                           organization='', expiry_date='', remaining_uses=0, user_key='', user_key_expiry=''):
    accounts_data = load_accounts()
    if any(t['username'] == username for t in accounts_data['teachers']):
        return False, '用户名已存在'
    if email and any(t.get('email') == email for t in accounts_data['teachers']):
        return False, '邮箱已被注册'
    if phone and any(t.get('phone') == phone for t in accounts_data['teachers']):
        return False, '手机号已被注册'
    new_teacher = {
        'username': username,
        'password': password,
        'name': name or username,
        'phone': phone or '',
        'email': email or '',
        'role': role,
        'subject': subject or '',
        'organization': organization,
        'expiry_date': expiry_date,
        'remaining_uses': remaining_uses,
        'user_key': user_key,
        'user_key_expiry': user_key_expiry,
        'createdAt': datetime.now().isoformat(),
        'updatedAt': datetime.now().isoformat()
    }
    accounts_data['teachers'].append(new_teacher)
    if save_accounts(accounts_data):
        teacher_dir = get_teacher_data_dir(username)
        os.makedirs(teacher_dir, exist_ok=True)
        teacher_template_dir = os.path.join(EXE_DIR, 'templates', username)
        os.makedirs(teacher_template_dir, exist_ok=True)
        teacher_data = get_empty_teacher_data(username)
        save_teacher_data_to_disk(username, teacher_data)
        return True, '教师账号创建成功'
    else:
        return False, '保存账号数据失败'

def delete_teacher(username):
    accounts_data = load_accounts()
    original_count = len(accounts_data['teachers'])
    accounts_data['teachers'] = [t for t in accounts_data['teachers'] if t['username'] != username]
    if len(accounts_data['teachers']) < original_count:
        if save_accounts(accounts_data):
            teacher_dir = get_teacher_data_dir(username)
            if os.path.exists(teacher_dir):
                shutil.rmtree(teacher_dir)
                print(f"🗑️ 删除教师数据目录: {teacher_dir}")
            return True, '教师账号删除成功'
        else:
            return False, '保存账号数据失败'
    else:
        return False, '教师账号不存在'

def find_teacher_by_user_key(user_key):
    accounts_data = load_accounts()
    for teacher in accounts_data['teachers']:
        if teacher.get('user_key') == user_key:
            return teacher
    return None

def batch_delete_students(student_ids):
    accounts_data = load_accounts()
    deleted_ids = []
    remaining_students = []
    for student in accounts_data['students']:
        if student['id'] in student_ids:
            deleted_ids.append(student['id'])
        else:
            remaining_students.append(student)
    accounts_data['students'] = remaining_students
    if save_accounts(accounts_data):
        return True, f'成功删除 {len(deleted_ids)} 名学生', deleted_ids
    else:
        return False, '保存账号数据失败', []

def get_students_by_ids(student_ids):
    accounts_data = load_accounts()
    return [s for s in accounts_data['students'] if s['id'] in student_ids]

def get_all_students():
    accounts_data = load_accounts()
    return accounts_data['students']

def add_student(student_data):
    accounts_data = load_accounts()
    if any(s['id'] == student_data['id'] for s in accounts_data['students']):
        return False, '学号已存在'
    if 'password' not in student_data:
        student_data['password'] = '123456'
    if 'class' not in student_data:
        student_data['class'] = '未分配班级'
    if 'name' not in student_data:
        student_data['name'] = f'学生{student_data["id"]}'
    accounts_data['students'].append(student_data)
    if save_accounts(accounts_data):
        return True, '学生添加成功'
    else:
        return False, '保存账号数据失败'

def update_student(student_id, student_data):
    accounts_data = load_accounts()
    for i, student in enumerate(accounts_data['students']):
        if student['id'] == student_id:
            student_data['id'] = student_id
            accounts_data['students'][i] = student_data
            if save_accounts(accounts_data):
                return True, '学生信息更新成功'
            else:
                return False, '保存账号数据失败'
    return False, '学生不存在'

def delete_student(student_id):
    accounts_data = load_accounts()
    original_count = len(accounts_data['students'])
    accounts_data['students'] = [s for s in accounts_data['students'] if s['id'] != student_id]
    if len(accounts_data['students']) < original_count:
        if save_accounts(accounts_data):
            return True, '学生删除成功'
        else:
            return False, '保存账号数据失败'
    else:
        return False, '学生不存在'

def batch_update_students(students):
    accounts_data = load_accounts()
    student_map = {s['id']: i for i, s in enumerate(accounts_data['students'])}
    added_count = 0
    updated_count = 0
    for student in students:
        if 'id' not in student:
            continue
        if 'password' not in student:
            student['password'] = '123456'
        if 'class' not in student:
            student['class'] = '未分配班级'
        if 'name' not in student:
            student['name'] = f'学生{student["id"]}'
        if student['id'] in student_map:
            accounts_data['students'][student_map[student['id']]] = student
            updated_count += 1
        else:
            accounts_data['students'].append(student)
            added_count += 1
    if save_accounts(accounts_data):
        return True, f'成功添加 {added_count} 名学生，更新 {updated_count} 名学生'
    else:
        return False, '保存账号数据失败'

def get_students_by_class(class_name):
    accounts_data = load_accounts()
    return [s for s in accounts_data['students'] if s.get('class') == class_name]

def get_students_by_teacher(teacher_username):
    accounts_data = load_accounts()
    teacher_classes = get_classes_for_teacher(teacher_username)
    class_names = [c['name'] for c in teacher_classes]
    return [s for s in accounts_data['students'] if s.get('class') in class_names]

def get_all_classes():
    accounts_data = load_accounts()
    return accounts_data['classes']

def add_class(class_data):
    accounts_data = load_accounts()
    if any(c['name'] == class_data['name'] for c in accounts_data['classes']):
        return False, '班级名称已存在'
    if 'subjectTeachers' not in class_data:
        class_data['subjectTeachers'] = []
    if isinstance(class_data['subjectTeachers'], str):
        class_data['subjectTeachers'] = [t.strip() for t in class_data['subjectTeachers'].split(',') if t.strip()]
    if 'id' in class_data:
        del class_data['id']
    if 'createdAt' in class_data:
        del class_data['createdAt']
    if 'studentCount' in class_data:
        del class_data['studentCount']
    if 'headTeacher' not in class_data:
        class_data['headTeacher'] = ''
    if class_data.get('headTeacher'):
        head_teacher_name = get_teacher_name_by_username(class_data['headTeacher'])
        class_data['headTeacher'] = head_teacher_name
    if class_data.get('subjectTeachers'):
        subject_teacher_names = []
        for teacher in class_data['subjectTeachers']:
            if teacher:
                teacher_name = get_teacher_name_by_username(teacher)
                subject_teacher_names.append(teacher_name)
        class_data['subjectTeachers'] = subject_teacher_names
    accounts_data['classes'].append(class_data)
    if save_accounts(accounts_data):
        return True, '班级创建成功'
    else:
        return False, '保存账号数据失败'

def update_class(class_name, class_data):
    accounts_data = load_accounts()
    for i, class_item in enumerate(accounts_data['classes']):
        if class_item['name'] == class_name:
            class_data['name'] = class_name
            if 'subjectTeachers' not in class_data:
                class_data['subjectTeachers'] = []
            if isinstance(class_data['subjectTeachers'], str):
                class_data['subjectTeachers'] = [t.strip() for t in class_data['subjectTeachers'].split(',') if t.strip()]
            if class_data.get('headTeacher'):
                head_teacher_name = get_teacher_name_by_username(class_data['headTeacher'])
                class_data['headTeacher'] = head_teacher_name
            if class_data.get('subjectTeachers'):
                subject_teacher_names = []
                for teacher in class_data['subjectTeachers']:
                    if teacher:
                        teacher_name = get_teacher_name_by_username(teacher)
                        subject_teacher_names.append(teacher_name)
                class_data['subjectTeachers'] = subject_teacher_names
            if 'headTeacher' not in class_data:
                class_data['headTeacher'] = class_item.get('headTeacher', '')
            accounts_data['classes'][i] = class_data
            if save_accounts(accounts_data):
                return True, '班级信息更新成功'
            else:
                return False, '保存账号数据失败'
    return False, '班级不存在'

def delete_class(class_name):
    accounts_data = load_accounts()
    original_count = len(accounts_data['classes'])
    accounts_data['classes'] = [c for c in accounts_data['classes'] if c['name'] != class_name]
    if len(accounts_data['classes']) < original_count:
        if save_accounts(accounts_data):
            return True, '班级删除成功'
        else:
            return False, '保存账号数据失败'
    else:
        return False, '班级不存在'

def get_classes_for_teacher(teacher_username):
    accounts_data = load_accounts()
    teacher_name = get_teacher_name_by_username(teacher_username)
    teacher_classes = []
    for class_item in accounts_data['classes']:
        subject_teachers = class_item.get('subjectTeachers', [])
        if isinstance(subject_teachers, str):
            subject_teachers = [t.strip() for t in subject_teachers.split(',') if t.strip()]
            class_item['subjectTeachers'] = subject_teachers
        is_head_teacher = class_item.get('headTeacher') == teacher_name
        is_subject_teacher = teacher_name in subject_teachers
        if is_head_teacher or is_subject_teacher:
            teacher_classes.append(class_item)
    return teacher_classes

def get_all_classes_with_details():
    accounts_data = load_accounts()
    classes = []
    for class_item in accounts_data['classes']:
        class_copy = class_item.copy()
        if 'headTeacher' not in class_copy:
            class_copy['headTeacher'] = '未设置'
        if 'subjectTeachers' not in class_copy:
            class_copy['subjectTeachers'] = []
        elif isinstance(class_copy['subjectTeachers'], str):
            class_copy['subjectTeachers'] = [
                t.strip() for t in class_copy['subjectTeachers'].split(',') 
                if t.strip()
            ]
        classes.append(class_copy)
    return classes

def import_class_template(teacher_username, template_name):
    templates = {
        'high_school_50': {
            'class_name': '高中班级',
            'student_count': 50,
            'prefix': '2025207'
        }
    }
    if template_name not in templates:
        return False, '模板不存在'
    template = templates[template_name]
    accounts_data = load_accounts()
    teacher_info = get_teacher_info(teacher_username)
    teacher_name = teacher_info.get('name', teacher_username) if teacher_info else teacher_username
    students = []
    for i in range(1, template['student_count'] + 1):
        student_id = f"{template['prefix']}{i:02d}"
        students.append({
            'id': student_id,
            'name': f'学生{i}',
            'class': template['class_name'],
            'password': '123456'
        })
    for student in students:
        if not any(s['id'] == student['id'] for s in accounts_data['students']):
            accounts_data['students'].append(student)
    class_exists = any(c['name'] == template['class_name'] for c in accounts_data['classes'])
    if not class_exists:
        class_data = {
            'name': template['class_name'],
            'headTeacher': teacher_name,
            'subjectTeachers': [teacher_name]
        }
        accounts_data['classes'].append(class_data)
    if save_accounts(accounts_data):
        return True, f'成功导入 {len(students)} 名学生'
    else:
        return False, '保存账号数据失败'

def load_teacher_data_to_memory(teacher_username):
    global teacher_data_cache, data_modified
    if teacher_username in teacher_data_cache:
        return teacher_data_cache[teacher_username]
    try:
        teacher_data = {}
        teacher_dir = get_teacher_data_dir(teacher_username)
        print(f"📂 加载教师数据: {teacher_username}, 目录: {teacher_dir}")
        if not os.path.exists(teacher_dir):
            os.makedirs(teacher_dir, exist_ok=True)
            teacher_data = get_empty_teacher_data(teacher_username)
            for data_type in ['assignments', 'submissions']:
                data_file = get_teacher_data_file(teacher_username, data_type)
                with open(data_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
            print(f"✅ 创建新的教师数据目录: {teacher_dir}")
        else:
            for data_type in ['assignments', 'submissions']:
                data_file = get_teacher_data_file(teacher_username, data_type)
                if os.path.exists(data_file):
                    try:
                        with open(data_file, 'r', encoding='utf-8') as f:
                            loaded_data = json.load(f)
                            if isinstance(loaded_data, list):
                                teacher_data[data_type] = loaded_data
                            else:
                                teacher_data[data_type] = []
                        print(f"✅ 加载 {data_type}: {len(teacher_data[data_type])} 条记录")
                    except json.JSONDecodeError:
                        teacher_data[data_type] = []
                    except Exception:
                        teacher_data[data_type] = []
                else:
                    teacher_data[data_type] = []
        teacher_data_cache[teacher_username] = teacher_data
        data_modified[teacher_username] = False
        print(f"✅ 成功加载教师 {teacher_username} 的数据到内存")
        return teacher_data
    except Exception as e:
        print(f"❌ 加载教师 {teacher_username} 数据失败: {e}")
        empty_data = get_empty_teacher_data(teacher_username)
        teacher_data_cache[teacher_username] = empty_data
        data_modified[teacher_username] = False
        return empty_data

def get_teacher_data(teacher_username):
    with data_lock:
        if teacher_username not in teacher_data_cache:
            teacher_data = load_teacher_data_to_memory(teacher_username)
            if teacher_data:
                teacher_data_cache[teacher_username] = teacher_data
            else:
                empty_data = get_empty_teacher_data(teacher_username)
                teacher_data_cache[teacher_username] = empty_data
        return copy.deepcopy(teacher_data_cache.get(teacher_username, get_empty_teacher_data(teacher_username)))

def update_teacher_data(teacher_username, new_data):
    global teacher_data_cache, data_modified
    with data_lock:
        teacher_data_cache[teacher_username] = new_data
        data_modified[teacher_username] = True

def save_teacher_data_to_disk(teacher_username, data):
    try:
        teacher_dir = get_teacher_data_dir(teacher_username)
        os.makedirs(teacher_dir, exist_ok=True)
        for data_type in ['assignments', 'submissions']:
            if data_type in data:
                data_file = get_teacher_data_file(teacher_username, data_type)
                with open(data_file, 'w', encoding='utf-8') as f:
                    json.dump(data[data_type], f, ensure_ascii=False, indent=2)
                print(f"✅ 保存 {data_type} 数据: {len(data[data_type])} 条记录")
        print(f"💾 教师 {teacher_username} 数据已成功保存到磁盘")
        return True
    except Exception as e:
        print(f"❌ 保存教师 {teacher_username} 数据到磁盘失败: {e}")
        return False

def manual_save_teacher(teacher_username):
    global data_modified
    with data_lock:
        if teacher_username not in teacher_data_cache:
            print(f"❌ 教师 {teacher_username} 没有数据可保存")
            return False
        current_data = copy.deepcopy(teacher_data_cache[teacher_username])
        data_modified[teacher_username] = False
    if save_teacher_data_to_disk(teacher_username, current_data):
        print(f"💾 教师 {teacher_username} 手动保存完成")
        return True
    else:
        print(f"❌ 教师 {teacher_username} 手动保存失败")
        with data_lock:
            data_modified[teacher_username] = True
        return False

def load_shared_data_to_memory():
    global shared_data_cache
    if shared_data_cache is not None:
        return shared_data_cache
    try:
        shared_data = {}
        templates_file = get_shared_data_file('prompt_templates')
        interactive_file = get_shared_data_file('interactive_templates')
        assignment_file = get_shared_data_file('assignment_templates')
        page_file = get_shared_data_file('page_templates')          # 新增此行

        # 加载 promptTemplates
        if os.path.exists(templates_file):
            with open(templates_file, 'r', encoding='utf-8') as f:
                shared_data['promptTemplates'] = json.load(f)
        else:
            shared_data['promptTemplates'] = get_empty_shared_data()['promptTemplates']
            with open(templates_file, 'w', encoding='utf-8') as f:
                json.dump(shared_data['promptTemplates'], f, ensure_ascii=False, indent=2)

        # 加载 interactiveTemplates
        if os.path.exists(interactive_file):
            with open(interactive_file, 'r', encoding='utf-8') as f:
                shared_data['interactiveTemplates'] = json.load(f)
        else:
            shared_data['interactiveTemplates'] = get_empty_shared_data()['interactiveTemplates']
            with open(interactive_file, 'w', encoding='utf-8') as f:
                json.dump(shared_data['interactiveTemplates'], f, ensure_ascii=False, indent=2)

        # 加载 assignmentTemplates
        if os.path.exists(assignment_file):
            with open(assignment_file, 'r', encoding='utf-8') as f:
                shared_data['assignmentTemplates'] = json.load(f)
        else:
            shared_data['assignmentTemplates'] = get_empty_shared_data()['assignmentTemplates']
            with open(assignment_file, 'w', encoding='utf-8') as f:
                json.dump(shared_data['assignmentTemplates'], f, ensure_ascii=False, indent=2)

        # 加载 pageTemplates
        if os.path.exists(page_file):
            with open(page_file, 'r', encoding='utf-8') as f:
                shared_data['pageTemplates'] = json.load(f)
        else:
            shared_data['pageTemplates'] = get_empty_shared_data()['pageTemplates']
            with open(page_file, 'w', encoding='utf-8') as f:        # 修正为 page_file
                json.dump(shared_data['pageTemplates'], f, ensure_ascii=False, indent=2)

        shared_data_cache = shared_data
        print(f"✅ 共享数据已加载到内存，包含 pageTemplates: {len(shared_data.get('pageTemplates', []))} 个")
        return shared_data
    except Exception as e:
        print(f"❌ 加载共享数据失败: {e}")
        shared_data_cache = get_empty_shared_data()
        return shared_data_cache
def get_shared_data():
    return load_shared_data_to_memory()

def update_shared_data(new_shared_data):
    global shared_data_cache
    shared_data_cache = new_shared_data
    save_shared_data_to_disk(new_shared_data)

def save_shared_data_to_disk(shared_data):
    try:
        templates_file = get_shared_data_file('prompt_templates')
        with open(templates_file, 'w', encoding='utf-8') as f:
            json.dump(shared_data['promptTemplates'], f, ensure_ascii=False, indent=2)
        interactive_file = get_shared_data_file('interactive_templates')
        with open(interactive_file, 'w', encoding='utf-8') as f:
            json.dump(shared_data['interactiveTemplates'], f, ensure_ascii=False, indent=2)
        assignment_file = get_shared_data_file('assignment_templates')
        with open(assignment_file, 'w', encoding='utf-8') as f:
            json.dump(shared_data['assignmentTemplates'], f, ensure_ascii=False, indent=2)
        page_file = get_shared_data_file('page_templates')          # 新增
        with open(page_file, 'w', encoding='utf-8') as f:
            json.dump(shared_data['pageTemplates'], f, ensure_ascii=False, indent=2)
        print(f"💾 共享数据已成功保存到磁盘")
        return True
    except Exception as e:
        print(f"❌ 保存共享数据到磁盘失败: {e}")
        return False
def export_teacher_data(teacher_username):
    try:
        teacher_data = get_teacher_data(teacher_username)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(DATA_BASE_DIR, f"backup_{teacher_username}_{timestamp}.json")
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(teacher_data, f, ensure_ascii=False, indent=2)
        return True, backup_file
    except Exception as e:
        return False, str(e)

def import_teacher_data(teacher_username, backup_file):
    try:
        with open(backup_file, 'r', encoding='utf-8') as f:
            imported_data = json.load(f)
        if not isinstance(imported_data, dict):
            return False, '导入的数据格式不正确'
        if 'assignments' not in imported_data:
            imported_data['assignments'] = []
        if 'submissions' not in imported_data:
            imported_data['submissions'] = []
        update_teacher_data(teacher_username, imported_data)
        manual_save_teacher(teacher_username)
        return True, '数据导入成功'
    except json.JSONDecodeError:
        return False, '备份文件格式错误'
    except Exception as e:
        return False, f'导入失败: {str(e)}'

def get_all_teachers_data():
    teachers_data = {}
    teachers_info = get_all_teachers()
    for teacher in teachers_info:
        if teacher['role'] == 'teacher':
            username = teacher['username']
            teacher_data = load_teacher_data_to_memory(username)
            teachers_data[username] = {
                'info': teacher,
                'data': teacher_data
            }
    return teachers_data

def auto_save_worker():
    global data_modified, teacher_data_cache
    while True:
        time.sleep(60)
        for teacher_username, modified in list(data_modified.items()):
            if modified and teacher_username in teacher_data_cache:
                with data_lock:
                    current_data = copy.deepcopy(teacher_data_cache[teacher_username])
                    data_modified[teacher_username] = False
                if save_teacher_data_to_disk(teacher_username, current_data):
                    print(f"🔄 教师 {teacher_username} 自动保存完成")
                else:
                    print(f"❌ 教师 {teacher_username} 自动保存失败")
                    with data_lock:
                        data_modified[teacher_username] = True

def start_auto_save():
    auto_save_thread = threading.Thread(target=auto_save_worker, daemon=True)
    auto_save_thread.start()
    print("🔄 自动保存线程已启动 (每1分钟检查一次)")
    return auto_save_thread

def sms_cleanup_worker():
    while True:
        time.sleep(300)
        cleanup_expired_data()

def start_sms_cleanup():
    sms_cleanup_thread = threading.Thread(target=sms_cleanup_worker, daemon=True)
    sms_cleanup_thread.start()
    print("🧹 短信数据清理线程已启动 (每5分钟检查一次)")
    return sms_cleanup_thread

def initialize_data():
    print("🚀 初始化数据系统...")
    ensure_directories()
    try:
        accounts_data = load_accounts()
        print(f"✅ 账号数据已加载: {len(accounts_data['teachers'])} 位教师, {len(accounts_data['students'])} 名学生, {len(accounts_data['classes'])} 个班级")
    except Exception as e:
        print(f"❌ 致命错误: 无法加载 accounts.json，程序将退出。请检查文件或修复后重试。")
        sys.exit(1)
    
    shared_data = get_shared_data()
    print(f"✅ 共享数据已加载: {len(shared_data.get('promptTemplates', []))} 个提示词模板")
    start_auto_save()
    start_sms_cleanup()
    print("✅ 数据系统初始化完成")

def get_private_students_file(teacher_username):
    return os.path.join(EXE_DIR, 'templates', teacher_username, 'student.json')

def load_private_students(teacher_username):
    file_path = get_private_students_file(teacher_username)
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ 加载私有学生失败: {e}")
        return []

def save_private_students(teacher_username, students):
    file_path = get_private_students_file(teacher_username)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(students, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ 保存私有学生失败: {e}")
        return False

def get_task_meta_path(teacher_username, task_name):
    return os.path.join(EXE_DIR, 'templates', teacher_username, task_name, '.task.json')

def load_task_meta(teacher_username, task_name):
    meta_path = get_task_meta_path(teacher_username, task_name)
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_task_meta(teacher_username, task_name, meta):
    meta_path = get_task_meta_path(teacher_username, task_name)
    task_dir = os.path.dirname(meta_path)
    if not os.path.isdir(task_dir):
        print(f"❌ 保存任务元数据失败：任务文件夹 {task_dir} 不存在")
        return False
    try:
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ 保存任务元数据失败: {e}")
        return False

def get_public_tasks():
    public_tasks = []
    base_dir = os.path.join(EXE_DIR, 'templates')
    if not os.path.exists(base_dir):
        return public_tasks
    for teacher in os.listdir(base_dir):
        teacher_dir = os.path.join(base_dir, teacher)
        if not os.path.isdir(teacher_dir):
            continue
        for task_name in os.listdir(teacher_dir):
            task_dir = os.path.join(teacher_dir, task_name)
            if not os.path.isdir(task_dir):
                continue
            meta = load_task_meta(teacher, task_name)
            if meta.get('public', False):
                public_tasks.append({
                    'teacher': teacher,
                    'taskName': task_name,
                    'url': f'/templates/{teacher}/{task_name}/index.html'
                })
    return public_tasks

def get_all_public_folders():
    public_folders = []
    base_dir = os.path.join(EXE_DIR, 'templates')
    if not os.path.exists(base_dir):
        return public_folders
    for teacher in os.listdir(base_dir):
        teacher_dir = os.path.join(base_dir, teacher)
        if not os.path.isdir(teacher_dir):
            continue
        for folder in os.listdir(teacher_dir):
            folder_path = os.path.join(teacher_dir, folder)
            if not os.path.isdir(folder_path):
                continue
            meta = load_task_meta(teacher, folder)
            if meta.get('public', False):
                public_folders.append({
                    'teacher': teacher,
                    'folderName': folder,
                    'path': f'{teacher}/{folder}',
                    'meta': meta
                })
    return public_folders

def get_student_accessible_folders(teacher_username, student_id=None):
    accessible = []
    base_dir = os.path.join(EXE_DIR, 'templates', teacher_username)
    if not os.path.isdir(base_dir):
        return accessible
    for folder in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, folder)
        if not os.path.isdir(folder_path):
            continue
        meta = load_task_meta(teacher_username, folder)
        if meta.get('allowPrivateStudents', False) or meta.get('allowGlobalStudents', False):
            accessible.append({
                'teacher': teacher_username,
                'folderName': folder,
                'path': f'{teacher_username}/{folder}',
                'meta': meta
            })
    return accessible

def check_student_folder_access(teacher_username, folder_name, student_id=None):
    meta = load_task_meta(teacher_username, folder_name)
    return meta.get('allowPrivateStudents', False) or meta.get('allowGlobalStudents', False)

def update_teacher_user_info(username, user_key, expiry, remaining_uses):
    accounts_data = load_accounts()
    for teacher in accounts_data['teachers']:
        if teacher['username'] == username:
            teacher['user_key'] = user_key
            teacher['user_key_expiry'] = expiry
            teacher['remaining_uses'] = remaining_uses
            if save_accounts(accounts_data):
                if 'teacher_info' in current_users and current_users['teacher_info'].get('username') == username:
                    current_users['teacher_info']['user_key'] = user_key
                    current_users['teacher_info']['user_key_expiry'] = expiry
                    current_users['teacher_info']['remaining_uses'] = remaining_uses
                return True, '用户密钥信息更新成功'
            else:
                return False, '保存失败'
    return False, '教师不存在'

def decrease_remaining_uses(username):
    accounts_data = load_accounts()
    for teacher in accounts_data['teachers']:
        if teacher['username'] == username:
            remaining = teacher.get('remaining_uses', 0)
            if remaining <= 0:
                return False, '剩余次数不足'
            teacher['remaining_uses'] = remaining - 1
            if save_accounts(accounts_data):
                if 'teacher_info' in current_users and current_users['teacher_info'].get('username') == username:
                    current_users['teacher_info']['remaining_uses'] = remaining - 1
                return True, f'剩余次数已更新为 {remaining-1}'
            else:
                return False, '保存失败'
    return False, '教师不存在'

def update_teacher_remaining(username, new_remaining):
    accounts_data = load_accounts()
    for teacher in accounts_data['teachers']:
        if teacher['username'] == username:
            teacher['remaining_uses'] = new_remaining
            if save_accounts(accounts_data):
                if 'teacher_info' in current_users and current_users['teacher_info'].get('username') == username:
                    current_users['teacher_info']['remaining_uses'] = new_remaining
                return True
            else:
                return False
    return False

def get_all_public_folders_recursive(base_dir='templates'):
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
                meta = load_task_meta(teacher, d)
                if meta.get('public'):
                    public_folders.append({
                        'path': rel_path,
                        'teacher': teacher,
                        'folderName': os.path.basename(folder_path),
                        'meta': meta
                    })
    return public_folders

# 注意：不再自动调用 initialize_data()，改为由 app.py 显式调用
# 这样可以确保 initialize_folders() 先执行，从打包资源恢复默认文件
# if __name__ == "__main__":
#     initialize_data()
# else:
#     initialize_data()
