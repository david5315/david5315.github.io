// API基础URL
const API_BASE = window.location.origin;

// 数据存储
let questionCounter = 0;
let classes = [];
let currentAssignment = null;
let assignments = [];
let isEditMode = false;
let questionTypes = {
    'text': '文本题',
    'choice': '选择题',
    'multiple-choice': '多选题',
    'fill': '填空题',
    'code': '编程题',
    'interactive': '互动题'
};

// AI助手相关数据存储
let promptTemplates = [];
let assignmentTemplates = [];
let selectedPromptTemplateId = null;
let selectedAssignmentTemplateId = null;
let currentAIAssignment = null;
let referenceImages = [];
let referenceAttachments = [];

// 内置引导提示词
const BUILT_IN_GUIDE_PROMPT = `你是一个专业的作业题目生成AI。请根据用户的需求生成符合以下JSON格式的作业数据：

作业数据格式要求：
{
  "title": "作业标题",
  "description": "作业描述",
  "questions": [
    {
      "type": "问题类型", // 可选值: "choice"(单选题), "multiple-choice"(多选题), "text"(文本题), "fill"(填空题), "code"(编程题), "interactive"(互动题)
      "question": "问题内容",
      "options": ["选项1", "选项2", ...], // 仅选择题需要
      "answer": "参考答案", // 单选题返回字母如"A"，多选题返回字母数组如["A", "C"]
      "answers": ["答案1", "答案2", ...], // 仅填空题需要，可多个正确答案
      "score": 分值, // 整数，如10
      "gradingPrompt": "本题批改提示词", // 指导AI如何批改本题
      "timeLimit": 时间限制, // 仅编程题需要，单位秒
      "memoryLimit": 内存限制, // 仅编程题需要，单位MB
      "language": "编程语言", // 仅编程题需要，如"python"
      "codeTemplate": "代码模板", // 仅编程题需要
      "interactiveCode": "互动代码", // 仅互动题需要，HTML/JS代码
      "images": [], // 图片URL数组（只保存路径）
      "attachments": [] // 附件数组（只保存路径信息）
    }
  ],
  "assignmentGradingPrompt": "作业级别批改提示词" // 指导AI如何批改整个作业
}

题型说明：
1. 单选题 (choice): 需要提供options数组包含多个选项，answer为单个字母
2. 多选题 (multiple-choice): 需要提供options数组包含多个选项，answer为字母数组
3. 文本题 (text): 学生输入文本回答
4. 填空题 (fill): 需要提供answers数组包含可能的正确答案
5. 编程题 (code): 需要设置时间限制、内存限制、编程语言和代码模板
6. 互动题 (interactive): 需要提供interactiveCode包含HTML/JS代码

图片和附件只保存路径信息，不要保存文件内容。

请确保生成的作业数据结构完整，题目难度适中，内容准确。根据用户的具体需求生成相应数量和类型的题目。`;

// ==================== API调用函数 ====================

async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            credentials: 'include', // 包含cookie
            ...options
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('API调用失败:', response.status, errorText);
            throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
        }
        
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return await response.json();
        } else {
            const text = await response.text();
            console.warn('非JSON响应:', text);
            return { success: false, message: '服务器返回了非JSON响应' };
        }
    } catch (error) {
        console.error('API调用失败:', error);
        throw error;
    }
}

// ==================== 班级选择功能 ====================

// 加载班级数据
async function loadClasses() {
    try {
        console.log('正在加载班级数据...');
        const response = await apiCall('/api/classes');
        
        console.log('班级数据响应:', response);
        
        if (response.success) {
            // 确保classes包含id和name属性
            classes = response.classes.map(classItem => {
                return {
                    id: classItem.name, // 
                    name: classItem.name
                };
            });
            console.log('成功加载班级:', classes.length, '个');
            renderClassSelection();
            
            // 如果没有班级数据，显示提示信息
            if (classes.length === 0 && response.message) {
                const container = document.getElementById('class-selection-container');
                container.innerHTML = `
                    <div class="alert alert-warning">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        ${response.message}
                        <div class="mt-2">
                            <a href="admin_management.html" class="btn btn-sm btn-outline-primary">
                                <i class="fas fa-cog me-1"></i> 前往班级管理
                            </a>
                        </div>
                    </div>
                `;
            }
        } else {
            // API调用失败
            throw new Error(response.message || '加载班级数据失败');
        }
    } catch (error) {
        console.error('加载班级数据失败:', error);
        const container = document.getElementById('class-selection-container');
        container.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-circle me-2"></i>
                加载班级数据失败: ${error.message}
                <button type="button" class="btn btn-sm btn-outline-primary mt-2" onclick="loadClasses()">
                    <i class="fas fa-redo me-1"></i> 重试
                </button>
            </div>
        `;
    }
}

// 渲染班级选择界面
function renderClassSelection() {
    const container = document.getElementById('class-selection-container');
    
    if (!classes || classes.length === 0) {
        container.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle me-2"></i>
                您还没有任教的班级。请联系管理员为您分配班级，或者如果您是管理员，请先创建班级。
                <div class="mt-2">
                    <a href="admin_management.html" class="btn btn-sm btn-outline-primary">
                        <i class="fas fa-cog me-1"></i> 前往班级管理
                    </a>
                </div>
            </div>
        `;
        return;
    }
    
    let html = '';
    
    classes.forEach(classItem => {
        // 获取班级名称和班级ID
        const className = classItem.name || classItem.className || '未命名班级';
        const classId = classItem.id || `class_${Date.now()}`;
        
        // 检查当前作业是否已经发布到该班级（编辑模式）
        let isSelected = false;
        if (currentAssignment && currentAssignment.targetClasses) {
            // 确保 targetClasses 是数组
            const targetClasses = Array.isArray(currentAssignment.targetClasses) 
                ? currentAssignment.targetClasses 
                : [currentAssignment.targetClasses];
            
            isSelected =  targetClasses.includes(className) ;
        }
        
        html += `
            <div class="class-checkbox-item-simple ${isSelected ? 'selected' : ''}">
                <div class="form-check">
                    <input class="form-check-input class-checkbox" 
                           type="checkbox" 
                           value="${className}" 
                           id="class-${classId}" 
                           ${isSelected ? 'checked' : ''}>
                    <label class="form-check-label" for="class-${classId}">
                        ${className}
                    </label>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
    
    // 更新选中班级数量
    updateSelectedClassesCount();
    
    // 添加班级选择事件监听
    document.querySelectorAll('.class-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const classItem = this.closest('.class-checkbox-item-simple');
            if (this.checked) {
                classItem.classList.add('selected');
            } else {
                classItem.classList.remove('selected');
            }
            updateSelectedClassesCount();
            updateSelectAllCheckbox();
        });
    });
    
    // 添加班级卡片点击事件
    document.querySelectorAll('.class-checkbox-item-simple').forEach(item => {
        item.addEventListener('click', function(e) {
            // 如果点击的是checkbox或label，不处理，让默认事件处理
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'LABEL') {
                return;
            }
            
            const checkbox = this.querySelector('.class-checkbox');
            if (checkbox) {
                checkbox.checked = !checkbox.checked;
                checkbox.dispatchEvent(new Event('change'));
            }
        });
    });
    
    // 初始化全选复选框
    updateSelectAllCheckbox();
}

// 更新选中班级数量
function updateSelectedClassesCount() {
    const selectedCount = getSelectedClassNames().length;
    document.getElementById('selected-classes-count').textContent = selectedCount;
}

// 更新全选复选框状态
function updateSelectAllCheckbox() {
    const selectAllCheckbox = document.getElementById('select-all-classes');
    if (!selectAllCheckbox) return;
    
    const checkboxes = document.querySelectorAll('.class-checkbox');
    const checkedCount = getSelectedClassNames().length;
    
    if (checkboxes.length === 0) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
    } else if (checkedCount === checkboxes.length) {
        selectAllCheckbox.checked = true;
        selectAllCheckbox.indeterminate = false;
    } else if (checkedCount > 0) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = true;
    } else {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
    }
}

// 获取选中的班级ID
function getSelectedClassNames() {
    const selectedClasses = [];
    document.querySelectorAll('.class-checkbox:checked').forEach(checkbox => {
        selectedClasses.push(checkbox.value);
    });
    return selectedClasses;
}

// ==================== 全选功能 ====================

// 初始化全选功能
function initSelectAll() {
    const selectAllCheckbox = document.getElementById('select-all-classes');
    if (!selectAllCheckbox) return;
    
    selectAllCheckbox.addEventListener('change', function() {
        const checkboxes = document.querySelectorAll('.class-checkbox');
        const isChecked = this.checked;
        
        checkboxes.forEach(checkbox => {
            checkbox.checked = isChecked;
            const classItem = checkbox.closest('.class-checkbox-item-simple');
            if (isChecked) {
                classItem.classList.add('selected');
            } else {
                classItem.classList.remove('selected');
            }
        });
        
        updateSelectedClassesCount();
    });
}

// ==================== 问题导航功能 ====================

// 更新问题导航
function updateQuestionsNavigation() {
    const questionCards = document.querySelectorAll('.question-card');
    const navigation = document.getElementById('questions-navigation');
    const countElement = document.getElementById('questions-count');
    const typeCountsElement = document.getElementById('question-type-counts');
    const quickNavElement = document.getElementById('questions-quick-nav');
    
    if (questionCards.length === 0) {
        navigation.style.display = 'none';
        return;
    }
    
    navigation.style.display = 'block';
    
    // 更新问题数量
    countElement.textContent = `共 ${questionCards.length} 个问题`;
    
    // 统计问题类型
    const typeCounts = {};
    Object.keys(questionTypes).forEach(type => {
        typeCounts[type] = 0;
    });
    
    questionCards.forEach(card => {
        const type = card.querySelector('input[type="radio"]:checked').value;
        if (typeCounts[type] !== undefined) {
            typeCounts[type]++;
        }
    });
    
    // 更新类型统计
    typeCountsElement.innerHTML = '';
    Object.keys(typeCounts).forEach(type => {
        if (typeCounts[type] > 0) {
            const badge = document.createElement('span');
            badge.className = `type-badge badge bg-secondary`;
            badge.textContent = `${questionTypes[type]}: ${typeCounts[type]}`;
            typeCountsElement.appendChild(badge);
        }
    });
    
    // 更新快速导航
    quickNavElement.innerHTML = '';
    questionCards.forEach((card, index) => {
        const questionNumber = index + 1;
        const navButton = document.createElement('a');
        navButton.href = `#question-${questionNumber}`;
        navButton.className = 'question-nav-btn';
        navButton.textContent = questionNumber;
        navButton.onclick = function(e) {
            e.preventDefault();
            scrollToQuestion(questionNumber);
            setActiveNavButton(questionNumber);
        };
        quickNavElement.appendChild(navButton);
    });
    
    // 默认激活第一个按钮
    if (questionCards.length > 0) {
        setActiveNavButton(1);
    }
}

// 滚动到指定问题
function scrollToQuestion(questionNumber) {
    const questionCards = document.querySelectorAll('.question-card');
    if (questionNumber > 0 && questionNumber <= questionCards.length) {
        const targetCard = questionCards[questionNumber - 1];
        targetCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        
        // 添加高亮效果
        targetCard.style.boxShadow = '0 0 0 2px #007bff';
        setTimeout(() => {
            targetCard.style.boxShadow = '';
        }, 2000);
    }
}

// 设置激活的导航按钮
function setActiveNavButton(questionNumber) {
    const navButtons = document.querySelectorAll('.question-nav-btn');
    navButtons.forEach((button, index) => {
        if (index + 1 === questionNumber) {
            button.classList.add('active');
        } else {
            button.classList.remove('active');
        }
    });
}

// ==================== AI助手功能 ====================

