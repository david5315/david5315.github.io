import os
import json

templates = [
    "regular_001_single_choice",
    "regular_002_multi_choice", 
    "regular_003_partial_choice",
    "regular_004_true_false",
    "regular_005_fill_blank",
    "regular_006_short_answer",
    "regular_007_programming",
    "interactive_sport_001_match",
    "interactive_special_004_category",
    "interactive_special_006_circuit",
    "interactive_special_009_mindmap",
    "interactive_special_013_chengyu",
    "data_13_attendance",
    "data_16_qwen_plus",
    "data_20_feedback_survey",
    "data_34_whiteboard"
]

type_map = {
    t: t.split('_')[1].lower() if '_' in t else 'other' for t in templates
}

base_dir = "C:/Users/Administrator/.openclaw/workspace/templates"

for name in templates:
    template_type = type_map[name]
    
    config = {
        "public": True,
        "allowOtherTeachers": False,
        "allowPrivateStudents": True,
        "allowGlobalStudents": False,
        "templateType": template_type,
        "templateId": name
    }
    
    filepath = os.path.join(base_dir, f"{name}.task.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"[OK] Created: {name}.task.json")

print(f"\n[Done] All {len(templates)} .task.json files created!")
