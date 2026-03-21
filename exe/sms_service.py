# sms_service.py - 短信服务模块，专门用于发送短信验证码
import requests
import json
import base64
import hashlib
import ssl
from urllib3 import poolmanager
import time
import random
import re
import os
from datetime import datetime

# 配置参数（与smsallvery.py保持一致）
EC_NAME = "江苏省南菁高级中学"
AP_ID = "NJ_AI"
SECRET_KEY = "Njzx@1998"
SIGN_TEMPLATE = "MrXlbspGI"
# VERIFY_TEMPLATE_ID 从环境变量读取，若不存在则使用默认值
VERIFY_TEMPLATE_ID = os.environ.get('SMS_VERIFY_TEMPLATE_ID', '4f1104a668c24845bc12f9c89c86c6e4')
ADD_SERIAL = ""
API_URL_TEMPLATE = "https://112.35.10.201:28888/sms/tmpsubmit"

# 创建忽略证书验证的适配器
class TLSAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        """创建自定义的SSL上下文"""
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

class SMSService:
    def __init__(self):
        self.session = requests.Session()
        self.session.mount('https://', TLSAdapter())
    
    def send_verification_code(self, phone, verify_code, validity="5"):
        """
        发送短信验证码
        
        参数:
            phone: 手机号码
            verify_code: 验证码
            validity: 有效期（分钟），默认5分钟
        
        返回:
            success: 是否成功
            message: 返回消息
        """
        try:
            # 验证手机号格式
            if not re.match(r'^1[3-9]\d{9}$', phone):
                return False, "无效的手机号码格式"
            
            mobiles = phone
            params = json.dumps([verify_code])
            #params = json.dumps([verify_code, validity])
            
            # 生成MAC校验码
            mac_str = EC_NAME + AP_ID + SECRET_KEY + VERIFY_TEMPLATE_ID + mobiles + params + SIGN_TEMPLATE + ADD_SERIAL
            mac = hashlib.md5(mac_str.encode('utf-8')).hexdigest()
            
            # 构造请求数据
            request_data = {
                "ecName": EC_NAME,
                "apId": AP_ID,
                "templateId": VERIFY_TEMPLATE_ID,
                "mobiles": mobiles,
                "params": params,
                "sign": SIGN_TEMPLATE,
                "addSerial": ADD_SERIAL,
                "mac": mac
            }
            
            print(f"📱 发送短信验证码到 {phone}: {verify_code}，有效期{validity}分钟")
            
            # 对请求数据进行BASE64编码
            json_data = json.dumps(request_data)
            base64_data = base64.b64encode(json_data.encode('utf-8'))
            
            # 发送请求
            headers = {'Content-Type': 'application/json'}
            response = self.session.post(
                API_URL_TEMPLATE,
                data=base64_data,
                headers=headers,
                timeout=30
            )
            
            # 处理响应
            if response.status_code == 200:
                result = response.json()
                if result.get('success') or result.get('rspcod') == 'success':
                    return True, f"验证码已发送到{phone}"
                else:
                    error_msg = result.get('rspcod', '未知错误')
                    return False, f"短信发送失败: {error_msg}"
            else:
                return False, f"HTTP错误: {response.status_code}"
            
        except Exception as e:
            print(f"❌ 发送短信验证码失败: {str(e)}")
            return False, f"发送失败: {str(e)}"
    
    def send_bulk_verification_codes(self, phones, verify_codes, validity="5"):
        """
        批量发送不同的验证码
        
        参数:
            phones: 手机号码列表
            verify_codes: 验证码列表
            validity: 有效期（分钟）
        
        返回:
            results: 每个号码的发送结果列表
        """
        results = []
        for i, phone in enumerate(phones):
            verify_code = verify_codes[i] if i < len(verify_codes) else str(random.randint(100000, 999999))
            success, message = self.send_verification_code(phone, verify_code, validity)
            
            if success:
                results.append({
                    'phone': phone,
                    'code': verify_code,
                    'success': True,
                    'message': message
                })
            else:
                results.append({
                    'phone': phone,
                    'success': False,
                    'message': message
                })
            
            # 避免发送过快
            time.sleep(0.5)
        
        return results

# 全局短信服务实例
sms_service = SMSService()

def send_sms_verification(phone, verify_code, validity="5"):
    """发送短信验证码的便捷函数"""
    return sms_service.send_verification_code(phone, verify_code, validity)

def generate_sms_code():
    """生成6位随机短信验证码"""
    return str(random.randint(100000, 999999))

def verify_phone_format(phone):
    """验证手机号格式"""
    return bool(re.match(r'^1[3-9]\d{9}$', phone))

if __name__ == "__main__":
    # 测试短信发送功能
    test_phone = "13815120911"  # 替换为实际测试号码
    test_code = generate_sms_code()
    
    print(f"🧪 测试短信发送功能...")
    success, message = send_sms_verification(test_phone, test_code)
    
    if success:
        print(f"✅ 测试成功: {message}")
    else:
        print(f"❌ 测试失败: {message}")