// 加载提示词模板
async function loadPromptTemplates() {
    try {
        const response = await apiCall('/api/prompt-templates');
        if (response.success) {
            promptTemplates = response.promptTemplates || [];
            renderPromptTemplateSelect();
        } else {
            console.error('加载提示词模板失败:', response.message);
            promptTemplates = [];
            renderPromptTemplateSelect();
        }
    } catch (error) {
        console.error('加载提示词模板失败:', error);
        promptTemplates = [];
        renderPromptTemplateSelect();
    }
}

// 渲染提示词模板下拉菜单
function renderPromptTemplateSelect() {
    const select = document.getElementById('prompt-template-select');
    select.innerHTML = '<option value="">请选择模板...</option>';
    
    promptTemplates.forEach(template => {
        const option = document.createElement('option');
        option.value = template.id;
        option.textContent = `${template.name} (${template.subject || '未分类'} - ${template.difficulty || '中等'})`;
        select.appendChild(option);
    });
}

// 显示单题提示词模板预览
function showPromptTemplatePreview(templateId) {
    const template = promptTemplates.find(t => t.id === templateId);
    const previewContainer = document.getElementById('prompt-template-preview');
    
    if (template) {
        previewContainer.innerHTML = `
            <div class="template-preview-content preserve-linebreaks">${template.content}</div>
        `;
    } else {
        previewContainer.innerHTML = '<div class="text-muted text-center py-3">选择模板后预览内容将显示在这里</div>';
    }
}

// 使用单题提示词模板
function usePromptTemplate(templateId) {
    const template = promptTemplates.find(t => t.id === templateId);
    if (template) {
        document.getElementById('ai-prompt').value = template.content;
        selectedPromptTemplateId = templateId;
    }
}

// 保存单题提示词模板
async function savePromptTemplate(isOverwrite = false) {
    const content = document.getElementById('ai-prompt').value.trim();
    
    if (!content) {
        alert('请输入提示词内容');
        return;
    }

    try {
        if (isOverwrite && selectedPromptTemplateId) {
            // 覆盖保存
            await apiCall(`/api/prompt-templates/${selectedPromptTemplateId}`, {
                method: 'PUT',
                body: JSON.stringify({
                    content: content
                })
            });
            alert('模板已更新');
        } else {
            // 新增保存
            const templateName = prompt('请输入模板名称:');
            if (templateName) {
                await apiCall('/api/prompt-templates', {
                    method: 'POST',
                    body: JSON.stringify({
                        name: templateName,
                        content: content
                    })
                });
                alert('模板已保存');
            }
        }
        await loadPromptTemplates();
    } catch (error) {
        alert('保存模板失败: ' + error.message);
    }
}

// ==================== 综合作业提示词模板管理 ====================

// 加载作业模板
async function loadAssignmentTemplates() {
    try {
        const response = await apiCall('/api/assignment-templates');
        if (response.success) {
            assignmentTemplates = response.assignmentTemplates || [];
            renderAssignmentTemplateSelect();
        } else {
            console.error('加载作业模板失败:', response.message);
            assignmentTemplates = [];
            renderAssignmentTemplateSelect();
        }
    } catch (error) {
        console.error('加载作业模板失败:', error);
        assignmentTemplates = [];
        renderAssignmentTemplateSelect();
    }
}

// 渲染作业模板下拉菜单
function renderAssignmentTemplateSelect() {
    const select = document.getElementById('assignment-template-select');
    select.innerHTML = '<option value="">请选择模板...</option>';
    
    assignmentTemplates.forEach(template => {
        const option = document.createElement('option');
        option.value = template.id;
        option.textContent = `${template.name} (${template.subject || '未分类'} - ${template.difficulty || '中等'})`;
        select.appendChild(option);
    });
}

// 显示综合作业提示词模板预览
function showAssignmentTemplatePreview(templateId) {
    const template = assignmentTemplates.find(t => t.id === templateId);
    const previewContainer = document.getElementById('assignment-template-preview');
    
    if (template) {
        previewContainer.innerHTML = `
            <div class="mb-2">
                <strong>${template.name}</strong>
                <span class="badge bg-primary ms-2">${template.subject || '未分类'}</span>
                <span class="badge bg-secondary ms-1">${template.difficulty || '中等'}</span>
                <span class="badge bg-info ms-1">${template.estimatedTime || 30}分钟</span>
            </div>
            <div class="template-preview-content preserve-linebreaks">${template.content}</div>
        `;
    } else {
        previewContainer.innerHTML = '<div class="text-muted text-center py-3">选择模板后预览内容将显示在这里</div>';
    }
}

// 使用综合作业提示词模板
function useAssignmentTemplate(templateId) {
    const template = assignmentTemplates.find(t => t.id === templateId);
    if (template) {
        document.getElementById('ai-prompt').value = template.content;
        selectedAssignmentTemplateId = templateId;
    }
}

// 保存综合作业提示词模板
async function saveAssignmentTemplate(isOverwrite = false) {
    const content = document.getElementById('ai-prompt').value.trim();
    
    if (!content) {
        alert('请输入作业模板内容');
        return;
    }

    try {
        if (isOverwrite && selectedAssignmentTemplateId) {
            // 覆盖保存
            await apiCall(`/api/assignment-templates/${selectedAssignmentTemplateId}`, {
                method: 'PUT',
                body: JSON.stringify({
                    content: content
                })
            });
            alert('模板已更新');
        } else {
            // 新增保存
            const templateName = prompt('请输入作业模板名称:');
            if (templateName) {
                const subject = prompt('请输入学科:') || '通用';
                const difficulty = prompt('请输入难度(简单/中等/困难):') || '中等';
                const estimatedTime = parseInt(prompt('请输入预计完成时间(分钟):') || '30');
                
                await apiCall('/api/assignment-templates', {
                    method: 'POST',
                    body: JSON.stringify({
                        name: templateName,
                        content: content,
                        subject: subject,
                        difficulty: difficulty,
                        estimatedTime: estimatedTime,
                        questionTypes: [] // 可以从内容中分析，这里简化处理
                    })
                });
                alert('作业模板已保存');
            }
        }
        await loadAssignmentTemplates();
    } catch (error) {
        alert('保存作业模板失败: ' + error.message);
    }
}

// ==================== 文件管理功能 ====================

// 获取文件类型图标
function getFileIcon(fileType) {
    if (fileType.startsWith('image/')) return 'fas fa-file-image';
    if (fileType.includes('pdf')) return 'fas fa-file-pdf';
    if (fileType.includes('word') || fileType.includes('document')) return 'fas fa-file-word';
    if (fileType.includes('excel') || fileType.includes('spreadsheet')) return 'fas fa-file-excel';
    if (fileType.includes('powerpoint') || fileType.includes('presentation')) return 'fas fa-file-powerpoint';
    if (fileType.includes('zip') || fileType.includes('compressed')) return 'fas fa-file-archive';
    if (fileType.includes('text')) return 'fas fa-file-alt';
    if (fileType.includes('audio')) return 'fas fa-file-audio';
    if (fileType.includes('video')) return 'fas fa-file-video';
    return 'fas fa-file';
}

// 获取文件类型文本
function getFileTypeText(fileType) {
    if (fileType.startsWith('image/')) return '图片';
    if (fileType.includes('pdf')) return 'PDF';
    if (fileType.includes('word') || fileType.includes('document')) return 'Word';
    if (fileType.includes('excel') || fileType.includes('spreadsheet')) return 'Excel';
    if (fileType.includes('powerpoint') || fileType.includes('presentation')) return 'PowerPoint';
    if (fileType.includes('zip') || fileType.includes('compressed')) return '压缩文件';
    if (fileType.includes('text')) return '文本';
    if (fileType.includes('audio')) return '音频';
    if (fileType.includes('video')) return '视频';
    return '文件';
}

// ==================== 图片上传功能 ====================

// 上传图片到服务器
async function uploadQuestionImage(file, questionIndex) {
    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('questionIndex', questionIndex);
        
        // 如果有作业ID，添加到表单数据
        const assignmentId = document.getElementById('assignment-id').value;
        if (assignmentId) {
            formData.append('assignmentId', assignmentId);
        }
        
        const response = await fetch(`${API_BASE}/api/upload/question-image`, {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`上传失败: ${response.status} ${errorText}`);
        }
        
        const result = await response.json();
        return result;
    } catch (error) {
        console.error('上传图片失败:', error);
        throw error;
    }
}

// 处理多张图片选择 - 修改为上传到服务器
async function handleMultipleImageSelect(input, questionIndex) {
    const files = input.files;
    const previewContainer = document.getElementById(`image-previews-${questionIndex}`);
    
    if (files.length === 0) return;
    
    // 显示上传进度
    const progressDiv = document.createElement('div');
    progressDiv.className = 'upload-progress';
    progressDiv.innerHTML = `
        <div class="progress">
            <div class="progress-bar" role="progressbar" style="width: 0%">0%</div>
        </div>
    `;
    previewContainer.parentNode.insertBefore(progressDiv, previewContainer.nextSibling);
    
    const progressBar = progressDiv.querySelector('.progress-bar');
    progressDiv.style.display = 'block';
    
    const uploadedImages = [];
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        if (!file.type.startsWith('image/')) {
            alert(`文件 ${file.name} 不是图片文件，已跳过`);
            continue;
        }
        
        try {
            // 更新进度
            const progress = Math.round(((i + 1) / files.length) * 100);
            progressBar.style.width = `${progress}%`;
            progressBar.textContent = `${progress}%`;
            
            // 上传图片
            const result = await uploadQuestionImage(file, questionIndex);
            
            if (result.success) {
                // 创建图片预览项
                const imageItem = document.createElement('div');
                imageItem.className = 'image-preview-item';
                imageItem.innerHTML = `
                    <img src="${result.imageUrl}" onclick="showImage('${result.imageUrl}')" style="cursor: pointer;">
                    <button type="button" class="remove-image-btn" onclick="removeImagePreview(this, '${result.imageUrl}')">
                        <i class="fas fa-times"></i>
                    </button>
                    <input type="hidden" name="question-${questionIndex}-images" value="${result.imageUrl}">
                `;
                previewContainer.appendChild(imageItem);
                
                uploadedImages.push(result.imageUrl);
            } else {
                alert(`上传图片 ${file.name} 失败: ${result.message}`);
            }
        } catch (error) {
            console.error(`上传图片 ${file.name} 失败:`, error);
            alert(`上传图片 ${file.name} 失败: ${error.message}`);
        }
    }
    
    // 隐藏进度条
    setTimeout(() => {
        progressDiv.style.display = 'none';
    }, 1000);
    
    // 重置文件输入，允许重复选择相同文件
    input.value = '';
}

// 移除图片预览
function removeImagePreview(button, imageUrl) {
    const imageItem = button.closest('.image-preview-item');
    if (imageItem) {
        imageItem.remove();
    }
}

// ==================== 附件上传功能 ====================

// 上传附件到服务器
async function uploadAttachment(file, questionIndex) {
    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('questionIndex', questionIndex);
        
        // 如果有作业ID，添加到表单数据
        const assignmentId = document.getElementById('assignment-id').value;
        if (assignmentId) {
            formData.append('assignmentId', assignmentId);
        }
        
        const response = await fetch(`${API_BASE}/api/upload/attachment`, {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`上传失败: ${response.status} ${errorText}`);
        }
        
        const result = await response.json();
        return result;
    } catch (error) {
        console.error('上传附件失败:', error);
        throw error;
    }
}

