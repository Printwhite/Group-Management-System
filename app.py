from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import os
import json
import csv
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///workflow.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 用户模型
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='employee')  # 'employee' or 'manager'
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    tasks = db.relationship('Task', backref='user', lazy=True)

# 任务模型
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='in_progress')  # 只有进行中
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# 日志模型
class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    action = db.Column(db.String(100), nullable=False)  # 操作类型
    details = db.Column(db.Text)  # 操作详情
    ip_address = db.Column(db.String(45))  # IP地址
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='logs')

# 日志记录函数
def log_action(action, details=None):
    """记录用户操作日志"""
    try:
        if current_user.is_authenticated:
            log = Log(
                user_id=current_user.id,
                user_name=current_user.name,
                action=action,
                details=details,
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
    except Exception as e:
        print(f"日志记录失败: {e}")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # 检查是否有自动登录cookie
    auto_login_cookie = request.cookies.get('auto_login')
    if auto_login_cookie:
        try:
            auto_login_data = json.loads(auto_login_cookie)
            username = auto_login_data.get('username')
            timestamp_str = auto_login_data.get('timestamp')
            
            if username and timestamp_str:
                # 检查cookie是否在30天内
                timestamp = datetime.fromisoformat(timestamp_str)
                if datetime.utcnow() - timestamp < timedelta(days=30):
                    user = User.query.filter_by(username=username).first()
                    if user:
                        login_user(user, remember=True)
                        log_action('自动登录', f'用户 {username} 通过cookie自动登录')
                        return redirect(url_for('dashboard'))
        except (json.JSONDecodeError, ValueError):
            pass
    
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = request.form.get('remember_me') == 'on'
        
        if not username or not password:
            flash('请输入用户名和密码')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember_me)
            
            # 记录登录日志
            log_action('用户登录', f'用户 {username} 登录系统')
            
            # 如果选择了记住我，设置cookie
            if remember_me:
                response = make_response(redirect(url_for('dashboard')))
                auto_login_data = {
                    'username': username,
                    'timestamp': datetime.utcnow().isoformat()
                }
                response.set_cookie(
                    'auto_login',
                    json.dumps(auto_login_data),
                    max_age=30*24*60*60,  # 30天
                    httponly=True,
                    samesite='Lax'
                )
                return response
            
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        name = request.form.get('name')
        role = request.form.get('role', 'employee')
        
        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            flash('用户名已存在')
            return render_template('register.html')
        
        try:
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                name=name,
                role=role
            )
            db.session.add(user)
            db.session.commit()
            
            # 记录注册日志
            log_action('用户注册', f'新用户 {username} 注册系统')
            
            flash('注册成功，请登录')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('注册失败，请重试')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    # 记录登出日志
    log_action('用户登出', f'用户 {current_user.username} 登出系统')
    
    logout_user()
    response = make_response(redirect(url_for('login')))
    # 清除自动登录cookie
    response.delete_cookie('auto_login')
    return response

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/tasks', methods=['GET'])
@login_required
def get_tasks():
    if current_user.role == 'manager':
        # 领导可以看到所有任务
        tasks = Task.query.all()
    else:
        # 职员只能看到自己的任务
        tasks = Task.query.filter_by(user_id=current_user.id).all()
    
    task_list = []
    for task in tasks:
        task_list.append({
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'date': task.date.strftime('%Y-%m-%d'),
            'status': task.status,
            'priority': task.priority,
            'user_name': task.user.name,
            'user_id': task.user_id,
            'user_username': task.user.username  # 添加用户名用于标识
        })
    
    # 记录查看任务日志
    log_action('查看任务列表', f'用户查看了 {len(tasks)} 个任务')
    
    return jsonify(task_list)

