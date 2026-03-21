# test_ai_models.py - 测试所有 AI 模型

import requests
import json
import ssl
from urllib3 import poolmanager

# 创建忽略证书验证的适配器
class TLSAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.poolmanager = poolmanager.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_version=ssl.PROTOCOL_TLS,
            ssl_context=ctx)

# 配置
API_KEY = "sk-676611e12c9549c08125cd1c0d3733b9"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 要测试的模型列表
MODELS = [
    "kimi-k2.5",
    "glm-5",
    "qwen3.5-plus",
    "qwen3-max-2026-01-23",
    "qwen3.5-flash"
]

# 测试提示词
TEST_PROMPT = "请用一句话介绍你自己"

print("="*60)
print("AI 模型测试")
print("="*60)
print(f"API 地址：{BASE_URL}")
print(f"API 密钥：{API_KEY[:20]}...")
print(f"测试模型数：{len(MODELS)}")
print("="*60)
print()

# 创建会话
session = requests.Session()
session.mount('https://', TLSAdapter())

# 逐个测试模型
results = []
for model in MODELS:
    print(f"\n[TEST] Model: {model}")
    print("-" * 60)
    
    try:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是一个有帮助的助手"},
                {"role": "user", "content": TEST_PROMPT}
            ],
            "max_tokens": 200,
            "temperature": 0.7
        }
        
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        full_url = f"{BASE_URL}/chat/completions"
        response = session.post(full_url, headers=headers, json=payload, timeout=60)
        
        print(f"HTTP 状态码：{response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                content = data['choices'][0]['message']['content']
                print(f"[OK] Success! Response: {content[:100]}...")
                
                # 统计 token 使用
                if 'usage' in data:
                    usage = data['usage']
                    print(f"[Token] Total={usage.get('total_tokens', 0)}, Prompt={usage.get('prompt_tokens', 0)}, Completion={usage.get('completion_tokens', 0)}")
                
                results.append({
                    'model': model,
                    'status': 'success',
                    'message': 'OK'
                })
            else:
                print(f"[ERROR] No choices in response")
                print(f"响应内容：{data}")
                results.append({
                    'model': model,
                    'status': 'error',
                    'message': 'No choices in response'
                })
        else:
            print(f"[ERROR] HTTP {response.status_code}")
            print(f"错误信息：{response.text[:200]}")
            results.append({
                'model': model,
                'status': 'error',
                'message': f'HTTP {response.status_code}'
            })
    
    except Exception as e:
        print(f"[ERROR] Exception: {str(e)}")
        results.append({
            'model': model,
            'status': 'error',
            'message': str(e)
        })

# 汇总结果
print("\n" + "="*60)
print("测试结果汇总")
print("="*60)

success_count = sum(1 for r in results if r['status'] == 'success')
error_count = len(results) - success_count

print(f"总计：{len(results)} 个模型")
print(f"[SUCCESS]: {success_count} models")
print(f"[FAILED]: {error_count} models")
print()

for result in results:
    status_mark = "[OK]" if result['status'] == 'success' else "[FAIL]"
    print(f"{status_mark} {result['model']}: {result['message']}")

print("\n" + "="*60)