// 处理附件选择 - 修改为上传到服务器
async function handleAttachmentSelect(input, questionIndex) {
    const files = input.files;
    const attachmentsContainer = document.getElementById(`attachments-${questionIndex}`);
    
    if (files.length === 0) return;
    
    // 显示上传进度
    const progressDiv = document.createElement('div');
    progressDiv.className = 'upload-progress';
    progressDiv.innerHTML = `
        <div class="progress">
            <div class="progress-bar" role="progressbar" style="width: 0%">0%</div>
        </div>
    `;
    attachmentsContainer.parentNode.insertBefore(progressDiv, attachmentsContainer.nextSibling);
    
    const progressBar = progressDiv.querySelector('.progress-bar');
    progressDiv.style.display = 'block';
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        // 检查文件大小（限制50MB）
        if (file.size > 50 * 1024 * 1024) {
            alert(`文件 ${file.name} 太大（超过50MB），已跳过`);
            continue;
        }
        
        // 创建上传中状态
        const uploadingItem = document.createElement('div');
        uploadingItem.className = 'attachment-item';
        uploadingItem.innerHTML = `
            <div class="attachment-icon">
                <i class="fas fa-spinner fa-spin"></i>
            </div>
            <div class="attachment-info">
                <div class="attachment-name">
                    ${file.name}
                    <span class="badge bg-secondary file-type-badge">上传中...</span>
                </div>
            </div>
        `;
        attachmentsContainer.appendChild(uploadingItem);
        
        try {
            // 更新进度
            const progress = Math.round(((i + 1) / files.length) * 100);
            progressBar.style.width = `${progress}%`;
            progressBar.textContent = `${progress}%`;
            
            // 上传附件
            const result = await uploadAttachment(file, questionIndex);
            
            // 移除上传中状态
            uploadingItem.remove();
            
            if (result.success) {
                // 创建附件项
                const attachmentItem = document.createElement('div');
                attachmentItem.className = 'attachment-item';
                
                const fileIcon = getFileIcon(file.type);
                const fileType = getFileTypeText(file.type);
                
                attachmentItem.innerHTML = `
                    <div class="attachment-icon">
                        <i class="${fileIcon}"></i>
                    </div>
                    <div class="attachment-info">
                        <div class="attachment-name">
                            ${result.originalFilename || file.name}
                            <span class="badge bg-secondary file-type-badge">${fileType}</span>
                        </div>
                        <input type="text" class="attachment-description" placeholder="请输入文件说明..." 
                               name="question-${questionIndex}-attachment-desc" data-filename="${result.filename || file.name}">
                    </div>
                    <button type="button" class="remove-attachment-btn" onclick="this.parentElement.remove()">
                        <i class="fas fa-times"></i>
                    </button>
                    <input type="hidden" name="question-${questionIndex}-attachments" 
                           value='${JSON.stringify({
                                filename: result.filename || file.name,
                                originalFilename: result.originalFilename || file.name,
                                fileUrl: result.fileUrl || '',
                                fileType: file.type,
                                description: ''
                           })}'>
                `;
                
                attachmentsContainer.appendChild(attachmentItem);
            } else {
                alert(`上传文件 ${file.name} 失败: ${result.message}`);
            }
        } catch (error) {
            // 移除上传中状态
            uploadingItem.remove();
            console.error(`上传文件 ${file.name} 失败:`, error);
            alert(`上传文件 ${file.name} 失败: ${error.message}`);
        }
    }
    
    // 隐藏进度条
    setTimeout(() => {
        progressDiv.style.display = 'none';
    }, 1000);
    
    // 重置文件输入
    input.value = '';
}

// ==================== 选择题功能 ====================

// 添加选项
function addOption(questionIndex, value = '') {
    const container = document.getElementById(`options-container-${questionIndex}`);
    const correctAnswerSelect = document.getElementById(`correct-answer-select-${questionIndex}`);
    
    const optionIndex = container.children.length;
    const optionLetter = String.fromCharCode(65 + optionIndex);
    
    const optionDiv = document.createElement('div');
    optionDiv.className = 'option-item-editable';
    optionDiv.innerHTML = `
        <div class="option-letter">${optionLetter}</div>
        <input type="text" class="form-control option-input" value="${value}" placeholder="请输入选项 ${optionLetter} 的内容">
        <button type="button" class="btn btn-sm btn-outline-danger" onclick="this.parentElement.remove(); updateCorrectAnswerOptions(${questionIndex})">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    container.appendChild(optionDiv);
    updateCorrectAnswerOptions(questionIndex);
}

// 更新正确答案选项
function updateCorrectAnswerOptions(questionIndex) {
    const container = document.getElementById(`options-container-${questionIndex}`);
    const correctAnswerSelect = document.getElementById(`correct-answer-select-${questionIndex}`);
    
    if (!correctAnswerSelect) return;
    
    // 清空现有选项
    correctAnswerSelect.innerHTML = '';
    
    // 添加新选项
    container.querySelectorAll('.option-input').forEach((input, index) => {
        const letter = String.fromCharCode(65 + index);
        const option = document.createElement('option');
        option.value = letter;
        option.textContent = `${letter}. ${input.value || `选项${letter}`}`;
        correctAnswerSelect.appendChild(option);
    });
}

// 获取选择题选项和正确答案
function getChoiceQuestionData(questionIndex) {
    const container = document.getElementById(`options-container-${questionIndex}`);
    const correctAnswerSelect = document.getElementById(`correct-answer-select-${questionIndex}`);
    
    const options = [];
    container.querySelectorAll('.option-input').forEach(input => {
        if (input.value.trim()) {
            options.push(input.value.trim());
        }
    });
    
    return {
        options: options,
        correctAnswer: correctAnswerSelect ? correctAnswerSelect.value : ''
    };
}

// 获取多选题答案
function getMultipleChoiceAnswers(questionIndex) {
    const answers = [];
    document.querySelectorAll(`#multiple-answers-${questionIndex} .multiple-answer-checkbox:checked`).forEach(checkbox => {
        answers.push(checkbox.value);
    });
    return answers;
}

// ==================== 填空题答案管理 ====================

// 添加填空题答案输入项
function addFillBlankAnswer(questionIndex, value = '') {
    const container = document.getElementById(`fill-blank-answers-${questionIndex}`);
    const answerItem = document.createElement('div');
    answerItem.className = 'fill-blank-item';
    answerItem.innerHTML = `
        <input type="text" class="form-control fill-blank-answer" value="${value}" placeholder="请输入填空答案">
        <button type="button" class="remove-fill-blank" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    container.appendChild(answerItem);
}

// 初始化填空题答案输入项
function initFillBlankAnswers(questionIndex, answers = []) {
    const container = document.getElementById(`fill-blank-answers-${questionIndex}`);
    container.innerHTML = '';
    if (answers.length === 0) {
        addFillBlankAnswer(questionIndex);
    } else {
        answers.forEach(answer => {
            addFillBlankAnswer(questionIndex, answer);
        });
    }
}

// 获取填空题所有答案
function getFillBlankAnswers(questionIndex) {
    const container = document.getElementById(`fill-blank-answers-${questionIndex}`);
    const answers = [];
    container.querySelectorAll('.fill-blank-answer').forEach(input => {
        if (input.value.trim() !== '') {
            answers.push(input.value.trim());
        }
    });
    return answers;
}

// ==================== 评测数据管理 ====================

// 处理评测数据文件选择
function handleTestDataFilesChange(questionIndex, event) {
    const files = event.target.files;
    const fileNamesContainer = document.getElementById(`test-data-file-names-${questionIndex}`);
    
    if (files.length === 0) {
        fileNamesContainer.style.display = 'none';
        fileNamesContainer.innerHTML = '';
        return;
    }
    
    // 显示文件名
    fileNamesContainer.style.display = 'block';
    const fileNames = Array.from(files).map(file => file.name).join(', ');
    fileNamesContainer.innerHTML = `<strong>已选择文件:</strong> ${fileNames}`;
}

// 上传并解析评测数据
async function uploadTestDataFiles(questionIndex) {
    const filesInput = document.querySelector(`#question-${questionIndex} .question-test-data-files`);
    const files = filesInput.files;
    
    if (files.length === 0) {
        alert('请先选择评测数据文件');
        return;
    }
    
    try {
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }
        
        const response = await fetch(`${API_BASE}/api/testdata/process`, {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP错误! 状态码: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            const testDataArray = result.test_data;
            const editor = document.querySelector(`#question-${questionIndex} .question-test-data`);
            
            // 将评测数据显示在文本框中
            editor.value = JSON.stringify(testDataArray, null, 2);
            
            alert('评测数据解析成功！');
        } else {
            throw new Error(result.message);
        }
        
    } catch (error) {
        alert('处理评测数据失败: ' + error.message);
    }
}

// ==================== 引导提示词功能 ====================

// 显示引导提示词模态框
function showGuidePrompt() {
    document.getElementById('guide-prompt-text').value = BUILT_IN_GUIDE_PROMPT;
    document.getElementById('guide-prompt-modal').classList.remove('hidden');
}

// 隐藏引导提示词模态框
function hideGuidePrompt() {
    document.getElementById('guide-prompt-modal').classList.add('hidden');
}

// 复制引导提示词到输入框
function copyGuidePromptToInput() {
    document.getElementById('ai-prompt').value = BUILT_IN_GUIDE_PROMPT;
    hideGuidePrompt();
}

// ==================== 模板选项卡功能 ====================

// 切换模板选项卡
function switchTemplateTab(tabName) {
    // 更新选项卡激活状态
    document.querySelectorAll('.template-tab').forEach(tab => {
        if (tab.dataset.tab === tabName) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });
    
    // 显示对应的内容区域
    document.querySelectorAll('.template-content-area').forEach(area => {
        area.classList.add('hidden');
    });
    
    if (tabName === 'prompt-templates') {
        document.getElementById('prompt-templates-content').classList.remove('hidden');
    } else if (tabName === 'assignment-templates') {
        document.getElementById('assignment-templates-content').classList.remove('hidden');
    } else if (tabName === 'ai-generation') {
        document.getElementById('ai-generation-content').classList.remove('hidden');
    }
}

// ==================== 图片查看功能 ====================

// 初始化图片模态框
function initImageModal() {
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImage');
    const closeBtn = document.getElementsByClassName('close-image-modal')[0];
    
    // 点击关闭按钮
    closeBtn.onclick = function() {
        modal.style.display = 'none';
    }
    
    // 点击模态框背景关闭
    modal.onclick = function(event) {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    }
    
    // ESC键关闭
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            modal.style.display = 'none';
        }
    });
}

// 显示图片
function showImage(src) {
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImage');
    modal.style.display = 'block';
    modalImg.src = src;
}

// ==================== 问题管理功能 ====================

