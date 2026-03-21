#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QuickForge 示例网站模板测试脚本
测试 D:\测试\quickforge3.8\templates\teach\示例网站\ 目录下的所有网页
验证数据提交流程和回收功能
"""

import requests
import json
import os
from datetime import datetime

BASE_URL = "http://localhost"
TEACHER = "teach"
ACTIVITY_ID = f"example_test_{int(datetime.now().timestamp())}"
STUDENT_ID = "EXAMPLE_TEST_001"

# 需要测试的 HTML 文件
html_files = [
    ("MQTT", r"D:\测试\quickforge3.8\templates\teach\示例网站\MQTT 模式系统\MQTT.html"),
    ("MQTT 统计", r"D:\测试\quickforge3.8\templates\teach\示例网站\MQTT 模式系统\MQTT_stat.html"),
    ("云课堂数学", r"D:\测试\quickforge3.8\templates\teach\示例网站\云课堂数学\云课堂数学.html"),
    ("台球组装游戏", r"D:\测试\quickforge3.8\templates\teach\示例网站\台球组装游戏\台球组装游戏.html"),
    ("查看台球作业", r"D:\测试\quickforge3.8\templates\teach\示例网站\台球组装游戏\查看台球作业.html"),
    ("模型搭建竞赛", r"D:\测试\quickforge3.8\templates\teach\示例网站\模型搭建竞赛\模型搭建竞赛 创建.html"),
    ("模型搭建快速建", r"D:\测试\quickforge3.8\templates\teach\示例网站\模型搭建竞赛\模型搭建竞赛 创建 _quickform.html"),
    ("营销课程", r"D:\测试\quickforge3.8\templates\teach\示例网站\营销课程\meal.html"),
    ("营销统计", r"D:\测试\quickforge3.8\templates\teach\示例网站\营销课程\meal_stat.html"),
    ("通用练习模式", r"D:\测试\quickforge3.8\templates\teach\示例网站\通用练习模式\index.html"),
    ("分析页面", r"D:\测试\quickforge3.8\templates\teach\示例网站\通用练习模式\analysis.html")
]

def test_submission_template(name, filepath):
    """测试单个模板的提交功能"""
    print(f"\n[TESTING] {name}")
    
    # 检查文件是否存在
    if not os.path.exists(filepath):
        print(f"  [SKIP] 文件不存在：{filepath}")
        return None
    
    # 检查文件内容是否包含正确的 API 调用
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 检查关键元素
        has_teacher = 'teacher' in content
        has_activity_id = 'activity_id' in content or 'task' in content
        has_student_id = 'student_id' in content
        has_data_json = 'JSON.stringify' in content or '"data"' in content
        
        checks = {
            'has teacher': has_teacher,
            'has activity_id': has_activity_id,
            'has student_id': has_student_id,
            'has data JSON': has_data_json
        }
        
        all_ok = all(checks.values())
        
        print(f"  代码检查:")
        for check_name, status in checks.items():
            symbol = "[+]" if status else "[-]"
            print(f"    {symbol} {check_name}: {'✓' if status else '✗'}")
        
        if not all_ok:
            print(f"  [WARN] 代码不规范，可能存在兼容性问题")
            return False
        
        # 尝试模拟提交
        payload = {
            'teacher': TEACHER,
            'activity_id': ACTIVITY_ID,
            'student_id': STUDENT_ID,
            'data': {'template': name, 'test': True}
        }
        
        response = requests.post(
            f"{BASE_URL}/api/submit",
            json=payload,
            timeout=10
        )
        
        result = response.json()
        is_success = result.get('success', False) and response.status_code in [200, 201]
        
        if is_success:
            print(f"  [PASS] 提交成功 - HTTP {response.status_code}")
            return True
        else:
            msg = result.get('message', '')
            print(f"  [FAIL] 提交失败 - HTTP {response.status_code} | {msg[:50]}")
            return False
            
    except Exception as e:
        print(f"  [ERROR] 读取文件出错：{str(e)[:50]}")
        return False


def main():
    print("=" * 70)
    print("QuickForge 示例网站模板 - 数据中台合规性测试")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Activity ID: {ACTIVITY_ID}")
    print("=" * 70)
    
    results = []
    
    # 测试每个模板
    print("\n[PHASE 1] 测试代码规范性和提交流程...")
    for name, filepath in html_files:
        result = test_submission_template(name, filepath)
        results.append({
            'name': name,
            'path': filepath,
            'status': 'PASS' if result == True else ('FAIL' if result == False else 'SKIP'),
            'filepath_exists': os.path.exists(filepath)
        })
    
    # 统计结果
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')
    skipped = sum(1 for r in results if r['status'] == 'SKIP')
    
    print(f"\n[SUMMARY] PASS: {passed}, FAIL: {failed}, SKIP: {skipped}")
    
    # 详细列表
    print("\nDETAILED STATUS:")
    print("-" * 70)
    for i, r in enumerate(results, 1):
        status_icon = {"PASS": "[OK]", "FAIL": "[X ]", "SKIP": "[?]"}[r['status']]
        exists_icon = "✓" if r['filepath_exists'] else "✗"
        print(f"{i:2}. {status_icon} {exists_icon} {r['name']:20s} | {r['status']}")
    
    # 问题汇总
    if failed > 0:
        print(f"\n[ISSUES FOUND] 以下模板存在问题:")
        for r in results:
            if r['status'] == 'FAIL':
                print(f"   - [{r['name']}] 文件：{os.path.basename(r['path'])}")
    
    # 测试查询功能
    print("\n[PHASE 2] 测试数据查询功能...")
    try:
        params = {'teacher': TEAKER, 'activity_id': ACTIVITY_ID, 'limit': 100}
        query_response = requests.get(f"{BASE_URL}/api/submissions", params=params, timeout=10)
        
        if query_response.status_code == 200:
            qresult = query_response.json()
            if qresult.get('success'):
                records = qresult.get('submissions', [])
                count = len(records)
                print(f"[OK] 查询成功 - 找到 {count} 条记录")
                
                if isinstance(records, list) and count > 0:
                    sample = records[0]
                    keys = list(sample.keys())
                    required = ['teacher', 'activity_id', 'student_id', 'data']
                    missing = [f for f in required if f not in sample]
                    
                    if missing:
                        print(f"[WARN] 部分记录缺少字段：{missing}")
                        query_format_ok = False
                    else:
                        print(f"[OK] 数据格式完整 - 包含所有必需字段")
                        query_format_ok = True
                    
                    # 检查是否为数组格式
                    print(f"[OK] submissions 为数组类型 (符合规范)")
                else:
                    print(f"[INFO] 暂无示例网站的活动记录 (正常，首次测试)")
                    query_format_ok = None
            else:
                print(f"[FAIL] 查询返回非成功状态")
                query_format_ok = False
        else:
            print(f"[FAIL] HTTP {query_response.status_code}")
            query_format_ok = False
            
    except Exception as e:
        print(f"[ERROR] 查询异常：{e}")
        query_format_ok = False
    
    # 最终总结
    print("\n" + "=" * 70)
    print("FINAL SUMMARY REPORT")
    print("=" * 70)
    
    total = len([r for r in results if r['status'] != 'SKIP'])
    
    print(f"\n提交功能测试结果:")
    print(f"   总计测试：{total}")
    print(f"   PASS: {passed} ({passed/total*100:.1f}%)")
    print(f"   FAIL: {failed} ({failed/total*100:.1f}%)")
    
    print(f"\n数据查询功能:")
    if query_format_ok is True:
        print(f"   OK: 查询接口工作正常")
    elif query_format_ok is False:
        print(f"   FAIL: 查询接口有问题")
    else:
        print(f"   INFO: 无历史数据可查询")
    
    # 保存报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tested": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{passed/total*100:.1f}%" if total > 0 else "0%"
        },
        "query_function": {
            "available": query_format_ok is True,
            "format_correct": query_format_ok is True
        },
        "issues": [r for r in results if r['status'] == 'FAIL'],
        "all_templates": results
    }
    
    output_file = "example_site_compliance_report.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n完整报告已保存至：{output_file}")
    print("=" * 70)

if __name__ == "__main__":
    main()
