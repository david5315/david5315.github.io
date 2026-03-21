import os
import shutil
from pathlib import Path

# 配置路径
source_dir = r"C:\Users\Administrator\.openclaw\workspace\templates"
target_base = r"D:\测试\quickforge3.8\templates\teach"

# 定义要复制的文件列表
file_list = [
    "regular_001_single_choice.html",
    "regular_002_multi_choice.html",
    "regular_003_partial_choice.html",
    "regular_004_true_false.html",
    "regular_005_fill_blank.html",
    "regular_006_short_answer.html",
    "regular_007_programming.html",
    "interactive_sport_001_match.html",
    "interactive_special_004_category.html",
    "interactive_special_006_circuit.html",
    "interactive_special_009_mindmap.html",
    "interactive_special_013_chengyu.html",
    "data_13_attendance.html",
    "data_16_qwen_plus.html",
    "data_20_feedback_survey.html",
    "data_34_whiteboard.html",
    "deepseek_data34_whiteboard_v2.html",
]

task_file_list = [
    "regular_001_single_choice.task.json",
    "regular_002_multi_choice.task.json",
    "regular_003_partial_choice.task.json",
    "regular_004_true_false.task.json",
    "regular_005_fill_blank.task.json",
    "regular_006_short_answer.task.json",
    "regular_007_programming.task.json",
    "interactive_sport_001_match.task.json",
    "interactive_special_004_category.task.json",
    "interactive_special_006_circuit.task.json",
    "interactive_special_009_mindmap.task.json",
    "interactive_special_013_chengyu.task.json",
    "data_13_attendance.task.json",
    "data_16_qwen_plus.task.json",
    "data_20_feedback_survey.task.json",
    "data_34_whiteboard.task.json",
]

print("=" * 60)
print("QuickForge Templates Deployment")
print(f"Source: {source_dir}")
print(f"Target: {target_base}")
print("=" * 60)

# 创建目标目录
os.makedirs(target_base, exist_ok=True)

copied = 0
failed = 0

# 复制 HTML 文件
print("\n[Copying HTML files]")
for filename in file_list:
    source_path = os.path.join(source_dir, filename)
    dest_path = os.path.join(target_base, filename)
    
    if os.path.exists(source_path):
        shutil.copy2(source_path, dest_path)
        size_kb = round(os.path.getsize(source_path) / 1024, 2)
        print(f"[OK] {filename} ({size_kb} KB)")
        copied += 1
    else:
        print(f"[X ] {filename} - Not found")
        failed += 1

# 复制 task.json 文件
print("\n[Copying configuration files]")
for filename in task_file_list:
    source_path = os.path.join(source_dir, filename)
    dest_path = os.path.join(target_base, filename)
    
    if os.path.exists(source_path):
        shutil.copy2(source_path, dest_path)
        print(f"[OK] {filename}")
        copied += 1
    else:
        print(f"[X ] {filename} - Not found")
        failed += 1

print("\n" + "=" * 60)
print(f"Deployment completed!")
print(f"Success: {copied}, Failed: {failed}")
print(f"Target: {target_base}")
print("=" * 60)

if failed == 0:
    print("\n[SUCCESS] All files deployed successfully!")
    print("[INFO] You can now browse these HTML files in your browser.")
else:
    print(f"\n[WARNING] {failed} file(s) failed to deploy.")