// 根据数据添加问题
function addQuestionFromData(questionData) {
    questionCounter++;
    const container = document.getElementById('questions-container');
    
    const questionCard = document.createElement('div');
    questionCard.className = 'card question-card mb-3';
    questionCard.id = `question-${questionCounter}`;
    
    // 根据不同题型生成不同的HTML
    let optionsHtml = '';
    let programmingSettingsHtml = '';
    let interactiveCodeHtml = '';
    let fillBlankAnswersHtml = '';
    let testDataHtml = '';
    
    // 选择题选项设置 - 分为单选题和多选题
    if (questionData.type === 'choice' || questionData.type === 'multiple-choice') {
        const isMultiple = questionData.type === 'multiple-choice';
        
        optionsHtml = `
            <div class="question-options mb-3">
                <div class="choice-type-selector">
                    <label class="form-label">选择题类型</label>
                    <div class="choice-type-buttons">
                        <button type="button" class="choice-type-btn ${!isMultiple ? 'active' : ''}" onclick="switchChoiceType(${questionCounter}, false)">
                            单选题
                        </button>
                        <button type="button" class="choice-type-btn ${isMultiple ? 'active' : ''}" onclick="switchChoiceType(${questionCounter}, true)">
                            多选题
                        </button>
                    </div>
                </div>
                <label class="form-label">选项设置</label>
                <div id="options-container-${questionCounter}">
                    <!-- 选项将通过JS动态生成 -->
                </div>
                <button type="button" class="btn btn-sm btn-outline-primary mt-2" onclick="addOption(${questionCounter})">
                    <i class="fas fa-plus me-1"></i> 添加选项
                </button>
                
                <!-- 单选题答案选择 -->
                <div class="correct-answer-selector mt-2 ${isMultiple ? 'hidden' : ''}" id="single-answer-selector-${questionCounter}">
                    <label class="form-label">正确答案（单选）</label>
                    <select class="form-select" id="correct-answer-select-${questionCounter}">
                        <!-- 选项将通过JS动态填充 -->
                    </select>
                </div>
                
                <!-- 多选题答案选择 -->
                <div class="multiple-choice-answers mt-2 ${!isMultiple ? 'hidden' : ''}" id="multiple-answers-${questionCounter}">
                    <label class="form-label">正确答案（多选）</label>
                    <div id="multiple-answers-container-${questionCounter}">
                        <!-- 多选题选项将通过JS动态生成 -->
                    </div>
                </div>
            </div>
        `;
    } else {
        optionsHtml = `
            <div class="question-options mb-3" style="display: none;">
                <div class="choice-type-selector">
                    <label class="form-label">选择题类型</label>
                    <div class="choice-type-buttons">
                        <button type="button" class="choice-type-btn active" onclick="switchChoiceType(${questionCounter}, false)">
                            单选题
                        </button>
                        <button type="button" class="choice-type-btn" onclick="switchChoiceType(${questionCounter}, true)">
                            多选题
                        </button>
                    </div>
                </div>
                <label class="form-label">选项设置</label>
                <div id="options-container-${questionCounter}">
                    <!-- 选项将通过JS动态生成 -->
                </div>
                <button type="button" class="btn btn-sm btn-outline-primary mt-2" onclick="addOption(${questionCounter})">
                    <i class="fas fa-plus me-1"></i> 添加选项
                </button>
                
                <!-- 单选题答案选择 -->
                <div class="correct-answer-selector mt-2" id="single-answer-selector-${questionCounter}">
                    <label class="form-label">正确答案（单选）</label>
                    <select class="form-select" id="correct-answer-select-${questionCounter}">
                        <!-- 选项将通过JS动态填充 -->
                    </select>
                </div>
                
                <!-- 多选题答案选择 -->
                <div class="multiple-choice-answers mt-2 hidden" id="multiple-answers-${questionCounter}">
                    <label class="form-label">正确答案（多选）</label>
                    <div id="multiple-answers-container-${questionCounter}">
                        <!-- 多选题选项将通过JS动态生成 -->
                    </div>
                </div>
            </div>
        `;
    }
    
    // 编程题设置
    if (questionData.type === 'code') {
        programmingSettingsHtml = `
            <div class="programming-settings">
                <h6><i class="fas fa-cog me-2"></i>编程题目设置</h6>
                <div class="row">
                    <div class="col-md-3">
                        <label class="form-label">时间限制（秒）</label>
                        <input type="number" class="form-control question-time-limit" min="1" max="30" value="${questionData.timeLimit || 5}">
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">内存限制（MB）</label>
                        <input type="number" class="form-control question-memory-limit" min="64" max="1024" value="${questionData.memoryLimit || 256}">
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">编程语言</label>
                        <select class="form-select question-language">
                            <option value="python" ${(questionData.language || 'python') === 'python' ? 'selected' : ''}>Python</option>
                            <option value="java" ${(questionData.language || 'python') === 'java' ? 'selected' : ''}>Java</option>
                            <option value="cpp" ${(questionData.language || 'python') === 'cpp' ? 'selected' : ''}>C++</option>
                            <option value="c" ${(questionData.language || 'python') === 'c' ? 'selected' : ''}>C</option>
                            <option value="javascript" ${(questionData.language || 'python') === 'javascript' ? 'selected' : ''}>JavaScript</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">启用代码评测</label>
                        <div class="form-check form-switch">
                            <input class="form-check-input question-code-testing" type="checkbox" ${questionData.codeTesting !== false ? 'checked' : ''}>
                            <label class="form-check-label">启用</label>
                        </div>
                    </div>
                </div>
                <div class="code-template-section">
                    <label class="form-label">代码模板</label>
                    <textarea class="form-control code-template-textarea question-code-template" placeholder="提供给学生的基础代码模板...">${questionData.codeTemplate || ''}</textarea>
                </div>
            </div>
        `;
        
        // 评测数据区域
        testDataHtml = `
            <div class="test-data-section">
                <label class="form-label">评测数据</label>
                <textarea class="form-control test-data-editor-textarea question-test-data" placeholder="评测数据将显示在这里...">${questionData.testData ? JSON.stringify(questionData.testData, null, 2) : '[{"id":"01","input":"22\\n","output":"2 11\\n"},{"id":"02","input":"3414\\n","output":"2 3 569\\n"}]'}</textarea>
                <div class="form-text">
                    评测数据格式：JSON数组，每个对象包含id、input和output字段。示例：
                    [{"id":"01","input":"22\\n","output":"2 11\\n"},{"id":"02","input":"3414\\n","output":"2 3 569\\n"}]
                </div>
                
                <!-- 评测数据文件上传 -->
                <div class="mt-3">
                    <label class="form-label">评测数据文件上传</label>
                    <input type="file" class="form-control question-test-data-files" multiple accept=".in,.out" onchange="handleTestDataFilesChange(${questionCounter}, event)">
                    <div class="form-text">
                        支持上传多个评测数据文件。文件名格式：数据编号.扩展名，例如01.in，01.out。
                        数据编号为2位，从01开始。
                    </div>
                    <div id="test-data-file-names-${questionCounter}" class="test-data-file-names" style="display: none;">
                        <!-- 选择的文件名将显示在这里 -->
                    </div>
                </div>
                
                <!-- 评测数据操作按钮 -->
                <div class="test-data-buttons">
                    <button type="button" class="btn btn-outline-primary" onclick="uploadTestDataFiles(${questionCounter})">
                        <i class="fas fa-upload me-1"></i> 上传并解析评测数据
                    </button>
                    <button type="button" class="btn btn-outline-success" onclick="generateTestData(${questionCounter})">
                        <i class="fas fa-robot me-1"></i> AI生成评测数据
                    </button>
                </div>
            </div>
        `;
    } else {
        programmingSettingsHtml = `
            <div class="programming-settings" style="display: none;">
                <h6><i class="fas fa-cog me-2"></i>编程题目设置</h6>
                <div class="row">
                    <div class="col-md-3">
                        <label class="form-label">时间限制（秒）</label>
                        <input type="number" class="form-control question-time-limit" min="1" max="30" value="5">
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">内存限制（MB）</label>
                        <input type="number" class="form-control question-memory-limit" min="64" max="1024" value="256">
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">编程语言</label>
                        <select class="form-select question-language">
                            <option value="python">Python</option>
                            <option value="java">Java</option>
                            <option value="cpp">C++</option>
                            <option value="c">C</option>
                            <option value="javascript">JavaScript</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">启用代码评测</label>
                        <div class="form-check form-switch">
                            <input class="form-check-input question-code-testing" type="checkbox" checked>
                            <label class="form-check-label">启用</label>
                        </div>
                    </div>
                </div>
                <div class="code-template-section">
                    <label class="form-label">代码模板</label>
                    <textarea class="form-control code-template-textarea question-code-template" placeholder="提供给学生的基础代码模板..."></textarea>
                </div>
            </div>
        `;
        
        testDataHtml = `
            <div class="test-data-section" style="display: none;">
                <label class="form-label">评测数据</label>
                <textarea class="form-control test-data-editor-textarea question-test-data" placeholder="评测数据将显示在这里...">[{"id":"01","input":"22\\n","output":"2 11\\n"},{"id":"02","input":"3414\\n","output":"2 3 569\\n"}]</textarea>
                <div class="form-text">
                    评测数据格式：JSON数组，每个对象包含id、input和output字段。示例：
                    [{"id":"01","input":"22\\n","output":"2 11\\n"},{"id":"02","input":"3414\\n","output":"2 3 569\\n"}]
                </div>
                
                <!-- 评测数据文件上传 -->
                <div class="mt-3">
                    <label class="form-label">评测数据文件上传</label>
                    <input type="file" class="form-control question-test-data-files" multiple accept=".in,.out" onchange="handleTestDataFilesChange(${questionCounter}, event)">
                    <div class="form-text">
                        支持上传多个评测数据文件。文件名格式：数据编号.扩展名，例如01.in，01.out。
                        数据编号为2位，从01开始。
                    </div>
                    <div id="test-data-file-names-${questionCounter}" class="test-data-file-names" style="display: none;">
                        <!-- 选择的文件名将显示在这里 -->
                    </div>
                </div>
                
                <!-- 评测数据操作按钮 -->
                <div class="test-data-buttons">
                    <button type="button" class="btn btn-outline-primary" onclick="uploadTestDataFiles(${questionCounter})">
                        <i class="fas fa-upload me-1"></i> 上传并解析评测数据
                    </button>
                    <button type="button" class="btn btn-outline-success" onclick="generateTestData(${questionCounter})">
                        <i class="fas fa-robot me-1"></i> AI生成评测数据
                    </button>
                </div>
            </div>
        `;
    }
    
    // 互动题设置
    if (questionData.type === 'interactive') {
        interactiveCodeHtml = `
            <div class="interactive-code-section">
                <h6><i class="fas fa-code me-2"></i>互动代码</h6>
                <div class="mb-3">
                    <label class="form-label">互动代码内容</label>
                    <textarea class="form-control interactive-code-textarea question-interactive-code" placeholder="请输入互动代码（HTML、JavaScript等）...">${questionData.interactiveCode || ''}</textarea>
                    <div class="form-text">互动题将显示此代码区域，支持HTML、JavaScript等，用于创建交互式学习体验。</div>
                </div>
            </div>
        `;
    } else {
        interactiveCodeHtml = `
            <div class="interactive-code-section" style="display: none;">
                <h6><i class="fas fa-code me-2"></i>互动代码</h6>
                <div class="mb-3">
                    <label class="form-label">互动代码内容</label>
                    <textarea class="form-control interactive-code-textarea question-interactive-code" placeholder="请输入互动代码（HTML、JavaScript等）..."></textarea>
                    <div class="form-text">互动题将显示此代码区域，支持HTML、JavaScript等，用于创建交互式学习体验。</div>
                </div>
            </div>
        `;
    }
    
    // 填空题答案设置
    if (questionData.type === 'fill') {
        fillBlankAnswersHtml = `
            <div class="fill-blank-answers mb-3">
                <label class="form-label">填空答案（可多个）</label>
                <div class="fill-blank-answers" id="fill-blank-answers-${questionCounter}">
                    <!-- 答案将通过JS动态生成 -->
                </div>
                <button type="button" class="btn btn-sm btn-outline-primary mt-2" onclick="addFillBlankAnswer(${questionCounter})">
                    <i class="fas fa-plus me-1"></i> 添加答案
                </button>
            </div>
        `;
    } else {
        fillBlankAnswersHtml = `
            <div class="fill-blank-answers mb-3" style="display: none;">
                <label class="form-label">填空答案（可多个）</label>
                <div class="fill-blank-answers" id="fill-blank-answers-${questionCounter}">
                    <!-- 答案将通过JS动态生成 -->
                </div>
                <button type="button" class="btn btn-sm btn-outline-primary mt-2" onclick="addFillBlankAnswer(${questionCounter})">
                    <i class="fas fa-plus me-1"></i> 添加答案
                </button>
            </div>
        `;
    }
    
    // 显示已有图片预览（如果有）
    let existingImagesHtml = '';
    if (questionData.images && questionData.images.length > 0) {
        existingImagesHtml = `
            <div class="mb-2">
                <label class="form-label">当前配图</label>
                <div class="image-preview-container" id="image-previews-${questionCounter}">
                    ${questionData.images.map((img, imgIndex) => `
                        <div class="image-preview-item">
                            <img src="${API_BASE}${img}" onclick="showImage('${API_BASE}${img}')" style="cursor: pointer;">
                            <button type="button" class="remove-image-btn" onclick="removeImagePreview(this, '${img}')">
                                <i class="fas fa-times"></i>
                            </button>
                            <input type="hidden" name="question-${questionCounter}-images" value="${img}">
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    } else {
        existingImagesHtml = `
            <div class="image-preview-container" id="image-previews-${questionCounter}"></div>
        `;
    }
    
    // 显示已有附件（如果有）
    let existingAttachmentsHtml = '';
    if (questionData.attachments && questionData.attachments.length > 0) {
        existingAttachmentsHtml = `
            <div class="attachments-container">
                <label class="form-label">当前附件</label>
                <div id="attachments-${questionCounter}">
                    ${questionData.attachments.map((attachment, attIndex) => {
                        const fileIcon = getFileIcon(attachment.fileType || '');
                        const fileType = getFileTypeText(attachment.fileType || '');
                        const fileUrl = attachment.fileUrl || '';
                        const filename = attachment.filename || attachment.originalFilename || '未命名文件';
                        
                        return `
                        <div class="attachment-item">
                            <div class="attachment-icon">
                                <i class="${fileIcon}"></i>
                            </div>
                            <div class="attachment-info">
                                <div class="attachment-name">
                                    ${filename}
                                    <span class="badge bg-secondary file-type-badge">${fileType}</span>
                                </div>
                                <input type="text" class="attachment-description" 
                                       value="${attachment.description || ''}" 
                                       name="question-${questionCounter}-attachment-desc" 
                                       data-filename="${attachment.filename || filename}">
                            </div>
                            <button type="button" class="remove-attachment-btn" onclick="this.parentElement.remove()">
                                <i class="fas fa-times"></i>
                            </button>
                            <input type="hidden" name="question-${questionCounter}-attachments" 
                                   value='${JSON.stringify(attachment)}'>
                        </div>
                    `}).join('')}
                </div>
            </div>
        `;
    } else {
        existingAttachmentsHtml = `
            <div class="attachments-container">
                <div id="attachments-${questionCounter}"></div>
            </div>
        `;
    }
    
    questionCard.innerHTML = `
        <div class="card-body">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h6 class="card-title mb-0">问题 ${questionCounter}</h6>
                <button type="button" class="btn-close" onclick="removeQuestion(${questionCounter})"></button>
            </div>
            <div class="question-type-select">
                <label class="form-label">题目类型</label>
                <div class="btn-group" role="group" aria-label="题目类型">
                    <input type="radio" class="btn-check" name="question-type-${questionCounter}" id="question-type-text-${questionCounter}" value="text" ${questionData.type === 'text' ? 'checked' : ''}>
                    <label class="btn btn-outline-primary" for="question-type-text-${questionCounter}">文本题</label>
                    
                    <input type="radio" class="btn-check" name="question-type-${questionCounter}" id="question-type-choice-${questionCounter}" value="choice" ${questionData.type === 'choice' ? 'checked' : ''}>
                    <label class="btn btn-outline-primary" for="question-type-choice-${questionCounter}">单选题</label>
                    
                    <input type="radio" class="btn-check" name="question-type-${questionCounter}" id="question-type-multiple-choice-${questionCounter}" value="multiple-choice" ${questionData.type === 'multiple-choice' ? 'checked' : ''}>
                    <label class="btn btn-outline-primary" for="question-type-multiple-choice-${questionCounter}">多选题</label>
                    
                    <input type="radio" class="btn-check" name="question-type-${questionCounter}" id="question-type-fill-${questionCounter}" value="fill" ${questionData.type === 'fill' ? 'checked' : ''}>
                    <label class="btn btn-outline-primary" for="question-type-fill-${questionCounter}">填空题</label>
                    
                    <input type="radio" class="btn-check" name="question-type-${questionCounter}" id="question-type-code-${questionCounter}" value="code" ${questionData.type === 'code' ? 'checked' : ''}>
                    <label class="btn btn-outline-primary" for="question-type-code-${questionCounter}">编程题</label>
                    
                    <input type="radio" class="btn-check" name="question-type-${questionCounter}" id="question-type-interactive-${questionCounter}" value="interactive" ${questionData.type === 'interactive' ? 'checked' : ''}>
                    <label class="btn btn-outline-primary" for="question-type-interactive-${questionCounter}">互动题</label>
                </div>
            </div>
            <div class="mb-3">
                <label class="form-label">问题内容</label>
                <textarea class="form-control question-content preserve-linebreaks" rows="2" required>${questionData.question || ''}</textarea>
            </div>
            <div class="mb-3">
                <label class="form-label">问题配图（可选，可多张）</label>
                <input type="file" class="form-control question-images" multiple accept="image/*" 
                       onchange="handleMultipleImageSelect(this, ${questionCounter})">
                <div class="form-text">为问题添加多张配图，帮助学生更好地理解题目</div>
                ${existingImagesHtml}
            </div>
            <div class="mb-3">
                <label class="form-label">附件（可选，可多个）</label>
                <input type="file" class="form-control question-attachments" multiple
                       onchange="handleAttachmentSelect(this, ${questionCounter})">
                <div class="form-text">为问题添加附件，如静态网站、网页、文档、音频、视频等</div>
                ${existingAttachmentsHtml}
            </div>
            ${optionsHtml}
            ${programmingSettingsHtml}
            ${testDataHtml}
            ${interactiveCodeHtml}
            ${fillBlankAnswersHtml}
            <div class="mb-3">
                <label class="form-label">参考答案</label>
                <textarea class="form-control question-answer preserve-linebreaks answer-textarea" rows="2" placeholder="请输入参考答案，用于学生答题时作为指导" required>${questionData.answer || ''}</textarea>
                <div class="form-text">学生答题时会在答题框下方看到此参考答案作为答题指导</div>
            </div>
            <div class="mb-3">
                <label class="form-label">问题分值</label>
                <input type="number" class="form-control question-score" value="${questionData.score || 10}" min="1" max="100" required>
                <div class="form-text">设置本题的分值，默认为10分</div>
            </div>
            <!-- 问题级别阅卷提示词 -->
            <div class="mb-3">
                <label class="form-label">
                    <i class="fas fa-robot me-1"></i> 本题阅卷提示词
                </label>
                <textarea class="form-control question-grading-prompt preserve-linebreaks" rows="2" placeholder="请输入本题的特定批改要求...">${questionData.gradingPrompt || ''}</textarea>
                <div class="form-text">此提示词将指导AI如何批改本题，例如：关注解题步骤、重视公式推导等</div>
            </div>
        </div>
    `;
    
    container.appendChild(questionCard);
    
    // 初始化选项（如果是选择题）
    if ((questionData.type === 'choice' || questionData.type === 'multiple-choice') && questionData.options) {
        questionData.options.forEach((option, index) => {
            addOption(questionCounter, option);
        });
        
        // 初始化答案
        if (questionData.type === 'choice' && questionData.correctAnswer) {
            // 单选题
            const correctAnswerSelect = document.getElementById(`correct-answer-select-${questionCounter}`);
            if (correctAnswerSelect) {
                correctAnswerSelect.value = questionData.correctAnswer;
            }
        } else if (questionData.type === 'multiple-choice' && questionData.answer) {
            // 多选题
            const answers = Array.isArray(questionData.answer) ? questionData.answer : [questionData.answer];
            const answersContainer = document.getElementById(`multiple-answers-container-${questionCounter}`);
            
            // 创建多选题答案选项
            if (answersContainer) {
                questionData.options.forEach((option, index) => {
                    const letter = String.fromCharCode(65 + index);
                    const isChecked = answers.includes(letter);
                    
                    const answerItem = document.createElement('div');
                    answerItem.className = 'multiple-answer-item';
                    answerItem.innerHTML = `
                        <input type="checkbox" class="form-check-input multiple-answer-checkbox" 
                               value="${letter}" id="multiple-answer-${questionCounter}-${letter}" ${isChecked ? 'checked' : ''}>
                        <label class="form-check-label" for="multiple-answer-${questionCounter}-${letter}">
                            ${letter}. ${option}
                        </label>
                    `;
                    answersContainer.appendChild(answerItem);
                });
            }
        }
    }
    
    // 初始化填空题答案
    if (questionData.type === 'fill' && questionData.answers) {
        initFillBlankAnswers(questionCounter, questionData.answers);
    }
    
    // 为题目类型单选按钮添加事件监听
    document.querySelectorAll(`input[name="question-type-${questionCounter}"]`).forEach(radio => {
        radio.addEventListener('change', function() {
            handleQuestionTypeChange(this, questionCounter);
        });
    });
    
    // 更新问题导航
    updateQuestionsNavigation();
}

