# assignment.py - 作业管理蓝图
from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid

from data_manager import get_current_teacher, get_teacher_data, update_teacher_data

assignment_bp = Blueprint('assignment', __name__)

def get_assignments(teacher_username):
    """获取教师作业列表"""
    data = get_teacher_data(teacher_username)
    return data.get('assignments', [])

def save_assignments(teacher_username, assignments):
    """保存教师作业列表"""
    data = get_teacher_data(teacher_username)
    data['assignments'] = assignments
    update_teacher_data(teacher_username, data)

@assignment_bp.route('/assignments', methods=['GET'])
def list_assignments():
    """获取当前教师的所有作业"""
    teacher = get_current_teacher()
    if not teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401
    assignments = get_assignments(teacher)
    return jsonify({'success': True, 'assignments': assignments})

@assignment_bp.route('/assignments/<assignment_id>', methods=['GET'])
def get_assignment(assignment_id):
    """获取单个作业详情"""
    teacher = get_current_teacher()
    if not teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401
    assignments = get_assignments(teacher)
    assignment = next((a for a in assignments if a['id'] == assignment_id), None)
    if not assignment:
        return jsonify({'success': False, 'message': '作业不存在'}), 404
    return jsonify({'success': True, 'assignment': assignment})

@assignment_bp.route('/assignments', methods=['POST'])
def create_assignment():
    """创建新作业"""
    teacher = get_current_teacher()
    if not teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401
    data = request.json
    required = ['title', 'classNames']
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'缺少字段 {field}'}), 400

    assignment_id = data.get('id') or f"assignment_{uuid.uuid4().hex[:10]}"
    assignment = {
        'id': assignment_id,
        'title': data['title'],
        'description': data.get('description', ''),
        'gradingPrompt': data.get('gradingPrompt', ''),
        'aiToolsEnabled': data.get('aiToolsEnabled', False),
        'autoGradingEnabled': data.get('autoGradingEnabled', False),
        'showAnswer': data.get('showAnswer', True),
        'classNames': data['classNames'],  # 数组
        'questions': data.get('questions', []),
        'createdBy': teacher,
        'createdAt': datetime.now().isoformat(),
        'updatedAt': datetime.now().isoformat()
    }

    assignments = get_assignments(teacher)
    # 检查是否已存在（如果前端提供了 id 则覆盖，但这里是 POST 创建，一般不提供 id）
    if any(a['id'] == assignment_id for a in assignments):
        return jsonify({'success': False, 'message': '作业ID已存在'}), 400
    assignments.append(assignment)
    save_assignments(teacher, assignments)
    return jsonify({'success': True, 'message': '作业创建成功', 'assignment': assignment})

@assignment_bp.route('/assignments/<assignment_id>', methods=['PUT'])
def update_assignment(assignment_id):
    """更新作业"""
    teacher = get_current_teacher()
    if not teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401
    data = request.json
    assignments = get_assignments(teacher)
    for i, a in enumerate(assignments):
        if a['id'] == assignment_id:
            a['title'] = data.get('title', a['title'])
            a['description'] = data.get('description', a['description'])
            a['gradingPrompt'] = data.get('gradingPrompt', a['gradingPrompt'])
            a['aiToolsEnabled'] = data.get('aiToolsEnabled', a['aiToolsEnabled'])
            a['autoGradingEnabled'] = data.get('autoGradingEnabled', a['autoGradingEnabled'])
            a['showAnswer'] = data.get('showAnswer', a['showAnswer'])
            a['classNames'] = data.get('classNames', a['classNames'])
            a['questions'] = data.get('questions', a['questions'])
            a['updatedAt'] = datetime.now().isoformat()
            save_assignments(teacher, assignments)
            return jsonify({'success': True, 'message': '作业更新成功', 'assignment': a})
    return jsonify({'success': False, 'message': '作业不存在'}), 404

@assignment_bp.route('/assignments/<assignment_id>', methods=['DELETE'])
def delete_assignment(assignment_id):
    """删除作业"""
    teacher = get_current_teacher()
    if not teacher:
        return jsonify({'success': False, 'message': '未登录'}), 401
    assignments = get_assignments(teacher)
    new_assignments = [a for a in assignments if a['id'] != assignment_id]
    if len(new_assignments) == len(assignments):
        return jsonify({'success': False, 'message': '作业不存在'}), 404
    save_assignments(teacher, new_assignments)
    return jsonify({'success': True, 'message': '作业删除成功'})