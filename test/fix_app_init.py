# Fix initialize_system in app.py
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_code = '''def initialize_system():
    print("🔧 初始化系统数据...")
    ensure_directories()
    try:
        teachers_data = load_teachers()
        shared_data = load_shared_data_to_memory()
        print("✅ 系统数据初始化成功")'''

new_code = '''def initialize_system():
    print("🔧 初始化系统数据...")
    ensure_directories()
    try:
        teachers_data = load_teachers()
        # 显式加载共享数据（在 initialize_folders() 之后调用，确保打包的资源已复制）
        from data_manager import initialize_data
        initialize_data()
        print("✅ 系统数据初始化成功")'''

content = content.replace(old_code, new_code)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('OK: initialize_system fixed')