// 切换选择题类型
function switchChoiceType(questionIndex, isMultiple) {
    const singleAnswerDiv = document.getElementById(`single-answer-selector-${questionIndex}`);
    const multipleAnswerDiv = document.getElementById(`multiple-answers-${questionIndex}`);
    
    // 更新选择题类型按钮状态
    const buttons = document.querySelectorAll(`#question-${questionIndex} .choice-type-btn`);
    buttons[0].classList.toggle('active', !isMultiple);
    buttons[1].classList.toggle('active', isMultiple);
    
    if (isMultiple) {
        // 切换到多选题
        if (singleAnswerDiv) singleAnswerDiv.classList.add('hidden');
        if (multipleAnswerDiv) multipleAnswerDiv.classList.remove('hidden');
        
        // 创建多选题答案选项
        const optionsContainer = document.getElementById(`options-container-${questionIndex}`);
        const multipleAnswersContainer = document.getElementById(`multiple-answers-container-${questionIndex}`);
        
        if (optionsContainer && multipleAnswersContainer) {
            multipleAnswersContainer.innerHTML = '';
            
            optionsContainer.querySelectorAll('.option-input').forEach((input, index) => {
                const letter = String.fromCharCode(65 + index);
                const value = input.value || `选项${letter}`;
                
                const answerItem = document.createElement('div');
                answerItem.className = 'multiple-answer-item';
                answerItem.innerHTML = `
                    <input type="checkbox" class="form-check-input multiple-answer-checkbox" 
                           value="${letter}" id="multiple-answer-${questionIndex}-${letter}">
                    <label class="form-check-label" for="multiple-answer-${questionIndex}-${letter}">
                        ${letter}. ${value}
                    </label>
                `;
                multipleAnswersContainer.appendChild(answerItem);
            });
        }
    } else {
        // 切换到单选题
        if (singleAnswerDiv) singleAnswerDiv.classList.remove('hidden');
        if (multipleAnswerDiv) multipleAnswerDiv.classList.add('hidden');
    }
}

// 删除问题
function removeQuestion(questionIndex) {
    const questionCard = document.getElementById(`question-${questionIndex}`);
    if (questionCard) {
        questionCard.remove();
        // 重新编号所有问题
        renumberQuestions();
        // 更新问题导航
        updateQuestionsNavigation();
    }
}

// 重新编号问题
function renumberQuestions() {
    const questionCards = document.querySelectorAll('.question-card');
    questionCounter = 0;
    
    questionCards.forEach((card, index) => {
        questionCounter++;
        card.id = `question-${questionCounter}`;
        const title = card.querySelector('.card-title');
        if (title) {
            title.textContent = `问题 ${questionCounter}`;
        }
        
        // 更新所有内部元素的ID和事件监听
        updateQuestionElementIds(card, index + 1, questionCounter);
    });
}

