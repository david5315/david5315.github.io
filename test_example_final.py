import os, requests, json
from datetime import datetime

print("=" * 60)
print("QuickForge 示例网站 - 模板数据提交功能测试")
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

BASE_URL = "http://localhost"
TEACHER = "teach"
ACTIVITY_ID = f"example_{int(datetime.now().timestamp())}"
STUDENT_ID = "EXAMPLE_TEST_001"

# 扫描示例网站目录下的所有 HTML 文件
html_files = []
base_dir = r"D:\测试\quickforge3.8\templates\teach\示例网站"

if not os.path.exists(base_dir):
    print(f"[ERROR] 目录不存在：{base_dir}")
    exit(1)

for root, dirs, files in os.walk(base_dir):
    for f in files:
        if f.endswith('.html'):
            full_path = os.path.join(root, f)
            rel_name = os.path.relpath(root, base_dir).replace('\\', '/')
            template_name = f"{rel_name}/{f}" if rel_name != '.' else f
            html_files.append((template_name, full_path))

print(f"\n[INFO] 找到 {len(html_files)} 个 HTML 文件\n")

results = []

# 测试每个文件
for name, filepath in html_files:
    print(f"[TEST] {name}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键元素
        has_teacher = 'teacher' in content.lower()
        has_activity_id = 'activity_id' in content.lower() or 'task' in content.lower()
        has_student_id = 'student_id' in content.lower()
        has_data_field = '"data"' in content or "'data'" in content
        
        status_checks = {
            'Teacher field': has_teacher,
            'Activity ID field': has_activity_id,
            'Student ID field': has_student_id,
            'Data JSON field': has_data_field
        }
        
        all_good = all(status_checks.values())
        
        if not all_good:
            print(f"  [WARN] 代码不规范:")
            for key, val in status_checks.items():
                icon = "+" if val else "-"
                print(f"    [{icon}] {key}: {'OK' if val else 'MISSING'}")
            
            # 尝试模拟提交 anyway
            payload = {
                'teacher': TEACHER,
                'activity_id': ACTIVITY_ID,
                'student_id': STUDENT_ID,
                'data': {'template': name.replace('/', '_')}
            }
            
            try:
                resp = requests.post(f"{BASE_URL}/api/submit", json=payload, timeout=5)
                result_json = resp.json()
                
                if resp.status_code in [200, 201] and result_json.get('success'):
                    print(f"  [PASS] API 调用成功 (HTTP {resp.status_code})")
                    results.append({'name': name, 'status': 'PASS', 'issues': list(k for k,v in status_checks.items() if not v)})
                else:
                    msg = result_json.get('message', '')
                    print(f"  [FAIL] API 调用失败 (HTTP {resp.status_code}): {msg[:40]}")
                    results.append({'name': name, 'status': 'FAIL', 'issues': list(status_checks.keys())})
            except Exception as e:
                print(f"  [FAIL] 网络错误：{str(e)[:40]}")
                results.append({'name': name, 'status': 'ERROR', 'issues': ['network']})
        else:
            print(f"  [OK] 代码规范")
            
            # 模拟提交测试
            payload = {
                'teacher': TEACHER,
                'activity_id': ACTIVITY_ID,
                'student_id': STUDENT_ID,
                'data': {'template': name.replace('/', '_'), 'test': True}
            }
            
            try:
                resp = requests.post(f"{BASE_URL}/api/submit", json=payload, timeout=5)
                result_json = resp.json()
                
                if resp.status_code in [200, 201] and result_json.get('success'):
                    print(f"  [PASS] 提交成功 (HTTP {resp.status_code})")
                    results.append({'name': name, 'status': 'PASS', 'issues': []})
                else:
                    msg = result_json.get('message', 'Unknown error')
                    print(f"  [FAIL] 提交失败：{msg[:50]}")
                    results.append({'name': name, 'status': 'FAIL', 'issues': ['api_submit']})
            except Exception as e:
                print(f"  [ERROR] 请求异常：{str(e)[:40]}")
                results.append({'name': name, 'status': 'ERROR', 'issues': [str(e)]})
    
    except Exception as e:
        print(f"  [ERROR] 读取文件失败：{str(e)[:40]}")
        results.append({'name': name, 'status': 'ERROR', 'issues': ['file_read']})

# 统计结果
passed = sum(1 for r in results if r['status'] == 'PASS')
failed = sum(1 for r in results if r['status'] == 'FAIL')
errors = sum(1 for r in results if r['status'] == 'ERROR')

print(f"\n{'='*60}")
print("测试结果汇总")
print(f"{'='*60}")
print(f"总计：{len(results)} 个模板")
print(f"PASS: {passed} ({passed/len(results)*100:.1f}%)")
print(f"FAIL: {failed} ({failed/len(results)*100:.1f}%)")
print(f"ERROR: {errors} ({errors/len(results)*100:.1f}%)")

# 测试查询功能
print(f"\n{'='*60}")
print("查询功能测试")
print(f"{'='*60}")

try:
    params = {'teacher': TEACHER, 'activity_id': ACTIVITY_ID, 'limit': 100}
    qresp = requests.get(f"{BASE_URL}/api/submissions", params=params, timeout=5)
    
    if qresp.status_code == 200:
        qresult = qresp.json()
        if qresult.get('success'):
            records = qresult.get('submissions', [])
            count = len(records)
            print(f"[OK] 查询成功 - 找到 {count} 条记录")
            
            if isinstance(records, list) and count > 0:
                sample = records[0]
                keys = list(sample.keys())
                required = ['teacher', 'activity_id', 'student_id', 'data']
                missing = [k for k in required if k not in sample]
                
                if missing:
                    print(f"[WARN] 部分记录缺少字段：{missing}")
                else:
                    print(f"[OK] 数据完整")
        else:
            print(f"[INFO] 暂无数据")
    else:
        print(f"[FAIL] HTTP {qresp.status_code}")
except Exception as e:
    print(f"[ERROR] 查询异常：{e}")

print(f"\n{'='*60}")
print("详细列表:")
print(f"{'-'*60}")
for i, r in enumerate(results, 1):
    status_map = {'PASS': '[+]', 'FAIL': '[-]', 'ERROR': '[?]'}
    print(f"{i:2}. {status_map[r['status']]} {r['name'].split('/')[-1]:30s} | {r['status']}")

# 保存报告
report = {
    "timestamp": datetime.now().isoformat(),
    "summary": {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "error": errors,
        "pass_rate": f"{passed/len(results)*100:.1f}%"
    },
    "results": results
}

with open('example_site_test_result.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"\n报告已保存至：example_site_test_result.json")
