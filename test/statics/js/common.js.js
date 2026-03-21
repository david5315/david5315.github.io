// common.js - 课堂互动教学评测系统公共函数库
// 创建日期: 2024年1月

// API基础URL
const API_BASE = window.location.origin;

// ==================== API调用函数 ====================

/**
 * 统一的API调用函数
 */
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            credentials: 'include',
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

// ==================== 文件类型工具函数 ====================

/**
 * 根据文件类型获取对应的FontAwesome图标
 */
function getFileIcon(fileType) {
    if (!fileType) return 'fas fa-file';
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

/**
 * 根据文件类型获取对应的中文类型文本
 */
function getFileTypeText(fileType) {
    if (!fileType) return '文件';
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

/**
 * 格式化文件大小
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// ==================== 图片上传功能 ====================

/**
 * 上传问题图片到服务器
 */
async function uploadQuestionImage(file, questionIndex, assignmentId = null) {
    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('questionIndex', questionIndex);
        
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

/**
 * 移除图片预览（统一版本，接受一个参数）
 */
function removeImagePreview(button) {
    const imageItem = button.closest('.image-preview-item');
    if (imageItem) {
        imageItem.remove();
    }
}

// ==================== 图片查看功能 ====================

/**
 * 初始化图片查看模态框
 */
function initImageModal() {
    const modal = document.getElementById('imageModal');
    if (!modal) return;
    
    const modalImg = document.getElementById('modalImage');
    const closeBtn = document.getElementsByClassName('close-image-modal')[0];
    
    if (closeBtn) {
        closeBtn.onclick = function() {
            modal.style.display = 'none';
        }
    }
    
    modal.onclick = function(event) {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    }
    
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            modal.style.display = 'none';
        }
    });
}

/**
 * 显示图片在模态框中
 */
function showImage(src) {
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImage');
    
    if (modal && modalImg) {
        modal.style.display = 'block';
        modalImg.src = src;
    }
}

// ==================== 评测数据管理 ====================

/**
 * 处理评测数据文件选择
 */
function handleTestDataFilesChange(questionIndex, event) {
    const files = event.target.files;
    const fileNamesContainer = document.getElementById(`test-data-file-names-${questionIndex}`);
    
    if (!fileNamesContainer) return;
    
    if (files.length === 0) {
        fileNamesContainer.style.display = 'none';
        fileNamesContainer.innerHTML = '';
        return;
    }
    
    fileNamesContainer.style.display = 'block';
    const fileNames = Array.from(files).map(file => file.name).join(', ');
    fileNamesContainer.innerHTML = `<strong>已选择文件:</strong> ${fileNames}`;
}

/**
 * 上传并解析评测数据
 */
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
            
            if (editor) {
                editor.value = JSON.stringify(testDataArray, null, 2);
                alert('评测数据解析成功！');
            }
        } else {
            throw new Error(result.message);
        }
        
    } catch (error) {
        alert('处理评测数据失败: ' + error.message);
    }
}

/**
 * AI生成评测数据
 */
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
            
            if (editor) {
                editor.value = JSON.stringify(testData, null, 2);
                alert(`评测数据生成成功！共生成 ${testData.length} 个测试用例`);
            }
        } else {
            throw new Error(result.message);
        }
        
    } catch (error) {
        console.error('生成评测数据失败:', error);
        alert('生成评测数据失败: ' + error.message);
    }
}

// ==================== 填空题答案管理 ====================

/**
 * 添加填空题答案输入项
 */
function addFillBlankAnswer(questionIndex, value = '') {
    const container = document.getElementById(`fill-blank-answers-${questionIndex}`);
    if (!container) return;
    
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

/**
 * 初始化填空题答案
 */
function initFillBlankAnswers(questionIndex, answers = []) {
    const container = document.getElementById(`fill-blank-answers-${questionIndex}`);
    if (!container) return;
    
    container.innerHTML = '';
    if (answers.length === 0) {
        addFillBlankAnswer(questionIndex);
    } else {
        answers.forEach(answer => {
            addFillBlankAnswer(questionIndex, answer);
        });
    }
}

/**
 * 获取填空题所有答案
 */
function getFillBlankAnswers(questionIndex) {
    const container = document.getElementById(`fill-blank-answers-${questionIndex}`);
    if (!container) return [];
    
    const answers = [];
    container.querySelectorAll('.fill-blank-answer').forEach(input => {
        if (input.value.trim() !== '') {
            answers.push(input.value.trim());
        }
    });
    return answers;
}

// ==================== 选择题功能 ====================

/**
 * 获取选择题数据
 */
function getChoiceQuestionData(questionIndex) {
    const container = document.getElementById(`options-container-${questionIndex}`);
    if (!container) return { options: [], answers: [] };
    
    const options = [];
    const answers = [];
    
    container.querySelectorAll('.option-item-editable').forEach((optionDiv, index) => {
        const input = optionDiv.querySelector('.option-input');
        const checkbox = optionDiv.querySelector('.option-checkbox');
        const letter = String.fromCharCode(65 + index);
        
        if (input && input.value.trim()) {
            options.push(input.value.trim());
            if (checkbox && checkbox.checked) {
                answers.push(letter);
            }
        }
    });
    
    return {
        options: options,
        answers: answers
    };
}

/**
 * 重新排列选项字母
 */
function renumberOptions(questionIndex) {
    const container = document.getElementById(`options-container-${questionIndex}`);
    if (!container) return;
    
    const options = container.querySelectorAll('.option-item-editable');
    
    options.forEach((optionDiv, index) => {
        const letter = String.fromCharCode(65 + index);
        const letterDiv = optionDiv.querySelector('.option-letter');
        const checkbox = optionDiv.querySelector('.option-checkbox');
        
        if (letterDiv) {
            letterDiv.textContent = letter;
        }
        if (checkbox) {
            checkbox.value = letter;
        }
    });
}

// ==================== 公共工具函数 ====================

/**
 * 显示状态消息
 */
function showStatus(message, type = 'info') {
    // 这个函数在两个文件中都有，但实现略有不同
    // 如果需要统一，可以在这里实现通用版本
}

/**
 * 防抖函数
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 节流函数
 */
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// ==================== 全局对象导出 ====================

// 将公共函数暴露给全局作用域
window.CommonUtils = {
    apiCall,
    getFileIcon,
    getFileTypeText,
    formatFileSize,
    uploadQuestionImage,
    removeImagePreview,
    initImageModal,
    showImage,
    handleTestDataFilesChange,
    uploadTestDataFiles,
    generateTestData,
    addFillBlankAnswer,
    getFillBlankAnswers,
    getChoiceQuestionData,
    renumberOptions,
    debounce,
    throttle
};

// 兼容旧版本调用方式
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.CommonUtils;
}