// 更新问题元素的ID
function updateQuestionElementIds(card, oldIndex, newIndex) {
    // 更新所有相关元素的ID和属性
    const elementsToUpdate = [
        'options-container',
        'correct-answer-select',
        'single-answer-selector',
        'multiple-answers',
        'multiple-answers-container',
        'image-previews',
        'attachments',
        'fill-blank-answers',
        'test-data-file-names'
    ];
    
    elementsToUpdate.forEach(prefix => {
        const oldId = `${prefix}-${oldIndex}`;
        const newId = `${prefix}-${newIndex}`;
        const element = card.querySelector(`#${oldId}`);
        if (element) {
            element.id = newId;
        }
    });
    
    // 更新事件监听
    const imageInput = card.querySelector('.question-images');
    if (imageInput) {
        imageInput.setAttribute('onchange', `handleMultipleImageSelect(this, ${newIndex})`);
    }
    
    const attachmentInput = card.querySelector('.question-attachments');
    if (attachmentInput) {
        attachmentInput.setAttribute('onchange', `handleAttachmentSelect(this, ${newIndex})`);
    }
    
    const addOptionBtn = card.querySelector('button[onclick*="addOption"]');
    if (addOptionBtn) {
        addOptionBtn.setAttribute('onclick', `addOption(${newIndex})`);
    }
    
    const addFillBlankBtn = card.querySelector('button[onclick*="addFillBlankAnswer"]');
    if (addFillBlankBtn) {
        addFillBlankBtn.setAttribute('onclick', `addFillBlankAnswer(${newIndex})`);
    }
    
    // 更新隐藏输入字段的name属性
    const hiddenInputs = card.querySelectorAll('input[type="hidden"]');
    hiddenInputs.forEach(input => {
        if (input.name) {
            input.name = input.name.replace(`-${oldIndex}-`, `-${newIndex}-`);
        }
    });
    
    const descInputs = card.querySelectorAll('input.attachment-description');
    descInputs.forEach(input => {
        input.name = `question-${newIndex}-attachment-desc`;
    });
    
    // 更新单选按钮的name属性
    const radioButtons = card.querySelectorAll('input[type="radio"]');
    radioButtons.forEach(radio => {
        radio.name = `question-type-${newIndex}`;
        radio.id = radio.id.replace(`-${oldIndex}`, `-${newIndex}`);
    });
    
    const radioLabels = card.querySelectorAll('label[for^="question-type-"]');
    radioLabels.forEach(label => {
        label.setAttribute('for', label.getAttribute('for').replace(`-${oldIndex}`, `-${newIndex}`));
    });
    
    // 更新多选题checkbox的ID
    const checkboxes = card.querySelectorAll('.multiple-answer-checkbox');
    checkboxes.forEach((checkbox, index) => {
        const letter = String.fromCharCode(65 + index);
        checkbox.id = `multiple-answer-${newIndex}-${letter}`;
        const label = card.querySelector(`label[for="multiple-answer-${oldIndex}-${letter}"]`);
        if (label) {
            label.setAttribute('for', `multiple-answer-${newIndex}-${letter}`);
        }
    });
    
    // 更新测试数据文件上传事件
    const testDataFileInput = card.querySelector('.question-test-data-files');
    if (testDataFileInput) {
        testDataFileInput.setAttribute('onchange', `handleTestDataFilesChange(${newIndex}, event)`);
    }
    
    // 更新测试数据按钮事件
    const testDataButtons = card.querySelectorAll('button[onclick*="uploadTestDataFiles"], button[onclick*="generateTestData"]');
    testDataButtons.forEach(button => {
        const onclick = button.getAttribute('onclick');
        if (onclick) {
            button.setAttribute('onclick', onclick.replace(`(${oldIndex})`, `(${newIndex})`));
        }
    });
}

// 添加问题
function addQuestion() {
    questionCounter++;
    const container = document.getElementById('questions-container');
    
    const questionCard = document.createElement('div');
    questionCard.className = 'card question-card mb-3';
    questionCard.id = `question-${questionCounter}`;
    questionCard.innerHTML = `
        <div class="card-body">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h6 class="card-title mb-0">问题 ${questionCounter}</h6>
                <button type="button" class="btn-close" onclick="removeQuestion(${questionCounter})"></button>
            </div>
            <div class="question-type-select">
                <label class="form-label">题目类型</label>
                <div class="btn-group" role="group" aria-label="题目类型">
                    <input type="radio" class="btn-check" name="question-type-${questionCounter}" id="question-type-text-${questionCounter}" value="text" checked>
                    <label class="btn btn-outline-primary" for="question-type-text-${questionCounter}">文本题</label>
                    
                    <input type="radio" class="btn-check" name="question-type-${questionCounter}" id="question-type-choice-${questionCounter}" value="choice">
                    <label class="btn btn-outline-primary" for="question-type-choice-${questionCounter}">单选题</label>
                    
                    <input type="radio" class="btn-check" name="question-type-${questionCounter}" id="question-type-multiple-choice-${questionCounter}" value="multiple-choice">
                    <label class="btn btn-outline-primary" for="question-type-multiple-choice-${questionCounter}">多选题</label>
                    
                    <input type="radio" class="btn-check" name="question-type-${questionCounter}" id="question-type-fill-${questionCounter}" value="fill">
                    <label class="btn btn-outline-primary" for="question-type-fill-${questionCounter}">填空题</label>
                    
                    <input type="radio" class="btn-check" name="question-type-${questionCounter}" id="question-type-code-${questionCounter}" value="code">
                    <label class="btn btn-outline-primary" for="question-type-code-${questionCounter}">编程题</label>
                    
                    <input type="radio" class="btn-check" name="question-type-${questionCounter}" id="question-type-interactive-${questionCounter}" value="interactive">
                    <label class="btn btn-outline-primary" for="question-type-interactive-${questionCounter}">互动题</label>
                </div>
            </div>
            <div class="mb-3">
                <label class="form-label">问题内容</label>
                <textarea class="form-control question-content preserve-linebreaks" rows="2" required></textarea>
            </div>
            <div class="mb-3">
                <label class="form-label">问题配图（可选，可多张）</label>
                <input type="file" class="form-control question-images" multiple accept="image/*" 
                       onchange="handleMultipleImageSelect(this, ${questionCounter})">
                <div class="form-text">为问题添加多张配图，帮助学生更好地理解题目</div>
                <div class="image-preview-container" id="image-previews-${questionCounter}"></div>
            </div>
            <div class="mb-3">
                <label class="form-label">附件（可选，可多个）</label>
                <input type="file" class="form-control question-attachments" multiple
                       onchange="handleAttachmentSelect(this, ${questionCounter})">
                <div class="form-text">为问题添加附件，如静态网站、网页、文档、音频、视频等</div>
                <div class="attachments-container">
                    <div id="attachments-${questionCounter}"></div>
                </div>
            </div>
            <div class="question-options mb-3" style="display: none;">
                <div class="choice-type-selector">
                    <label class="form-label">选择题类型</label>
                    <div class="choice-type-buttons">
                        <button type="button" class="choice-type-btn active" onclick="switchChoiceType(${questionCounter}, false)">
                            单选题
                        </button>
                        <button type="button" class="choice-type-btn" onclick="switchChoiceType(${questionCounter}, true)">
                            多选题
                        </button>
                    </div>
                </div>
                <label class="form-label">选项设置</label>
                <div id="options-container-${questionCounter}">
                    <!-- 选项将通过JS动态生成 -->
                </div>
                <button type="button" class="btn btn-sm btn-outline-primary mt-2" onclick="addOption(${questionCounter})">
                    <i class="fas fa-plus me-1"></i> 添加选项
                </button>
                
                <!-- 单选题答案选择 -->
                <div class="correct-answer-selector mt-2" id="single-answer-selector-${questionCounter}">
                    <label class="form-label">正确答案（单选）</label>
                    <select class="form-select" id="correct-answer-select-${questionCounter}">
                        <!-- 选项将通过JS动态填充 -->
                    </select>
                </div>
                
                <!-- 多选题答案选择 -->
                <div class="multiple-choice-answers mt-2 hidden" id="multiple-answers-${questionCounter}">
                    <label class="form-label">正确答案（多选）</label>
                    <div id="multiple-answers-container-${questionCounter}">
                        <!-- 多选题选项将通过JS动态生成 -->
                    </div>
                </div>
            </div>
            <div class="programming-settings" style="display: none;">
                <h6><i class="fas fa-cog me-2"></i>编程题目设置</h6>
                <div class="row">
                    <div class="col-md-3">
                        <label class="form-label">时间限制（秒）</label>
                        <input type="number" class="form-control question-time-limit" min="1" max="30" value="5">
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">内存限制（MB）</label>
                        <input type="number" class="form-control question-memory-limit" min="64" max="1024" value="256">
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">编程语言</label>
                        <select class="form-select question-language">
                            <option value="python">Python</option>
                            <option value="java">Java</option>
                            <option value="cpp">C++</option>
                            <option value="c">C</option>
                            <option value="javascript">JavaScript</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">启用代码评测</label>
                        <div class="form-check form-switch">
                            <input class="form-check-input question-code-testing" type="checkbox" checked>
                            <label class="form-check-label">启用</label>
                        </div>
                    </div>
                </div>
                <div class="code-template-section">
                    <label class="form-label">代码模板</label>
                    <textarea class="form-control code-template-textarea question-code-template" placeholder="提供给学生的基础代码模板..."></textarea>
                </div>
            </div>
            <div class="test-data-section" style="display: none;">
                <label class="form-label">评测数据</label>
                <textarea class="form-control test-data-editor-textarea question-test-data" placeholder="评测数据将显示在这里...">[{"id":"01","input":"22\\n","output":"2 11\\n"},{"id":"02","input":"3414\\n","output":"2 3 569\\n"}]</textarea>
                <div class="form-text">
                    评测数据格式：JSON数组，每个对象包含id、input和output字段。示例：
                    [{"id":"01","input":"22\\n","output":"2 11\\n"},{"id":"02","input":"3414\\n","output":"2 3 569\\n"}]
                </div>
                
                <!-- 评测数据文件上传 -->
                <div class="mt-3">
                    <label class="form-label">评测数据文件上传</label>
                    <input type="file" class="form-control question-test-data-files" multiple accept=".in,.out" onchange="handleTestDataFilesChange(${questionCounter}, event)">
                    <div class="form-text">
                        支持上传多个评测数据文件。文件名格式：数据编号.扩展名，例如01.in，01.out。
                        数据编号为2位，从01开始。
                    </div>
                    <div id="test-data-file-names-${questionCounter}" class="test-data-file-names" style="display: none;">
                        <!-- 选择的文件名将显示在这里 -->
                    </div>
                </div>
                
                <!-- 评测数据操作按钮 -->
                <div class="test-data-buttons">
                    <button type="button" class="btn btn-outline-primary" onclick="uploadTestDataFiles(${questionCounter})">
                        <i class="fas fa-upload me-1"></i> 上传并解析评测数据
                    </button>
                    <button type="button" class="btn btn-outline-success" onclick="generateTestData(${questionCounter})">
                        <i class="fas fa-robot me-1"></i> AI生成评测数据
                    </button>
                </div>
            </div>
            <div class="interactive-code-section" style="display: none;">
                <h6><i class="fas fa-code me-2"></i>互动代码</h6>
                <div class="mb-3">
                    <label class="form-label">互动代码内容</label>
                    <textarea class="form-control interactive-code-textarea question-interactive-code" placeholder="请输入互动代码（HTML、JavaScript等）..."></textarea>
                    <div class="form-text">互动题将显示此代码区域，支持HTML、JavaScript等，用于创建交互式学习体验。</div>
                </div>
            </div>
            <div class="fill-blank-answers mb-3" style="display: none;">
                <label class="form-label">填空答案（可多个）</label>
                <div class="fill-blank-answers" id="fill-blank-answers-${questionCounter}">
                    <div class="fill-blank-item">
                        <input type="text" class="form-control fill-blank-answer" placeholder="请输入填空答案">
                        <button type="button" class="remove-fill-blank" onclick="this.parentElement.remove()">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </div>
                <button type="button" class="btn btn-sm btn-outline-primary mt-2" onclick="addFillBlankAnswer(${questionCounter})">
                    <i class="fas fa-plus me-1"></i> 添加答案
                </button>
            </div>
            <div class="mb-3">
                <label class="form-label">参考答案</label>
                <textarea class="form-control question-answer preserve-linebreaks answer-textarea" rows="2" placeholder="请输入参考答案，用于学生答题时作为指导" required></textarea>
                <div class="form-text">学生答题时会在答题框下方看到此参考答案作为答题指导</div>
            </div>
            <div class="mb-3">
                <label class="form-label">问题分值</label>
                <input type="number" class="form-control question-score" value="10" min="1" max="100" required>
                <div class="form-text">设置本题的分值，默认为10分</div>
            </div>
            <!-- 问题级别阅卷提示词 -->
            <div class="mb-3">
                <label class="form-label">
                    <i class="fas fa-robot me-1"></i> 本题阅卷提示词
                </label>
                <textarea class="form-control question-grading-prompt preserve-linebreaks" rows="2" placeholder="请输入本题的特定批改要求..."></textarea>
                <div class="form-text">此提示词将指导AI如何批改本题，例如：关注解题步骤、重视公式推导等</div>
            </div>
        </div>
    `;
    
    container.appendChild(questionCard);
    
    // 为题目类型单选按钮添加事件监听
    document.querySelectorAll(`input[name="question-type-${questionCounter}"]`).forEach(radio => {
        radio.addEventListener('change', function() {
            handleQuestionTypeChange(this, questionCounter);
        });
    });
    
    // 更新问题导航
    updateQuestionsNavigation();
}

