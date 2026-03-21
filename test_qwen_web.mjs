// 使用 Qwen 3.5-Flash 生成课堂投票页面
async function testQwen() {
    const apiKey = 'sk-0d242b2a93e445b8be509dd9feccd9b6'; // qwen-custom
    const baseUrl = 'https://dashscope-us.aliyuncs.com/compatible-mode/v1';
    
    const prompt = `请为一个「课堂问卷投票」活动创建完整的 HTML 页面，用于信息技术课高一 (1) 班第 3 次课的实时投票活动。教师：老张

功能需求：
1. 支持单选和多选题型 (至少 3 道题目)
2. 匿名投票选项
3. 实时统计图表展示投票结果 (用饼图或柱状图)
4. 投票后显示统计结果和进度条
5. 现代化 UI 设计，渐变色背景，卡片式布局
6. 响应式设计适配手机和电脑

技术要点：
- 使用 Canvas 或 Chart.js 绘制图表
- FormData 提交到 /api/submit
- 包含 teacher='老张', activity_id='课堂实时投票 - 第 3 次课' 字段
- 美观的交互体验和加载状态

请直接返回完整可用的 HTML 代码。`;

    try {
        console.log('正在调用 Qwen-3.5-Flash...\n');
        
        const response = await fetch(`${baseUrl}/chat/completions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify({
                model: 'qwen3.5-flash',
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
        console.log('\n✅ Qwen 响应成功！\n');
        console.log(result.choices[0].message.content);

    } catch (error) {
        console.error('❌ 请求失败:', error.message);
    }
}

testQwen();
