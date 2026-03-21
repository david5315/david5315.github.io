# 课堂互动教学评测系统 - 项目运维文档

## 📋 项目概述

**项目名称**：课堂互动教学评测系统（快铸网站 AI 生成发布系统）  
**主要功能**：一句话生成互动网站，实现作业发布评测、实时教学评价  
**技术栈**：Flask + PyInstaller + HTML/JS  
**打包方式**：PyInstaller 单文件 EXE

---

## 📁 项目结构

```
test/
├── app.py                      # 主程序（Flask 应用 + GUI 启动界面）
├── app.spec                    # PyInstaller 打包配置
├── data_manager.py             # 数据管理模块（账号、学生、班级、共享数据）
├── teacher_apis.py             # 教师 API 蓝图（文件管理、教学业务）
├── student_apis.py             # 学生 API 蓝图
├── assignment.py               # 作业管理 API
├── ai_services.py              # AI 服务（提示词模板、AI 配置）
├── sms_service.py              # 短信验证码服务
├── statics/                    # 前端页面（HTML/CSS/JS）
│   ├── teacher.html            # 教师页面（文件管理、网站生成）
│   ├── student.html            # 学生页面
│   ├── login.html              # 登录页
│   ├── admin_management.html   # 管理员页面
│   └── ...
├── templates/                  # 教师网站模板目录
│   └── teach/                  # 教学模板
├── data/                       # 数据目录
│   ├── accounts.json           # 统一账号数据（教师、学生、班级）
│   ├── teachers.json           # 教师列表（兼容旧版）
│   └── shared/                 # 共享数据模板
│       ├── prompt_templates.json       # AI 提示词模板
│       ├── interactive_templates.json  # 交互网页模板
│       ├── assignment_templates.json   # 作业模板
│       └── page_templates.json         # 页面模板（新增）
├── uploads/                    # 上传文件存储
└── logs/                       # 日志文件
```

---

## 🔧 关键修复记录

### 2026-03-20 PyInstaller 打包问题修复

#### 问题 1：data/shared 模板文件未复制
**原因**：`data_manager.py` 模块导入时自动调用 `initialize_data()`，在 `initialize_folders()` 运行前就创建了空 JSON 文件。

**修复**：
- `data_manager.py`：移除文件末尾的自动初始化调用
- `app.py`：在 `initialize_system()` 中显式调用 `initialize_data()`
- `app.py`：增强 `initialize_folders()` 逻辑，空文件会被打包资源覆盖

#### 问题 2：teacher 页面文件上传失败
**原因**：`teacher_apis.py` 使用相对路径 `'templates'`，打包后工作目录不是 EXE 所在目录。

**修复**：
- `teacher_apis.py`：添加 `EXE_DIR` 检测逻辑
- `teacher_apis.py`：`safe_join_path()` 使用 `EXE_DIR` 拼接路径
- `teacher_apis.py`：`is_in_templates()` 使用 `EXE_DIR` 拼接路径

#### 问题 3：Windows 控制台编码问题
**现象**：emoji 字符导致 GBK 编码错误  
**状态**：未修复（不影响功能，仅控制台显示乱码）

---

## 🚀 打包流程

```powershell
# 1. 清理旧构建
Remove-Item "dist" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "build" -Recurse -Force -ErrorAction SilentlyContinue

# 2. 打包
python -m PyInstaller app.spec --clean

# 3. 测试
.\dist\app.exe
```

**打包配置**：`app.spec`
- 数据目录：`uploads`, `statics`, `data`, `templates`
- 输出：单文件 EXE（控制台模式）

---

## 📦 运行时行为

### 启动流程
1. `initialize_folders()` - 从打包资源恢复默认文件到 `dist/` 目录
2. `initialize_system()` - 加载账号数据和共享数据
3. 启动 Flask 服务器（Waitress，默认端口 80）
4. 显示 GUI 启动界面

### 关键路径
- **EXE 目录**：`sys.executable` 所在目录（打包后）或 `__file__` 所在目录（开发环境）
- **templates 目录**：`EXE_DIR/templates` - 教师网站存放位置
- **data 目录**：`EXE_DIR/data` - 账号数据和共享模板
- **uploads 目录**：`EXE_DIR/uploads` - 用户上传文件