@app.route('/api/tasks', methods=['POST'])
@login_required
def create_task():
    # 领导不能创建任务
    if current_user.role == 'manager':
        return jsonify({'error': '领导不能创建任务'}), 403
    
    data = request.get_json()
    task_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    today = datetime.now().date()
    
    # 检查日期限制：只能填写最近一天往前5天的工作内容
    if task_date > today or task_date < today - timedelta(days=5):
        return jsonify({'error': '只能填写最近一天往前5天的工作内容'}), 400
    
    task = Task(
        title=data['title'],
        description=data.get('description', ''),
        date=task_date,
        priority=data.get('priority', 'medium'),
        user_id=current_user.id
    )
    
    db.session.add(task)
    db.session.commit()
    
    # 记录创建任务日志
    log_action('创建任务', f'创建任务: {data["title"]} (日期: {data["date"]})')
    
    return jsonify({'message': '任务创建成功', 'id': task.id})

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    # 管理员不能编辑任务
    if current_user.role == 'manager':
        return jsonify({'error': '管理员只能查看任务，不能编辑'}), 403
    
    task = Task.query.get_or_404(task_id)
    
    # 检查权限：只有任务创建者可以编辑
    if task.user_id != current_user.id:
        return jsonify({'error': '无权限'}), 403
    
    data = request.get_json()
    task_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    today = datetime.now().date()
    
    # 检查日期限制：只能填写最近一天往前5天的工作内容
    if task_date > today or task_date < today - timedelta(days=5):
        return jsonify({'error': '只能填写最近一天往前5天的工作内容'}), 400
    
    old_title = task.title
    task.title = data.get('title', task.title)
    task.description = data.get('description', task.description)
    task.date = task_date
    task.status = data.get('status', task.status)
    task.priority = data.get('priority', task.priority)
    
    db.session.commit()
    
    # 记录更新任务日志
    log_action('更新任务', f'更新任务: {old_title} -> {task.title} (日期: {data["date"]})')
    
    return jsonify({'message': '任务更新成功'})

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    # 管理员不能删除任务
    if current_user.role == 'manager':
        return jsonify({'error': '管理员只能查看任务，不能删除'}), 403
    
    task = Task.query.get_or_404(task_id)
    
    # 检查权限：只有任务创建者可以删除
    if task.user_id != current_user.id:
        return jsonify({'error': '无权限'}), 403
    
    task_title = task.title
    db.session.delete(task)
    db.session.commit()
    
    # 记录删除任务日志
    log_action('删除任务', f'删除任务: {task_title}')
    
    return jsonify({'message': '任务删除成功'})

@app.route('/api/users')
@login_required
def get_users():
    if current_user.role != 'manager':
        return jsonify({'error': '无权限'}), 403
    
    users = User.query.filter_by(role='employee').all()
    user_list = []
    for user in users:
        user_list.append({
            'id': user.id,
            'name': user.name,
            'username': user.username
        })
    
    # 记录查看用户列表日志
    log_action('查看用户列表', f'查看了 {len(users)} 个用户')
    
    return jsonify(user_list)

@app.route('/api/logs')
@login_required
def get_logs():
    if current_user.role != 'manager':
        return jsonify({'error': '无权限'}), 403
    
    # 获取查询参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    user_id = request.args.get('user_id', type=int)
    action = request.args.get('action', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    # 构建查询
    query = Log.query
    
    if user_id:
        query = query.filter(Log.user_id == user_id)
    if action:
        query = query.filter(Log.action.contains(action))
    if start_date:
        query = query.filter(Log.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Log.created_at <= datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
    
    # 按时间倒序排列
    query = query.order_by(Log.created_at.desc())
    
    # 分页
    logs = query.paginate(page=page, per_page=per_page, error_out=False)
    
    log_list = []
    for log in logs.items:
        log_list.append({
            'id': log.id,
            'user_name': log.user_name,
            'action': log.action,
            'details': log.details,
            'ip_address': log.ip_address,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify({
        'logs': log_list,
        'total': logs.total,
        'pages': logs.pages,
        'current_page': page
    })

@app.route('/api/export-csv')
@login_required
def export_csv():
    if current_user.role != 'manager':
        return jsonify({'error': '无权限'}), 403
    
    # 获取查询参数
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # 查询任务
    query = Task.query.join(User)
    
    if start_date:
        query = query.filter(Task.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Task.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    
    tasks = query.all()
    
    # 创建CSV数据
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow(['员工姓名', '任务标题', '任务描述', '日期', '优先级', '状态', '创建时间'])
    
    # 写入数据
    for task in tasks:
        writer.writerow([
            task.user.name,
            task.title,
            task.description or '',
            task.date.strftime('%Y-%m-%d'),
            get_priority_text(task.priority),
            get_status_text(task.status),
            task.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    # 记录导出CSV日志
    log_action('导出CSV', f'导出了 {len(tasks)} 个任务数据')
    
    # 创建响应
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = f'attachment; filename=tasks_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response

def get_priority_text(priority):
    texts = {
        'high': '高',
        'medium': '中',
        'low': '低'
    }
    return texts.get(priority, priority)

def get_status_text(status):
    texts = {
        'in_progress': '进行中'
    }
    return texts.get(status, status)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # 创建默认管理员账户
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                name='系统管理员',
                role='manager'
            )
            db.session.add(admin)
            
            # 创建默认员工账户
            employee1 = User(
                username='zhang_san',
                password_hash=generate_password_hash('123456'),
                name='张三',
                role='employee'
            )
            db.session.add(employee1)
            
            employee2 = User(
                username='li_si',
                password_hash=generate_password_hash('123456'),
                name='李四',
                role='employee'
            )
            db.session.add(employee2)
            
            db.session.commit()
    
    app.run(debug=True, host='0.0.0.0', port=5000) 