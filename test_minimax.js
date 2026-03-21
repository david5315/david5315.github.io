# 请在下面的引号内填入你的阿里云 MiniMax API Key

const apiKey = "sk-"; // 替换为你的 API key

const baseUrl = "https://api.minimax.chat/v1"; // 保持不变
const modelId = "minimax-m2.5"; // 保持不变

// 测试连接
fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
    },
    body: JSON.stringify({
        model: modelId,
        messages: [{ role: 'user', content: 'Hello' }]
    })
})
.then(res => res.json())
.then(data => console.log('MiniMax 连接测试:', data))
.catch(err => console.error('错误:', err));