### 数据初始化
- **accounts.json**：首次运行自动创建，包含默认教师账号 `teach/123456`
- **shared/*.json**：从打包资源复制 4 个模板文件
- **教师目录**：`templates/teacher_{username}/` - 按教师隔离数据

---

## 👥 默认账号

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| teach | 123456 | teacher | 默认教师账号 |
| admin | - | admin | 管理员（需手动创建） |

---

## 🌐 系统版本模式

通过 `ai_config.json` 的 `site_setup.quickforge_version` 控制：

| 版本 | 功能 | 允许角色 |
|------|------|----------|
| `basic` | 基础版，public 目录发布网站 | 游客、teacher |
| `personal` | 个人版，管理私有学生 | teacher |
| `school` | 校园版，管理全校教师学生 | school、admin |
| `quickforge` | 官网版 | admin |

**登录时自动切换**：
- school 角色 → `school` 模式
- teacher 角色 → `personal` 模式
- admin 角色 → 保持当前版本

---

## 📝 API 蓝图

### teacher_apis.py (`/api`)
- `/teacher/files` - 文件浏览、新建文件夹、删除
- `/teacher/upload` - 文件上传
- `/teacher/website` - AI 生成网站
- `/page-templates` - 页面模板管理

### student_apis.py (`/api`)
- 学生登录、作业提交

### assignment.py (`/api`)
- 作业管理、评测

### ai_services.py (`/api`)
- AI 配置、提示词模板

---

## 🔐 认证与权限

### 登录类型
1. **Web 登录**：教师/管理员，带验证码
2. **私有学生登录**：学号 + 密码
3. **游客登录**：免登录访问公开任务

### 权限控制
- **admin**：管理所有教师、学生、班级，创建/删除账号
- **teacher**：管理个人目录、私有学生
- **school**：管理全校资源
- **private-student**：仅访问授权任务

---

## 🛠️ 常见问题

### Q: 打包后运行提示找不到 templates 目录？
**A**：检查 `teacher_apis.py`、`data_manager.py`、`app.py` 是否都使用 `EXE_DIR` 拼接路径。

### Q: 上传文件失败？
**A**：确保 `safe_join_path()` 使用 `EXE_DIR`，目标目录权限正确。

### Q: 共享模板文件是空的？
**A**：检查 `initialize_folders()` 是否在 `load_shared_data_to_memory()` 之前调用。

### Q: 控制台显示乱码？
**A**：Windows GBK 编码不支持 emoji，不影响功能。可添加 UTF-8 编码强制转换：
```python
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
```

---

## 📊 数据库结构

### accounts.json
```json
{
  "teachers": [
    {
      "username": "teach",
      "password": "123456",
      "name": "教师",
      "role": "teacher",
      "phone": "",
      "subject": "语文",
      "expiry_date": "",
      "remaining_uses": 0,
      "user_key": ""
    }
  ],
  "students": [],
  "classes": []
}
```

### shared/prompt_templates.json
AI 提示词模板数组，包含：
- `id`: 模板标识
- `name`: 模板名称
- `content`: 提示词内容
- `subject`: 适用学科
- `difficulty`: 难度等级

---

## 🔑 配置文件

### ai_config.json
```json
{
  "text_model": {
    "model": "qwen-plus",
    "available_models": ["qwen-plus", "qwen-turbo"]
  },
  "site_setup": {
    "quickforge_version": "basic",
    "quickforge_URL": ""
  },
  "remote_key": "",
  "temp_key": "",
  "temp_key_expiry": ""
}
```

---

## 📈 性能优化建议

1. **自动保存**：每 60 秒检查一次内存数据变化
2. **短信清理**：每 5 分钟清理过期验证码
3. **日志轮转**：按天分割日志文件
4. **文件上传**：支持多文件批量上传

---

## 🧪 测试检查清单

打包后运行测试：
- [ ] 默认账号登录（teach/123456）
- [ ] 新建文件夹
- [ ] 上传文件（图片、文档）
- [ ] AI 生成网站（需配置 API Key）
- [ ] 学生账号管理
- [ ] 班级管理
- [ ] 公开任务发布

---

## 📞 技术支持

- **开发团队**：快铸 AI 课题组
- **联系方式**：13815120911（微信同号）
- **官网**：www.quickforge.cn
- **开源地址**：https://gitee.com/xmicai/aiedtech/

---

*最后更新：2026-03-20*
