#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复示例网站下的 HTML 模板，使其符合数据中台规范
添加缺失的 teacher、activity_id 和 data JSON 字段
"""

import os, re, json

base_dir = r"D:\测试\quickforge3.8\templates\teach\示例网站"

# 需要修复的模板列表（基于测试结果）
templates_to_fix = [
    "MQTT 模式系统/MQTT.html",
    "MQTT 模式系统/MQTT_stat.html", 
    "云课堂数学/云课堂数学.html",
    "台球组装游戏/台球组装游戏.html",
    "台球组装游戏/查看台球作业.html",
    "模型搭建竞赛/模型搭建竞赛 创建.html",
    "模型搭建竞赛/模型搭建竞赛 创建 _quickform.html",
    "营销课程/meal.html",
    "营销课程/meal_stat.html",
    "通用练习模式/analysis.html",
    "通用练习模式/index.html"
]

def fix_html_file(filepath, template_name):
    """修复单个 HTML 文件"""
    print(f"\n[FIXING] {template_name}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 检查是否需要修复
        needs_teacher = '<input type="hidden" id="teacher"' not in content
        needs_data_json = '"data":' not in content and "'data':" not in content
        
        if not needs_teacher and not needs_data_json:
            print(f"  [SKIP] 已符合规范")
            return True
        
        # 添加 teacher 和 activity_id 隐藏字段
        if needs_teacher:
            # 在 form 标签后或 head 结束后添加
            insert_code = '''
            <!-- Added by QuickForge Fix Script -->
            <input type="hidden" id="teacher" value="{{teacher}}" />
            <input type="hidden" id="activityId" value="{{task}}" />
            <input type="hidden" id="studentId" name="student_id" value="" />
            <!-- End Added Code -->'''
            
            # 尝试插入到 form 标签附近
            if '<form' in content:
                content = content.replace('<form', '''<form
                onsubmit="setStudentId(event);""' + '\n' + insert_code)
            elif '</head>' in content:
                content = content.replace('</head>', '</head>\n' + insert_code)
            else:
                print(f"  [WARN] 找不到合适位置插入字段")
        
        # 修复 submit 函数使用 data JSON 格式
        if needs_data_json:
            # 查找现有的 submitFormData 或类似函数
            patterns_to_replace = [
                # 替换 submit function body
                (r'(var\s+formData\s*=\s*new\s+FormData\(\))([\s\S]*?)(\.(append\(|\.get\()\);)',
                 lambda m: m.group(1) + m.group(2) + '''
                    // Fix: Wrap additional fields in data object
                    formData.append('data', JSON.stringify({
                        raw_fields: {},  // Will be replaced
                        client_timestamp: new Date().toISOString(),
                        submission_type: '{{template}}'
                    }));''' + m.group(3)),
                
                # 添加 setStudentId 函数
                (r'(function\s+\w+\(e?\)\s*\{[\s\S]*?)if\s+\(e\.preventDefault\(\)\)',
                 lambda m: m.group(1) + '''
                    function setStudentId(e) {
                        const studentIdInput = document.getElementById('studentId');
                        if(studentIdInput && window.studentId) {
                            studentIdInput.value = window.studentId;
                        }
                        e.preventDefault();
                    }
                    
                    ''' + m.group(2))
            ]
            
            for pattern, replacement in patterns_to_replace:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
        
        # 如果内容有变化，保存文件
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  [OK] File updated successfully")
            return True
        else:
            print(f"  [SKIP] No changes needed or couldn't modify")
            return False
            
    except Exception as e:
        print(f"  [ERROR] Failed to process: {str(e)[:50]}")
        return False


def main():
    print("=" * 60)
    print("QuickForge - 修复示例网站模板")
    print(f"Base Directory: {base_dir}")
    print("=" * 60)
    
    if not os.path.exists(base_dir):
        print(f"[ERROR] Base directory not found: {base_dir}")
        exit(1)
    
    fixed_count = 0
    skipped_count = 0
    error_count = 0
    
    for rel_path in templates_to_fix:
        full_path = os.path.join(base_dir, rel_path)
        
        if os.path.exists(full_path):
            if fix_html_file(full_path, rel_path):
                fixed_count += 1
            else:
                skipped_count += 1
        else:
            print(f"\n[ERROR] File not found: {rel_path}")
            error_count += 1
    
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  Fixed: {fixed_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors: {error_count}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
