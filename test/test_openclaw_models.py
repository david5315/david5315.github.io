# test_openclaw_models.py - 测试模型并生成 OpenClaw 配置

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
    {"id": "kimi-k2.5", "name": "Kimi K2.5"},
    {"id": "glm-5", "name": "GLM-5"},
    {"id": "qwen3.5-plus", "name": "Qwen3.5-Plus"},
    {"id": "qwen3-max-2026-01-23", "name": "Qwen3-Max"},
    {"id": "qwen3.5-flash", "name": "Qwen3.5-Flash"}
]

# 测试提示词
TEST_PROMPT = "请用一句话介绍你自己"

print("="*70)
print("OpenClaw Model Compatibility Test")
print("="*70)
print(f"API Base URL: {BASE_URL}")
print(f"API Key: {API_KEY[:20]}...")
print(f"Testing {len(MODELS)} models")
print("="*70)
print()

# 创建会话
session = requests.Session()
session.mount('https://', TLSAdapter())

# 测试结果
results = []
working_models = []

# 逐个测试模型
for model in MODELS:
    model_id = model["id"]
    model_name = model["name"]
    print(f"\n[TEST] {model_name} ({model_id})")
    print("-" * 70)
    
    try:
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant"},
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
        
        print(f"HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                content = data['choices'][0]['message']['content']
                print(f"[OK] Response: {content[:80]}...")
                
                # 获取 token 使用信息
                usage = data.get('usage', {})
                total_tokens = usage.get('total_tokens', 0)
                context_window = 200000  # 默认值
                max_tokens = 8192  # 默认值
                
                print(f"[Token] Total: {total_tokens}")
                
                results.append({
                    'model_id': model_id,
                    'model_name': model_name,
                    'status': 'success',
                    'context_window': context_window,
                    'max_tokens': max_tokens,
                    'supports_images': False  # 需要进一步测试
                })
                
                working_models.append(model)
            else:
                print(f"[ERROR] No choices in response")
                results.append({
                    'model_id': model_id,
                    'model_name': model_name,
                    'status': 'error',
                    'error': 'No choices in response'
                })
        else:
            print(f"[ERROR] HTTP {response.status_code}")
            print(f"Error: {response.text[:200]}")
            results.append({
                'model_id': model_id,
                'model_name': model_name,
                'status': 'error',
                'error': f'HTTP {response.status_code}'
            })
    
    except Exception as e:
        print(f"[ERROR] Exception: {str(e)}")
        results.append({
            'model_id': model_id,
            'model_name': model_name,
            'status': 'error',
            'error': str(e)
        })

# 汇总结果
print("\n" + "="*70)
print("Test Summary")
print("="*70)

success_count = sum(1 for r in results if r['status'] == 'success')
error_count = len(results) - success_count

print(f"Total: {len(results)} models")
print(f"Success: {success_count} models")
print(f"Failed: {error_count} models")
print()

for result in results:
    status_mark = "[OK]" if result['status'] == 'success' else "[FAIL]"
    print(f"{status_mark} {result['model_name']} ({result['model_id']}): {result.get('error', 'OK')}")

# 生成 OpenClaw 配置
if working_models:
    print("\n" + "="*70)
    print("OpenClaw Configuration (models.json)")
    print("="*70)
    
    openclaw_config = {
        "providers": {
            "dashscope-custom": {
                "baseUrl": BASE_URL,
                "apiKey": API_KEY,
                "models": []
            }
        }
    }
    
    for model in working_models:
        model_config = {
            "id": model["id"],
            "name": model["name"],
            "api": "openai-completions",
            "reasoning": False,
            "input": ["text"],
            "cost": {
                "input": 0,
                "output": 0,
                "cacheRead": 0,
                "cacheWrite": 0
            },
            "contextWindow": 200000,
            "maxTokens": 8192
        }
        openclaw_config["providers"]["dashscope-custom"]["models"].append(model_config)
    
    print(json.dumps(openclaw_config, indent=2, ensure_ascii=False))
    
    # 保存到文件
    config_file = "openclaw_models_config.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(openclaw_config, f, indent=2, ensure_ascii=False)
    
    print(f"\n[INFO] Configuration saved to: {config_file}")
    print("\nTo apply this configuration:")
    print(f"  1. Backup your current models.json")
    print(f"  2. Merge the 'dashscope-custom' provider into your models.json")
    print(f"  3. Or replace the 'qwen-custom' provider with this new one")
    print(f"  4. Restart OpenClaw gateway")

print("\n" + "="*70)
