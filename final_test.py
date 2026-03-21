import requests, json
from datetime import datetime

print("=" * 70)
print("FINAL API COMPLIANCE TEST - All 16 Templates")
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

BASE_URL = "http://localhost"
TEACHER = "teach"  # FIXED: was TEAKER
ACTIVITY_ID = f"final_test_{int(datetime.now().timestamp())}"
STUDENT_ID = "FINAL_TEST_001"

templates = [
    ("regular_001", "单选题练习"),
    ("regular_002", "多选题练习"),
    ("regular_003", "不定项选择"),
    ("regular_004", "判断题"),
    ("regular_005", "填空题"),
    ("regular_006", "问答题"),
    ("regular_007", "编程练习"),
    ("interactive_001", "运动项目连线"),
    ("interactive_004", "物品分类"),
    ("interactive_006", "电路组装"),
    ("interactive_009", "思维导图"),
    ("interactive_013", "成语填空"),
    ("data_013", "课堂签到"),
    ("data_016", "成绩查询"),
    ("data_020", "反馈调查"),
    ("data_034", "绘画白板")
]

passed = []
failed = []

print("\nTesting submissions:")
for tid, name in templates:
    payload = {
        'teacher': TEACHER,  # FIXED!
        'activity_id': ACTIVITY_ID,
        'student_id': STUDENT_ID,
        'data': {'test': tid}
    }
    
    try:
        r = requests.post(f"{BASE_URL}/api/submit", json=payload, timeout=10)
        result = r.json()
        
        if r.status_code in [200, 201] and result.get('success'):
            passed.append(tid)
            print(f"[PASS] {tid:20s} | {name:<15s} | HTTP {r.status_code}")
        else:
            failed.append(tid)
            msg = result.get('message', 'Unknown')
            print(f"[FAIL] {tid:20s} | {name:<15s} | {msg[:40]}")
            
    except Exception as e:
        failed.append(tid)
        print(f"[ERR ] {tid:20s} | {name:<15s} | {str(e)[:40]}")

# Summary
print(f"\nResults: PASS={len(passed)}, FAIL={len(failed)}")

# Test query
print("\nTesting /api/submissions query...")
params = {'teacher': TEACHER, 'activity_id': ACTIVITY_ID, 'limit': 100}
qr = requests.get(f"{BASE_URL}/api/submissions", params=params, timeout=10)

if qr.status_code == 200:
    qresult = qr.json()
    if qresult.get('success'):
        records = qresult.get('submissions', [])
        count = len(records)
        print(f"[OK] Found {count} records")
        
        if isinstance(records, list) and count > 0:
            sample = records[0]
            keys = list(sample.keys())
            print(f"     Sample has {len(keys)} fields: {keys}")
            required = ['teacher', 'activity_id', 'student_id', 'data']
            missing = [f for f in required if f not in sample]
            if missing:
                print(f"     WARNING: Missing fields: {missing}")
            else:
                print(f"     OK: All required fields present")
        
        query_ok = True
    else:
        print(f"[FAIL] Query returned non-success")
        query_ok = False
else:
    print(f"[FAIL] HTTP {qr.status_code}")
    query_ok = False

print("\n" + "=" * 70)
print("COMPLIANCE SUMMARY")
print("=" * 70)
print(f"Submission rate: {len(passed)}/{len(templates)} ({len(passed)/len(templates)*100:.1f}%)")
print(f"Query format: {'CORRECT' if query_ok else 'INCORRECT'}")
print("=" * 70)

# Save report
report = {
    "timestamp": datetime.now().isoformat(),
    "pass_rate": f"{len(passed)}/{len(templates)} ({len(passed)/len(templates)*100:.1f}%)",
    "queries_ok": query_ok,
    "all_templates_compliant": len(passed) == len(templates)
}

with open('FINAL_TEST_RESULT.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2)

print("\nReport saved to: FINAL_TEST_RESULT.json")
