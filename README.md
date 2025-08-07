# 领导工作流程管理系统

一个基于Python Flask的领导工作流程管理系统，采用iOS 16风格设计，支持职员和领导两种角色，提供日历式任务管理和工作流程跟踪功能。

## 功能特性

### 🎯 核心功能
- **用户角色管理**: 支持职员和领导两种角色
- **日历视图**: 直观的日历式任务展示和管理
- **任务管理**: 完整的任务增删改查功能
- **权限控制**: 基于角色的数据访问控制
- **响应式设计**: 支持桌面和移动设备

### 👥 角色功能

#### 职员功能
- 查看和管理个人任务
- 日历式任务展示
- 任务状态更新
- 任务优先级设置

#### 领导功能
- 查看所有职员的任务
- 用户管理
- 任务分配和监控
- 工作流程统计

### 🎨 设计特色
- **iOS 16风格**: 现代化的毛玻璃效果和圆角设计
- **渐变背景**: 美观的渐变色彩搭配
- **动画效果**: 流畅的交互动画
- **响应式布局**: 适配各种屏幕尺寸

## 技术栈

### 后端
- **Python 3.8+**
- **Flask**: Web框架
- **Flask-SQLAlchemy**: ORM数据库操作
- **Flask-Login**: 用户认证
- **SQLite**: 数据库

### 前端
- **HTML5 + CSS3**: 现代化布局和样式
- **JavaScript (ES6+)**: 交互逻辑
- **iOS 16设计语言**: 毛玻璃效果、圆角、渐变

## 安装和运行

### 1. 环境要求
- Python 3.8 或更高版本
- pip 包管理器

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 运行应用
```bash
python app.py
```

### 4. 访问系统
打开浏览器访问: `http://localhost:5000`

## 默认账户

系统会自动创建默认管理员账户：
- **用户名**: admin
- **密码**: admin123
- **角色**: 领导

## 使用指南

### 首次使用
1. 访问系统首页
2. 使用默认管理员账户登录
3. 创建职员账户
4. 开始使用系统

### 职员操作
1. **登录系统**: 使用分配的账户登录
2. **查看日历**: 在日历视图中查看任务安排
3. **添加任务**: 点击"添加任务"按钮创建新任务
4. **编辑任务**: 点击任务进行编辑或状态更新
5. **删除任务**: 删除不需要的任务

### 领导操作
1. **登录系统**: 使用管理员账户登录
2. **查看所有任务**: 在日历和任务列表中查看所有职员的任务
3. **用户管理**: 在用户管理页面查看职员信息
4. **任务监控**: 实时监控任务完成情况

## 项目结构

```
Lider/
├── app.py                 # Flask主应用
├── requirements.txt       # Python依赖
├── README.md             # 项目说明
├── templates/            # HTML模板
│   ├── login.html        # 登录页面
│   ├── register.html     # 注册页面
│   └── dashboard.html    # 仪表板页面
└── static/              # 静态资源
    ├── css/
    │   └── style.css     # 样式文件
    └── js/
        └── dashboard.js  # JavaScript逻辑
```

## 数据库模型

### User (用户)
- id: 用户ID
- username: 用户名
- email: 邮箱
- password_hash: 密码哈希
- role: 角色 (employee/manager)
- name: 姓名
- created_at: 创建时间

### Task (任务)
- id: 任务ID
- title: 任务标题
- description: 任务描述
- date: 任务日期
- status: 任务状态 (pending/in_progress/completed)
- priority: 优先级 (low/medium/high)
- user_id: 所属用户ID
- created_at: 创建时间
- updated_at: 更新时间

## API接口

### 认证相关
- `POST /login`: 用户登录
- `POST /register`: 用户注册
- `GET /logout`: 用户退出

### 任务管理
- `GET /api/tasks`: 获取任务列表
- `POST /api/tasks`: 创建新任务
- `PUT /api/tasks/<id>`: 更新任务
- `DELETE /api/tasks/<id>`: 删除任务

### 用户管理
- `GET /api/users`: 获取用户列表（仅领导）

## 自定义和扩展

### 添加新功能
1. 在 `app.py` 中添加新的路由和逻辑
2. 在 `templates/` 中创建对应的HTML模板
3. 在 `static/css/style.css` 中添加样式
4. 在 `static/js/dashboard.js` 中添加交互逻辑

### 修改样式
- 编辑 `static/css/style.css` 文件
- 支持CSS变量自定义主题色彩
- 响应式断点可调整

### 数据库修改
- 修改模型定义后需要重新创建数据库
- 删除 `workflow.db` 文件重新运行应用

## 部署建议

### 生产环境
1. 使用 Gunicorn 或 uWSGI 作为WSGI服务器
2. 配置 Nginx 作为反向代理
3. 使用 PostgreSQL 或 MySQL 替代 SQLite
4. 配置 HTTPS 证书
5. 设置环境变量管理敏感信息

### 安全建议
1. 修改默认管理员密码
2. 使用强密码策略
3. 定期备份数据库
4. 配置防火墙规则
5. 启用日志记录

## 故障排除

### 常见问题
1. **端口被占用**: 修改 `app.py` 中的端口号
2. **数据库错误**: 删除 `workflow.db` 重新创建
3. **样式不加载**: 检查静态文件路径配置
4. **登录失败**: 确认用户名密码正确

### 日志查看
- 开发模式: 控制台输出
- 生产模式: 配置日志文件

## 贡献指南

欢迎提交 Issue 和 Pull Request 来改进这个项目。

## 许可证

MIT License

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 GitHub Issue
- 发送邮件至项目维护者

---

**注意**: 这是一个演示项目，生产环境使用前请进行充分的安全测试和配置优化。
