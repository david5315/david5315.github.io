#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QuickForge 模板数据中台 API 测试脚本
测试日期：2026-03-19
测试目标：验证所有 16 个模板的提交和查询功能
"""

import requests
import json
from datetime import datetime
import time

# ==================== 配置 ====================
BASE_URL = "http://localhost"
TEACHER = "teach"
ACTIVITY_ID = "test_activity_" + str(int(time.time()))
TEST_STUDENT_ID = f"TEST_STU_{int(time.time())}"

TEMPLATES = {
    "regular_001": {"name": "单选题练习", "data_sample": {"answers": [1], "score": 1, "total": 1}},
    "regular_002": {"name": "多选题练习", "data_sample": {"answers": [[0, 1]], "score": 1, "total": 1}},
    "regular_003": {"name": "不定项选择", "data_sample": {"answers": [[0, 2]], "score": 1, "total": 1}},
    "regular_004": {"name": "判断题", "data_sample": {"answers": [True], "score": 1, "total": 1}},
    "regular_005": {"name": "填空题", "data_sample": {"answers": ["北京"], "score": 1, "total": 1}},
    "regular_006": {"name": "问答题", "data_sample": {"answers": ["测试回答"], "score": 5, "total": 5}},
    "regular_007": {"name": "编程练习", "data_sample": {"code": "print('hello')"}},
    "interactive_001": {"name": "运动项目连线", "data_sample": {"matches": [{"gushi": "床前明月光", "author": "李白"}]}},
    "interactive_004": {"name": "物品分类", "data_sample": {"placements": {"fruit": [1, 2, 3]}}},
    "interactive_006": {"name": "电路组装", "data_sample": {"elements": [{"type": "battery"}]}},
    "interactive_009": {"name": "思维导图", "data_sample": {"nodes": [{"text": "中心", "x": 100, "y": 100}]}},
    "interactive_013": {"name": "成语填空", "data_sample": {"answers": {"0": "马"}}},
    "data_013": {"name": "课堂签到", "data_sample": {"name": "张三", "class": "高一 (1) 班", "time": datetime.now().isoformat()}},
    "data_016": {"name": "成绩查询", "data_sample": {}},
    "data_020": {"name": "反馈调查", "data_sample": {"clarity_score": 5, "difficulty": "appropriate"}},
    "data_034": {"name": "绘画白板", "data_sample": {"image_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="}}
}

def test_submission(tid, tinfo):
    print(f"\n[TEST] {tid}: {tinfo['name']}")
    try:
        formData = {
            'teacher': TEACHER,
            'activity_id': ACTIVITY_ID,
            'student_id': TEST_STUDENT_ID,
            'data': json.dumps(tinfo['data_sample'])
        }
        response = requests.post(f"{BASE_URL}/api/submit", data=formData, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print(f"  OK: Success - {result.get('message', 'OK')}")
                return True
            else:
                print(f"  FAIL: {result.get('message', result.get('error'))}")
                return False
        else:
            print(f"  FAIL: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"  ERROR: {str(e)}")
        return False

def test_query():
    try:
        params = {'teacher': TEACHER, 'activity_id': ACTIVITY_ID, 'limit': 100}
        response = requests.get(f"{BASE_URL}/api/submissions", params=params, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                submissions = result.get('submissions', [])
                count = len(submissions)
                if count > 0:
                    print(f"  OK: Found {count} records")
                    if isinstance(submissions, list):
                        print(f"  OK: submissions is array type")
                        return True
                    else:
                        print(f"  WARNING: submissions not an array!")
                        return False
                else:
                    print(f"  NO DATA: No records yet")
                    return None
            else:
                print(f"  FAIL: {result.get('message')}")
                return False
        else:
            print(f"  FAIL: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"  ERROR: {str(e)}")
        return False

def main():
    print("=" * 70)
    print("TESTING: QuickForge Data Middleware API Compliance")
    print(f"TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"TEACHER: {TEACHER}")
    print(f"ACTIVITY: {ACTIVITY_ID}")
    print("=" * 70)
    
    results = {'submitted': [], 'failed': []}
    
    print("\n[PHASE 1] Testing submission...")
    for tid, tinfo in TEMPLATES.items():
        if test_submission(tid, tinfo):
            results['submitted'].append(tid)
        else:
            results['failed'].append(tid)
        time.sleep(0.3)
    
    print("\n[PHASE 2] Testing retrieval...")
    print(f"Query activity '{ACTIVITY_ID}':")
    query_result = test_query()
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    total = len(TEMPLATES)
    ok_count = len(results['submitted'])
    fail_count = len(results['failed'])
    
    print(f"\nSUBMISSION RESULTS:")
    print(f"   Total: {total}")
    print(f"   OK: {ok_count} ({ok_count/total*100:.1f}%)")
    print(f"   FAIL: {fail_count}")
    
    if results['failed']:
        print(f"\nFAILED:")
        for tid in results['failed']:
            print(f"   - {tid}: {TEMPLATES[tid]['name']}")
    
    print(f"\nQUERY FUNCTION:")
    if query_result is True:
        print("   OK: Query works")
    elif query_result is False:
        print("   FAIL: Query failed")
    else:
        print("   NO DATA: Interface available")
    
    print("\nDETAILED STATUS:")
    print("-" * 70)
    for i, (tid, info) in enumerate(TEMPLATES.items(), 1):
        symbol = "[+]" if tid in results['submitted'] else "[-]"
        status = "OK" if tid in results['submitted'] else "FAIL"
        print(f"{i:2}. {symbol} {tid:<20s} | {status} - {info['name']}")
    
    print("\n" + "=" * 70)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {"total": total, "ok": ok_count, "failed": fail_count},
        "results": {"submitted": results['submitted'], "failed": results['failed'], "query_ok": query_result is True}
    }
    
    with open('api_test_results_v2.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\nREPORT SAVED TO: api_test_results_v2.json")

if __name__ == "__main__":
    main()
