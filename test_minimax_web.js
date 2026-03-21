const fetch = require('node-fetch');

async function testMinimax() {
    const apiKey = 'sk-81d5a28abec94bc6bd9dbbe27342980f';
    const baseUrl = 'https://api.minimax.chat/v1';
    
    const prompt = `请为一个「课堂问卷投票」活动创建完整的 HTML 页面。要求：
    
功能需求：
1. 支持单选和多选题型（至少 3 道题目）
2. 匿名投票选项
3. 实时统计图表展示投票结果
4. 投票后显示统计结果和进度条
5. 现代化 UI 设计，渐变色背景

技术要点：
- 使用 Canvas 或 Chart.js 绘制饼图/柱状图
- 表单提交到 /api/submit
- 包含 teacher、activity_id 字段
- 响应式设计

请直接返回完整可用的 HTML 代码。`;

    try {
        console.log('正在调用 MiniMax-2.5...\n');
        
        const response = await fetch(`${baseUrl}/chat/completions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify({
                model: 'minimax-m2.5',
                messages: [
                    {
                        role: 'user',
                        content: prompt
                    }
                ],
                max_tokens: 8192,
                temperature: 0.7
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        console.log('\n✅ MiniMax 响应成功！\n');
        console.log(result.choices[0].message.content);

    } catch (error) {
        console.error('❌ 请求失败:', error.message);
    }
}

testMinimax();
