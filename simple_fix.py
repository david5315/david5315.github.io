import os, re

base_dir = r"D:\测试\quickforge3.8\templates\teach\示例网站"

print("=" * 60)
print("QuickForge - Fix Example Templates")
print("=" * 60)

# Scan all HTML files
html_files = []
for root, dirs, files in os.walk(base_dir):
    for f in files:
        if f.endswith('.html'):
            full_path = os.path.join(root, f)
            rel_name = f.replace('\\', '/')
            html_files.append((rel_name, full_path))

print(f"\nFound {len(html_files)} HTML files\n")

fixed_count = 0
skipped_count = 0

# Common fix template - add hidden fields after form tag
insert_code = """
            <!-- QUICKFORGE FIX -->
            <input type="hidden" id="qf_teacher" value="{{teacher}}">
            <input type="hidden" id="qf_activity_id" value="{{task}}">
            <input type="hidden" id="qf_student_id" name="student_id" value="">
            <!-- END FIX -->"""

for name, filepath in html_files:
    print(f"[PROCESSING] {name}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # Check if needs fixing
        has_teacher_hidden = '<input.*id="teacher"' in content.lower()
        has_data_json = '"data"' in content or "'data'" in content
        
        # Add teacher/activity/student hidden fields if missing
        if not has_teacher_hidden:
            # Try to insert after <form
            if '<form' in content:
                insert_pos = content.find('<form')
                # Find end of form tag line
                end_form = content.find('>', insert_pos)
                if end_form > 0:
                    content = content[:end_form+1] + '\n' + insert_code + content[end_form+1:]
                    print(f"  [OK] Added hidden fields")
            
            # Or insert after </head>
            elif '</head>' in content:
                content = content.replace('</head>', '</head>\n' + insert_code)
                print(f"  [OK] Added after head")
        
        # If still no data JSON field, add to submit function
        if not has_data_json:
            # Look for fetch or XMLHttpRequest calls and wrap data
            # Simple approach: add data object wrapper before form submission
            
            # Pattern to find submit handlers
            patterns = [
                r'(submit\(event|onclick=")([\s\S]*?)(onsubmit|</script>)',
            ]
            
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    print(f"  [OK] Found submit handler, would add data wrapper")
                    break
            else:
                print(f"  [INFO] No complex submit logic found")
        
        # Save if changed
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed_count += 1
        else:
            skipped_count += 1
            
    except Exception as e:
        print(f"  [ERROR] {str(e)[:40]}")

print(f"\n{'='*60}")
print(f"Completed: Fixed={fixed_count}, Skipped={skipped_count}")
print(f"Files updated in: {base_dir}")
print(f"{'='*60}")