// 处理问题类型变化
function handleQuestionTypeChange(radio, questionIndex) {
    const cardBody = radio.closest('.card-body');
    const optionsDiv = cardBody.querySelector('.question-options');
    const programmingSettings = cardBody.querySelector('.programming-settings');
    const testDataSection = cardBody.querySelector('.test-data-section');
    const interactiveCodeSection = cardBody.querySelector('.interactive-code-section');
    const fillBlankAnswers = cardBody.querySelector('.fill-blank-answers');
    
    // 隐藏所有区域
    optionsDiv.style.display = 'none';
    programmingSettings.style.display = 'none';
    testDataSection.style.display = 'none';
    interactiveCodeSection.style.display = 'none';
    fillBlankAnswers.style.display = 'none';
    
    // 根据选择的类型显示对应区域
    if (radio.value === 'choice' || radio.value === 'multiple-choice') {
        optionsDiv.style.display = 'block';
        // 初始化选项
        const container = cardBody.querySelector(`#options-container-${questionIndex}`);
        if (container.children.length === 0) {
            addOption(questionIndex);
            addOption(questionIndex);
        }
    } else if (radio.value === 'code') {
        programmingSettings.style.display = 'block';
        testDataSection.style.display = 'block';
    } else if (radio.value === 'interactive') {
        interactiveCodeSection.style.display = 'block';
    } else if (radio.value === 'fill') {
        fillBlankAnswers.style.display = 'block';
    }
}

// ==================== 作业编辑功能 ====================

// 从URL获取作业ID
function getAssignmentIdFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('id');
}

// 加载作业数据
async function loadAssignmentData() {
    const assignmentId = getAssignmentIdFromUrl();
    if (!assignmentId) {
        // 创建模式
        isEditMode = false;
        document.getElementById('page-title').textContent = '创建作业';
        document.getElementById('save-button-text').textContent = '保存作业';
        document.getElementById('save-button-text-bottom').textContent = '保存作业';
        return;
    }

    // 编辑模式
    isEditMode = true;
    document.getElementById('page-title').textContent = '编辑作业';
    document.getElementById('save-button-text').textContent = '更新作业';
    document.getElementById('save-button-text-bottom').textContent = '更新作业';

    try {
        const response = await apiCall('/api/assignments');
        if (response && Array.isArray(response)) {
            assignments = response;
            currentAssignment = assignments.find(a => a.id === assignmentId);
        } else {
            console.error('获取作业列表失败，响应格式错误:', response);
            throw new Error('获取作业列表失败');
        }
        
        if (!currentAssignment) {
            alert('未找到该作业');
            window.location.href = 'teacher.html';
            return;
        }
        
        console.log('当前作业数据:', currentAssignment); // 调试日志
        
        // 填充表单数据
        document.getElementById('assignment-id').value = currentAssignment.id;
        document.getElementById('assignment-title').value = currentAssignment.title;
        document.getElementById('assignment-description').value = currentAssignment.description || '';
        document.getElementById('assignment-grading-prompt').value = currentAssignment.assignmentGradingPrompt || '';
        document.getElementById('ai-tools-switch').checked = currentAssignment.aiToolsEnabled || false;
        document.getElementById('auto-grading-switch').checked = currentAssignment.autoGrading || false;
        document.getElementById('show-answer-switch').checked = currentAssignment.showAnswer !== false; // 默认true
        
        // 确保 targetClasses 存在且是数组
        if (!currentAssignment.targetClasses) {
            currentAssignment.targetClasses = [];
        } else if (typeof currentAssignment.targetClasses === 'string') {
            // 如果是字符串，转换为数组
            currentAssignment.targetClasses = [currentAssignment.targetClasses];
        }
        
        // 重新渲染班级选择（确保选中状态正确）
        // 注意：这里班级列表可能还没加载完成，我们会在loadClasses完成后再次处理
        // 现在先确保classes加载完成后再执行
        setTimeout(() => {
            renderClassSelection();
        }, 100);
        
        // 清空问题容器并添加现有问题
        const container = document.getElementById('questions-container');
        container.innerHTML = '';
        questionCounter = 0;
        
        if (currentAssignment.questions && Array.isArray(currentAssignment.questions)) {
            currentAssignment.questions.forEach((question, index) => {
                addQuestionFromData(question);
            });
        } else {
            console.warn('作业问题列表为空或格式错误:', currentAssignment.questions);
        }
        
        // 更新问题导航
        updateQuestionsNavigation();
        
    } catch (error) {
        console.error('加载作业数据失败:', error);
        alert('加载作业数据失败: ' + error.message);
        window.location.href = 'teacher.html';
    }
}

// 保存作业
async function saveAssignment() {
    const assignmentId = document.getElementById('assignment-id').value;
    const title = document.getElementById('assignment-title').value;
    const description = document.getElementById('assignment-description').value;
    const assignmentGradingPrompt = document.getElementById('assignment-grading-prompt').value;
    const aiToolsEnabled = document.getElementById('ai-tools-switch').checked;
    const autoGrading = document.getElementById('auto-grading-switch').checked;
    const showAnswer = document.getElementById('show-answer-switch').checked;
    

    const targetClasses = getSelectedClassNames();
    
    if (!title) {
        alert('请输入作业标题');
        return;
    }
    
    if (targetClasses.length === 0) {
        alert('请至少选择一个班级');
        return;
    }
    
    const questionCards = document.querySelectorAll('.question-card');
    if (questionCards.length === 0) {
        alert('请至少添加一个问题');
        return;
    }
    
    const questions = [];
    
    // 处理每个问题
    for (let i = 0; i < questionCards.length; i++) {
        const card = questionCards[i];
        const typeRadio = card.querySelector(`input[name="question-type-${i+1}"]:checked`);
        if (!typeRadio) {
            alert(`问题 ${i + 1} 没有选择题目类型`);
            return;
        }
        
        const type = typeRadio.value;
        const content = card.querySelector('.question-content').value;
        const answer = card.querySelector('.question-answer').value;
        const score = parseInt(card.querySelector('.question-score').value) || 10;
        const gradingPrompt = card.querySelector('.question-grading-prompt').value;
        
        if (!content) {
            alert(`问题 ${i + 1} 的内容不能为空`);
            return;
        }
        
        // 收集图片
        const imageInputs = card.querySelectorAll(`input[name="question-${i+1}-images"]`);
        const images = Array.from(imageInputs).map(input => input.value);
        
        // 收集附件
        const attachmentInputs = card.querySelectorAll(`input[name="question-${i+1}-attachments"]`);
        const attachments = [];
        
        for (const input of attachmentInputs) {
            try {
                const attachmentData = JSON.parse(input.value);
                // 查找对应的描述
                const descInput = card.querySelector(`input[name="question-${i+1}-attachment-desc"][data-filename="${attachmentData.filename}"]`);
                if (descInput) {
                    attachmentData.description = descInput.value;
                }
                attachments.push(attachmentData);
            } catch (e) {
                console.error('解析附件数据失败:', e);
            }
        }
        
        // 根据题目类型收集特定数据
        let questionData = {
            id: currentAssignment?.questions?.[i]?.id || 'Q' + Date.now() + i,
            type,
            question: content,
            images: images,
            attachments: attachments,
            answer: answer,
            score: score,
            gradingPrompt: gradingPrompt
        };
        
        // 单选题数据
        if (type === 'choice') {
            const choiceData = getChoiceQuestionData(i+1);
            questionData.options = choiceData.options;
            questionData.correctAnswer = choiceData.correctAnswer;
            
            if (questionData.options.length < 2) {
                alert(`问题 ${i + 1} 的选择题至少需要两个选项`);
                return;
            }
            
            if (!questionData.correctAnswer) {
                alert(`问题 ${i + 1} 的单选题请选择正确答案`);
                return;
            }
        }
        
        // 多选题数据
        if (type === 'multiple-choice') {
            const choiceData = getChoiceQuestionData(i+1);
            const answers = getMultipleChoiceAnswers(i+1);
            
            questionData.options = choiceData.options;
            questionData.answer = answers;
            
            if (questionData.options.length < 2) {
                alert(`问题 ${i + 1} 的多选题至少需要两个选项`);
                return;
            }
            
            if (answers.length === 0) {
                alert(`问题 ${i + 1} 的多选题请至少选择一个正确答案`);
                return;
            }
        }
        
        // 填空题数据
        if (type === 'fill') {
            questionData.answers = getFillBlankAnswers(i+1);
            if (questionData.answers.length === 0) {
                alert(`问题 ${i + 1} 的填空题至少需要一个答案`);
                return;
            }
        }
        
        // 编程题数据
        if (type === 'code') {
            questionData.timeLimit = parseInt(card.querySelector('.question-time-limit').value) || 5;
            questionData.memoryLimit = parseInt(card.querySelector('.question-memory-limit').value) || 256;
            questionData.language = card.querySelector('.question-language').value;
            questionData.codeTesting = card.querySelector('.question-code-testing').checked;
            questionData.codeTemplate = card.querySelector('.question-code-template').value;
            
            // 收集评测数据
            const testDataText = card.querySelector('.question-test-data').value;
            if (testDataText) {
                try {
                    questionData.testData = JSON.parse(testDataText);
                } catch (e) {
                    console.error('解析评测数据失败:', e);
                }
            }
        }
        
        // 互动题数据
        if (type === 'interactive') {
            questionData.interactiveCode = card.querySelector('.question-interactive-code').value;
        }
        
        questions.push(questionData);
    }
    
    const assignment = {
        id: assignmentId || 'A' + Date.now(),
        title,
        description,
        targetClasses: targetClasses,
        questions,
        assignmentGradingPrompt: assignmentGradingPrompt,
        aiToolsEnabled: aiToolsEnabled,
        autoGrading: autoGrading,
        showAnswer: showAnswer,
        createdAt: currentAssignment?.createdAt || new Date().toISOString()
    };
    
    try {
        if (isEditMode) {
            // 更新作业 - 强制覆盖，不检查重复
            await apiCall(`/api/assignments/${assignmentId}`, {
                method: 'PUT',
                body: JSON.stringify(assignment)
            });
        } else {
            // 创建新作业
            await apiCall('/api/assignments', {
                method: 'POST',
                body: JSON.stringify(assignment)
            });
        }
        
        alert(isEditMode ? '作业更新成功！' : '作业创建成功！');
        window.location.href = 'teacher.html';
    } catch (error) {
        console.error('保存作业失败:', error);
        alert((isEditMode ? '更新' : '保存') + '作业失败，请重试: ' + error.message);
    }
}

// ==================== 初始化函数 ====================

