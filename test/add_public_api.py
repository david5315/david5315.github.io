# Add public folder-content API to teacher_apis.py

api_code = '''

# ==================== 公开目录浏览 API ====================
@teacher_bp.route('/public/folder-content', methods=['GET'])
def public_folder_content():
    """公开目录内容浏览（无需登录）"""
    path = request.args.get('path', '')
    
    # 基础目录为 templates
    base_dir = os.path.join(EXE_DIR, 'templates')
    
    # 拼接目标路径
    if path:
        # 防止路径遍历
        target_dir = os.path.realpath(os.path.join(base_dir, path))
        if not target_dir.startswith(os.path.realpath(base_dir)):
            return jsonify({'success': False, 'message': '无权访问该路径'}), 403
    else:
        target_dir = base_dir
    
    if not os.path.exists(target_dir):
        return jsonify({'success': False, 'message': '目录不存在'}), 404
    
    items = []
    try:
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            if item.startswith('.'):
                continue
            
            # 检查是否是公开目录
            if os.path.isdir(item_path):
                meta_path = os.path.join(item_path, '.task.json')
                is_public = False
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                            is_public = meta.get('public', False)
                    except:
                        pass
                
                if is_public or item in ['teach']:  # teach 目录默认公开
                    items.append({
                        'name': item,
                        'type': 'dir',
                        'size': 0,
                        'modified': datetime.fromtimestamp(os.path.getmtime(item_path)).isoformat()
                    })
            else:
                # 文件直接显示
                stat = os.stat(item_path)
                items.append({
                    'name': item,
                    'type': 'file',
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        # 按类型和名称排序：目录在前，文件在后
        items.sort(key=lambda x: (x['type'] != 'dir', x['name'].lower()))
        
        return jsonify({
            'success': True,
            'path': path,
            'items': items
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

'''

# 读取文件
with open('teacher_apis.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 添加到末尾
content = content.rstrip() + api_code

# 写入
with open('teacher_apis.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('OK: API added')