// 初始化
async function initializePage() {
    console.log('初始化页面...');
    
    // 初始化图片模态框
    initImageModal();
    
    // 先加载班级数据，再加载作业数据
    await loadClasses();
    
    // 加载提示词模板
    await loadPromptTemplates();
    
    // 加载作业模板
    await loadAssignmentTemplates();
    
    // 加载作业数据
    await loadAssignmentData();
    
    // 初始化全选功能
    initSelectAll();
    
    // 添加问题按钮事件
    document.getElementById('add-question-btn').addEventListener('click', addQuestion);
    
    // 保存作业按钮事件（右上角）
    document.getElementById('save-assignment-btn').addEventListener('click', saveAssignment);
    
    // 保存作业按钮事件（底部）
    document.getElementById('save-assignment-bottom-btn').addEventListener('click', saveAssignment);
    
    // AI分析作业按钮事件
    document.getElementById('ai-analyze-btn').addEventListener('click', async function() {
        const prompt = document.getElementById('ai-prompt').value.trim();
        
        if (!prompt) {
            alert('请输入AI出题提示词');
            return;
        }
        
        try {
            // 显示处理中状态
            document.getElementById('ai-import-section').classList.add('hidden');
            document.getElementById('ai-processing').classList.remove('hidden');
            
            // 发送到后端API
            const response = await apiCall('/api/ai/generate-assignment', {
                method: 'POST',
                body: JSON.stringify({
                    prompt: prompt,
                    referenceImages: referenceImages,
                    referenceAttachments: referenceAttachments
                })
            });
            
            // 隐藏处理中状态
            document.getElementById('ai-processing').classList.add('hidden');
            
            if (response.success) {
                // 显示分析结果预览
                showAIResultPreview(response.assignment);
            } else {
                alert('AI生成作业失败: ' + response.message);
                document.getElementById('ai-import-section').classList.remove('hidden');
            }
            
        } catch (error) {
            console.error('AI生成作业失败:', error);
            alert('AI生成作业失败: ' + error.message);
            document.getElementById('ai-processing').classList.add('hidden');
            document.getElementById('ai-import-section').classList.remove('hidden');
        }
    });
    
    // 应用AI分析结果按钮事件
    document.getElementById('apply-ai-result-btn').addEventListener('click', applyAIResult);
    
    // 放弃AI分析结果按钮事件
    document.getElementById('discard-ai-result-btn').addEventListener('click', discardAIResult);
    
    // 单题提示词模板选择事件
    document.getElementById('prompt-template-select').addEventListener('change', function() {
        const templateId = this.value;
        showPromptTemplatePreview(templateId);
        if (templateId) {
            usePromptTemplate(templateId);
        }
    });
    
    // 综合作业提示词模板选择事件
    document.getElementById('assignment-template-select').addEventListener('change', function() {
        const templateId = this.value;
        showAssignmentTemplatePreview(templateId);
        if (templateId) {
            useAssignmentTemplate(templateId);
        }
    });
    
    // 单题提示词模板保存按钮事件
    document.getElementById('overwrite-prompt-template-btn').addEventListener('click', function() {
        savePromptTemplate(true);
    });
    
    document.getElementById('add-prompt-template-btn').addEventListener('click', function() {
        savePromptTemplate(false);
    });
    
    // 综合作业提示词模板保存按钮事件
    document.getElementById('overwrite-assignment-template-btn').addEventListener('click', function() {
        saveAssignmentTemplate(true);
    });
    
    document.getElementById('add-assignment-template-btn').addEventListener('click', function() {
        saveAssignmentTemplate(false);
    });
    
    // 引导提示词按钮事件
    document.getElementById('show-guide-prompt-btn').addEventListener('click', showGuidePrompt);
    document.getElementById('close-guide-modal-btn').addEventListener('click', hideGuidePrompt);
    document.getElementById('close-guide-prompt-btn').addEventListener('click', hideGuidePrompt);
    document.getElementById('copy-guide-prompt-btn').addEventListener('click', copyGuidePromptToInput);
    
    // 模板选项卡切换事件
    document.querySelectorAll('.template-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            switchTemplateTab(this.dataset.tab);
        });
    });

    // 检查当前用户登录状态
    try {
        const response = await apiCall('/api/current');
        if (response.success) {
            console.log('当前登录用户:', response.teacher);
        } else {
            console.warn('未登录或获取用户信息失败:', response.message);
        }
    } catch (error) {
        console.log('获取当前用户信息失败:', error);
    }
    
    // AI参考图片上传事件
    const aiReferenceImages = document.getElementById('ai-reference-images');
    if (aiReferenceImages) {
        aiReferenceImages.addEventListener('change', function() {
            // 简化处理，实际应该上传到服务器
            const files = this.files;
            const previewContainer = document.getElementById('image-previews');
            
            Array.from(files).forEach((file, index) => {
                if (file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const imageData = {
                            id: 'img_' + Date.now() + '_' + index,
                            filename: file.name,
                            fileType: file.type,
                            dataUrl: e.target.result
                        };
                        
                        referenceImages.push(imageData);
                        
                        const imageItem = document.createElement('div');
                        imageItem.className = 'image-preview-item';
                        imageItem.innerHTML = `
                            <img src="${e.target.result}">
                            <button type="button" class="remove-image-btn" onclick="removeAIReferenceImage('${imageData.id}')">
                                <i class="fas fa-times"></i>
                            </button>
                        `;
                        previewContainer.appendChild(imageItem);
                    };
                    reader.readAsDataURL(file);
                }
            });
            
            // 重置文件输入
            this.value = '';
        });
    }
    
    // AI参考附件上传事件
    const aiReferenceAttachments = document.getElementById('ai-reference-attachments');
    if (aiReferenceAttachments) {
        aiReferenceAttachments.addEventListener('change', function() {
            // 简化处理，实际应该上传到服务器
            const files = this.files;
            const attachmentsContainer = document.getElementById('attachments-container');
            
            Array.from(files).forEach((file, index) => {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const attachmentData = {
                        id: 'att_' + Date.now() + '_' + index,
                        filename: file.name,
                        fileType: file.type,
                        dataUrl: e.target.result
                    };
                    
                    referenceAttachments.push(attachmentData);
                    
                    const attachmentItem = document.createElement('div');
                    attachmentItem.className = 'attachment-item';
                    attachmentItem.innerHTML = `
                        <div class="attachment-icon">
                            <i class="${getFileIcon(file.type)}"></i>
                        </div>
                        <div class="attachment-info">
                            <div class="attachment-name">
                                ${file.name}
                                <span class="badge bg-secondary file-type-badge">${getFileTypeText(file.type)}</span>
                            </div>
                        </div>
                        <button type="button" class="remove-attachment-btn" onclick="removeAIReferenceAttachment('${attachmentData.id}')">
                            <i class="fas fa-times"></i>
                        </button>
                    `;
                    
                    attachmentsContainer.appendChild(attachmentItem);
                };
                reader.readAsDataURL(file);
            });
            
            // 重置文件输入
            this.value = '';
        });
    }
}

// 移除AI参考图片
function removeAIReferenceImage(imageId) {
    referenceImages = referenceImages.filter(img => img.id !== imageId);
    const imageItems = document.querySelectorAll('#image-previews .image-preview-item');
    imageItems.forEach(item => {
        const button = item.querySelector('.remove-image-btn');
        if (button && button.onclick && button.onclick.toString().includes(imageId)) {
            item.remove();
        }
    });
}

// 移除AI参考附件
function removeAIReferenceAttachment(attachmentId) {
    referenceAttachments = referenceAttachments.filter(att => att.id !== attachmentId);
    const attachmentItems = document.querySelectorAll('#attachments-container .attachment-item');
    attachmentItems.forEach(item => {
        const button = item.querySelector('.remove-attachment-btn');
        if (button && button.onclick && button.onclick.toString().includes(attachmentId)) {
            item.remove();
        }
    });
}

// AI生成评测数据
async function generateTestData(questionIndex) {
    const questionContent = document.querySelector(`#question-${questionIndex} .question-content`).value;
    const answerContent = document.querySelector(`#question-${questionIndex} .question-answer`).value;
    
    if (!questionContent) {
        alert('问题内容不能为空');
        return;
    }
    
    try {
        const result = await apiCall('/api/ai/generate-test-data', {
            method: 'POST',
            body: JSON.stringify({
                question_content: questionContent,
                answer_content: answerContent
            })
        });
        
        if (result.success) {
            const testData = result.test_data;
            const editor = document.querySelector(`#question-${questionIndex} .question-test-data`);
            
            // 将评测数据格式化为JSON字符串显示在编辑器中
            editor.value = JSON.stringify(testData, null, 2);
            
            alert(`评测数据生成成功！共生成 ${testData.length} 个测试用例`);
        } else {
            throw new Error(result.message);
        }
        
    } catch (error) {
        console.error('生成评测数据失败:', error);
        alert('生成评测数据失败: ' + error.message);
    }
}

// 显示AI分析结果预览
function showAIResultPreview(assignmentData) {
    const previewContainer = document.getElementById('ai-result-preview');
    const previewContent = document.getElementById('ai-preview-content');
    
    // 生成预览内容
    let previewHTML = `
        <div class="mb-3">
            <strong>作业标题:</strong> ${assignmentData.title || '未识别'}
        </div>
    `;
    
    if (assignmentData.description) {
        previewHTML += `
            <div class="mb-3">
                <strong>作业描述:</strong> <span class="preserve-linebreaks">${assignmentData.description}</span>
            </div>
        `;
    }
    
    previewHTML += `
        <div class="mb-3">
            <strong>识别到的问题:</strong> ${assignmentData.questions ? assignmentData.questions.length : 0} 个
        </div>
    `;
    
    if (assignmentData.questions && assignmentData.questions.length > 0) {
        previewHTML += '<div class="mt-3"><strong>问题预览:</strong><ul class="mt-2">';
        assignmentData.questions.forEach((question, index) => {
            previewHTML += `
                <li>
                    <strong>问题 ${index + 1}:</strong> <span class="preserve-linebreaks">${question.question.substring(0, 50)}...</span>
                    <br><small>类型: ${question.type} | 分值: ${question.score || 10}</small>
                </li>
            `;
        });
        previewHTML += '</ul></div>';
    }
    
    previewContent.innerHTML = previewHTML;
    previewContainer.classList.remove('hidden');
    
    // 存储AI分析结果
    currentAIAssignment = assignmentData;
}

// 应用AI分析结果并跳转到编辑页面
function applyAIResult() {
    if (!currentAIAssignment) return;
    
    // 应用AI生成的作业数据到手动编辑页面
    applyAIGeneratedAssignment(currentAIAssignment);
    
    // 切换到手动编辑选项卡
    const manualTab = new bootstrap.Tab(document.getElementById('manual-tab'));
    manualTab.show();
    
    // 显示成功消息
    alert('AI作业生成成功！请检查生成的内容并进行必要的调整。');
    
    // 隐藏AI结果预览
    document.getElementById('ai-result-preview').classList.add('hidden');
    document.getElementById('ai-import-section').classList.remove('hidden');
}

// 放弃AI分析结果
function discardAIResult() {
    document.getElementById('ai-result-preview').classList.add('hidden');
    document.getElementById('ai-import-section').classList.remove('hidden');
    currentAIAssignment = null;
}

// 应用AI生成的作业数据
function applyAIGeneratedAssignment(assignmentData) {
    if (!assignmentData) return;
    
    // 填充作业基本信息
    if (assignmentData.title) {
        document.getElementById('assignment-title').value = assignmentData.title;
    }
    
    if (assignmentData.description) {
        document.getElementById('assignment-description').value = assignmentData.description;
    }
    
    if (assignmentData.assignmentGradingPrompt) {
        document.getElementById('assignment-grading-prompt').value = assignmentData.assignmentGradingPrompt;
    }
    
    // 清空现有问题
    const container = document.getElementById('questions-container');
    container.innerHTML = '';
    questionCounter = 0;
    
    // 添加AI生成的问题
    if (assignmentData.questions && assignmentData.questions.length > 0) {
        assignmentData.questions.forEach(question => {
            addQuestionFromData(question);
        });
    }
    
    // 更新问题导航
    updateQuestionsNavigation();
}

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', initializePage);