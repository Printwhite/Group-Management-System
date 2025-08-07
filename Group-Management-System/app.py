from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import os
import json
import csv
import io
import random
import hashlib
import secrets
import re
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)  # 使用随机生成的密钥
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///workflow.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 安全配置
app.config['SESSION_COOKIE_SECURE'] = False  # 开发环境设为False，生产环境设为True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# 自动登录和安全配置
app.config['AUTO_LOGIN_ENABLED'] = True  # 启用自动登录
app.config['TRUSTED_IPS'] = ['127.0.0.1', '::1', 'localhost']  # 受信任的IP地址
app.config['MAX_LOGIN_ATTEMPTS'] = 5  # 最大登录尝试次数
app.config['LOCKOUT_DURATION'] = 30  # 锁定时间（分钟）
app.config['RATE_LIMIT_WINDOW'] = 300  # 速率限制窗口（秒）
app.config['MAX_REQUESTS_PER_WINDOW'] = 100  # 每个窗口最大请求数

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 用户模型（简化版）
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='employee')  # 'employee' or 'manager'
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True)  # 邮箱
    phone = db.Column(db.String(20))  # 手机号
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)  # 最后登录时间
    is_active = db.Column(db.Boolean, default=True)  # 账户状态
    login_attempts = db.Column(db.Integer, default=0)  # 登录尝试次数
    locked_until = db.Column(db.DateTime)  # 账户锁定时间
    
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
    user_agent = db.Column(db.String(500))  # 用户代理
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='logs')

# 设备信任模型
class TrustedDevice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    device_hash = db.Column(db.String(64), nullable=False)  # 设备指纹哈希
    ip_address = db.Column(db.String(45), nullable=False)  # IP地址
    user_agent = db.Column(db.String(500))  # 用户代理
    last_used = db.Column(db.DateTime, default=datetime.utcnow)  # 最后使用时间
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    is_active = db.Column(db.Boolean, default=True)  # 是否激活
    
    user = db.relationship('User', backref='trusted_devices')

# 安全事件模型
class SecurityEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False)  # IP地址
    event_type = db.Column(db.String(50), nullable=False)  # 事件类型
    event_details = db.Column(db.Text)  # 事件详情
    user_agent = db.Column(db.String(500))  # 用户代理
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    is_blocked = db.Column(db.Boolean, default=False)  # 是否被阻止

# 安全工具函数
def sanitize_input(text):
    """清理用户输入，防止XSS攻击"""
    if not text:
        return ""
    # 移除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    # 移除危险字符
    text = text.replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#x27;')
    return text.strip()

def validate_email(email):
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """验证手机号格式"""
    pattern = r'^1[3-9]\d{9}$'
    return re.match(pattern, phone) is not None

def rate_limit_check(user_id):
    """检查登录频率限制"""
    user = User.query.get(user_id)
    if not user:
        return False
    
    # 如果账户被锁定
    if user.locked_until and user.locked_until > datetime.utcnow():
        return False
    
    # 如果登录尝试次数过多，锁定账户
    if user.login_attempts >= 5:
        user.locked_until = datetime.utcnow() + timedelta(minutes=30)
        db.session.commit()
        return False
    
    return True

def log_action(action, details=None, ip_address=None):
    """记录用户操作日志"""
    try:
        user_agent = request.headers.get('User-Agent', '')
        log = Log(
            user_id=current_user.id if current_user.is_authenticated else None,
            user_name=current_user.name if current_user.is_authenticated else 'Anonymous',
            action=action,
            details=sanitize_input(details) if details else None,
            ip_address=ip_address or request.remote_addr,
            user_agent=user_agent[:500]  # 限制长度
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"日志记录失败: {e}")

def generate_device_hash(ip_address, user_agent):
    """生成设备指纹哈希"""
    device_string = f"{ip_address}:{user_agent}"
    return hashlib.sha256(device_string.encode()).hexdigest()

def is_trusted_ip(ip_address):
    """检查是否为受信任的IP地址"""
    return ip_address in app.config['TRUSTED_IPS']

def is_device_trusted(user_id, device_hash, ip_address):
    """检查设备是否受信任"""
    trusted_device = TrustedDevice.query.filter_by(
        user_id=user_id,
        device_hash=device_hash,
        ip_address=ip_address,
        is_active=True
    ).first()
    
    if trusted_device:
        # 更新最后使用时间
        trusted_device.last_used = datetime.utcnow()
        db.session.commit()
        return True
    return False

def add_trusted_device(user_id, ip_address, user_agent):
    """添加受信任设备"""
    device_hash = generate_device_hash(ip_address, user_agent)
    
    # 检查是否已存在
    existing_device = TrustedDevice.query.filter_by(
        user_id=user_id,
        device_hash=device_hash,
        ip_address=ip_address
    ).first()
    
    if not existing_device:
        trusted_device = TrustedDevice(
            user_id=user_id,
            device_hash=device_hash,
            ip_address=ip_address,
            user_agent=user_agent[:500]
        )
        db.session.add(trusted_device)
        db.session.commit()

def log_security_event(event_type, event_details, ip_address=None, user_agent=None):
    """记录安全事件"""
    try:
        security_event = SecurityEvent(
            event_type=event_type,
            event_details=sanitize_input(event_details),
            ip_address=ip_address or request.remote_addr,
            user_agent=user_agent or request.headers.get('User-Agent', '')[:500]
        )
        db.session.add(security_event)
        db.session.commit()
    except Exception as e:
        print(f"安全事件记录失败: {e}")

def check_rate_limit(ip_address):
    """检查速率限制"""
    window_start = datetime.utcnow() - timedelta(seconds=app.config['RATE_LIMIT_WINDOW'])
    
    # 统计最近时间窗口内的请求数
    recent_events = SecurityEvent.query.filter(
        SecurityEvent.ip_address == ip_address,
        SecurityEvent.created_at >= window_start
    ).count()
    
    if recent_events >= app.config['MAX_REQUESTS_PER_WINDOW']:
        log_security_event('RATE_LIMIT_EXCEEDED', f'IP {ip_address} 请求频率过高', ip_address)
        return False
    
    return True

def check_ip_blocked(ip_address):
    """检查IP是否被阻止"""
    # 检查是否有恶意事件
    malicious_events = SecurityEvent.query.filter(
        SecurityEvent.ip_address == ip_address,
        SecurityEvent.is_blocked == True
    ).count()
    
    return malicious_events > 0

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 安全中间件
@app.before_request
def security_middleware():
    """安全中间件，在每个请求前执行安全检查"""
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')
    
    # 跳过静态文件的安全检查
    if request.path.startswith('/static/'):
        return
    
    # 检查IP是否被阻止
    if check_ip_blocked(ip_address):
        log_security_event('BLOCKED_IP_REQUEST', f'被阻止的IP尝试访问: {request.path}', ip_address, user_agent)
        return jsonify({'error': '访问被拒绝'}), 403
    
    # 检查速率限制（对非登录页面）
    if not request.path.startswith('/login') and not request.path.startswith('/register'):
        if not check_rate_limit(ip_address):
            log_security_event('RATE_LIMIT_EXCEEDED', f'IP {ip_address} 请求频率过高', ip_address, user_agent)
            return jsonify({'error': '请求过于频繁，请稍后再试'}), 429
    
    # 记录可疑活动
    suspicious_patterns = [
        'sqlmap', 'nikto', 'nmap', 'dirb', 'gobuster', 'wfuzz',  # 安全扫描工具
        'union select', 'drop table', 'insert into', 'delete from',  # SQL注入
        '<script', 'javascript:', 'onload=', 'onerror=',  # XSS攻击
        '../', '..\\', 'etc/passwd', 'windows/system32'  # 路径遍历
    ]
    
    request_string = f"{request.method} {request.path} {request.query_string.decode()} {request.get_data().decode()}"
    request_string_lower = request_string.lower()
    
    for pattern in suspicious_patterns:
        if pattern in request_string_lower:
            log_security_event('SUSPICIOUS_ACTIVITY', f'检测到可疑活动: {pattern}', ip_address, user_agent)
            break

@app.route('/')
def index():
    # 如果用户已登录，直接跳转到仪表板
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # 检查是否有自动登录cookie
    auto_login_cookie = request.cookies.get('auto_login')
    if auto_login_cookie:
        try:
            auto_login_data = json.loads(auto_login_cookie)
            username = auto_login_data.get('username')
            timestamp_str = auto_login_data.get('timestamp')
            token = auto_login_data.get('token')  # 新增安全令牌
            
            if username and timestamp_str and token:
                # 检查cookie是否在30天内
                timestamp = datetime.fromisoformat(timestamp_str)
                if datetime.utcnow() - timestamp < timedelta(days=30):
                    user = User.query.filter_by(username=username).first()
                    if user:
                        # 验证安全令牌（简单的哈希验证）
                        expected_token = hashlib.sha256(f"{username}{timestamp_str}{user.password_hash[:10]}".encode()).hexdigest()
                        if token == expected_token:
                            login_user(user, remember=True)
                            log_action('自动登录', f'用户 {username} 通过安全cookie自动登录', request.remote_addr)
                            return redirect(url_for('dashboard'))
                        else:
                            # 令牌无效，清除cookie
                            response = make_response(redirect(url_for('login')))
                            response.delete_cookie('auto_login')
                            return response
        except (json.JSONDecodeError, ValueError, KeyError):
            # 清除无效的cookie
            response = make_response(redirect(url_for('login')))
            response.delete_cookie('auto_login')
            return response
    
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # 安全检查
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')
    
    # 检查IP是否被阻止
    if check_ip_blocked(ip_address):
        log_security_event('BLOCKED_IP_ACCESS', f'被阻止的IP尝试访问: {ip_address}', ip_address, user_agent)
        flash('访问被拒绝，请联系管理员')
        return render_template('login.html'), 403
    
    # 检查速率限制
    if not check_rate_limit(ip_address):
        flash('请求过于频繁，请稍后再试')
        return render_template('login.html'), 429
    
    # 如果用户已登录，直接跳转到仪表板
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # 检查自动登录
    if app.config['AUTO_LOGIN_ENABLED']:
        # 检查设备信任
        device_hash = generate_device_hash(ip_address, user_agent)
        auto_login_cookie = request.cookies.get('auto_login')
        
        if auto_login_cookie:
            try:
                auto_login_data = json.loads(auto_login_cookie)
                username = auto_login_data.get('username')
                timestamp_str = auto_login_data.get('timestamp')
                token = auto_login_data.get('token')
                
                if username and timestamp_str and token:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    if datetime.utcnow() - timestamp < timedelta(days=30):
                        user = User.query.filter_by(username=username).first()
                        if user:
                            expected_token = hashlib.sha256(f"{username}{timestamp_str}{user.password_hash[:10]}".encode()).hexdigest()
                            if token == expected_token:
                                # 检查设备是否受信任
                                if is_device_trusted(user.id, device_hash, ip_address) or is_trusted_ip(ip_address):
                                    login_user(user, remember=True)
                                    user.last_login = datetime.utcnow()
                                    db.session.commit()
                                    log_action('自动登录', f'用户 {username} 通过受信任设备自动登录', ip_address)
                                    return redirect(url_for('dashboard'))
            except (json.JSONDecodeError, ValueError, KeyError):
                pass
    
    if request.method == 'POST':
        username = sanitize_input(request.form.get('username'))
        password = request.form.get('password')
        remember_me = request.form.get('remember_me') == 'on'
        trust_device = request.form.get('trust_device') == 'on'  # 新增：信任设备选项
        
        if not username or not password:
            flash('请输入用户名和密码')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            # 检查用户状态
            if hasattr(user, 'is_active') and not user.is_active:
                flash('账户已被禁用，请联系管理员')
                return render_template('login.html')
            
            # 检查登录频率限制
            if not rate_limit_check(user.id):
                flash('登录尝试次数过多，账户已锁定')
                return render_template('login.html')
            
            # 验证通过，执行登录
            login_user(user, remember=remember_me)
            
            # 更新最后登录时间
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # 记录登录日志
            log_action('用户登录', f'用户 {username} 登录系统', ip_address)
            
            # 如果选择了信任设备，添加设备到受信任列表
            if trust_device:
                add_trusted_device(user.id, ip_address, user_agent)
                log_action('添加受信任设备', f'用户 {username} 添加了受信任设备', ip_address)
            
            # 如果选择了记住我，设置安全cookie
            if remember_me:
                response = make_response(redirect(url_for('dashboard')))
                timestamp = datetime.utcnow().isoformat()
                auto_login_data = {
                    'username': username,
                    'timestamp': timestamp,
                    'token': hashlib.sha256(f"{username}{timestamp}{user.password_hash[:10]}".encode()).hexdigest()
                }
                response.set_cookie(
                    'auto_login',
                    json.dumps(auto_login_data),
                    max_age=30*24*60*60,  # 30天
                    httponly=True,
                    secure=False,  # 在生产环境中设置为True（HTTPS）
                    samesite='Lax'
                )
                return response
            
            return redirect(url_for('dashboard'))
        else:
            # 记录失败的登录尝试
            if user:  # 只有当用户存在时才记录登录尝试次数
                user.login_attempts += 1
                db.session.commit()
            
            # 记录安全事件
            log_security_event('LOGIN_FAILED', f'用户 {username} 登录失败', ip_address, user_agent)
            log_action('登录失败', f'用户 {username} 登录失败', ip_address)
            flash('用户名或密码错误')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = sanitize_input(request.form.get('username'))
        password = request.form.get('password')
        name = sanitize_input(request.form.get('name'))
        role = request.form.get('role', 'employee')
        email = sanitize_input(request.form.get('email'))
        phone = sanitize_input(request.form.get('phone'))
        
        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            flash('用户名已存在')
            return render_template('register.html')
        
        # 验证邮箱格式
        if email and not validate_email(email):
            flash('邮箱格式不正确')
            return render_template('register.html')
        
        # 检查邮箱是否已存在
        if email and User.query.filter_by(email=email).first():
            flash('邮箱已被使用')
            return render_template('register.html')
        
        # 验证手机号格式
        if phone and not validate_phone(phone):
            flash('手机号格式不正确')
            return render_template('register.html')
        
        try:
            # 创建用户
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                name=name,
                role=role,
                email=email,
                phone=phone
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

@app.route('/api/check-login-status')
def check_login_status():
    """检查用户登录状态，用于前端自动登录检测"""
    if current_user.is_authenticated:
        return jsonify({
            'logged_in': True,
            'user': {
                'username': current_user.username,
                'name': current_user.name,
                'role': current_user.role
            }
        })
    
    # 检查是否有有效的自动登录cookie
    auto_login_cookie = request.cookies.get('auto_login')
    if auto_login_cookie:
        try:
            auto_login_data = json.loads(auto_login_cookie)
            username = auto_login_data.get('username')
            timestamp_str = auto_login_data.get('timestamp')
            token = auto_login_data.get('token')
            
            if username and timestamp_str and token:
                timestamp = datetime.fromisoformat(timestamp_str)
                if datetime.utcnow() - timestamp < timedelta(days=30):
                    user = User.query.filter_by(username=username).first()
                    if user:
                        expected_token = hashlib.sha256(f"{username}{timestamp_str}{user.password_hash[:10]}".encode()).hexdigest()
                        if token == expected_token:
                            return jsonify({
                                'auto_login_available': True,
                                'username': username
                            })
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    
    return jsonify({
        'logged_in': False,
        'auto_login_available': False
    })

@app.route('/api/auto-login')
def auto_login():
    """执行自动登录"""
    auto_login_cookie = request.cookies.get('auto_login')
    if auto_login_cookie:
        try:
            auto_login_data = json.loads(auto_login_cookie)
            username = auto_login_data.get('username')
            timestamp_str = auto_login_data.get('timestamp')
            token = auto_login_data.get('token')
            
            if username and timestamp_str and token:
                timestamp = datetime.fromisoformat(timestamp_str)
                if datetime.utcnow() - timestamp < timedelta(days=30):
                    user = User.query.filter_by(username=username).first()
                    if user:
                        expected_token = hashlib.sha256(f"{username}{timestamp_str}{user.password_hash[:10]}".encode()).hexdigest()
                        if token == expected_token:
                            login_user(user, remember=True)
                            user.last_login = datetime.utcnow()
                            db.session.commit()
                            log_action('自动登录', f'用户 {username} 通过API自动登录', request.remote_addr)
                            return jsonify({'success': True, 'redirect': url_for('dashboard')})
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    
    return jsonify({'success': False, 'error': '自动登录失败'})

@app.route('/api/update-contact-info', methods=['POST'])
@login_required
def update_contact_info():
    """更新联系信息"""
    data = request.get_json()
    email = data.get('email')
    phone = data.get('phone')
    
    # 验证邮箱格式
    if email and not validate_email(email):
        return jsonify({'success': False, 'error': '邮箱格式不正确'})
    
    # 检查邮箱是否已被其他用户使用
    if email and email != current_user.email:
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'success': False, 'error': '该邮箱已被使用'})
    
    # 验证手机号格式
    if phone and not validate_phone(phone):
        return jsonify({'success': False, 'error': '手机号格式不正确'})
    
    # 检查手机号是否已被其他用户使用
    if phone and phone != current_user.phone:
        existing_user = User.query.filter_by(phone=phone).first()
        if existing_user:
            return jsonify({'success': False, 'error': '该手机号已被使用'})
    
    # 更新联系信息
    current_user.email = email
    current_user.phone = phone
    db.session.commit()
    
    log_action('更新联系信息', f'用户更新了联系信息')
    
    return jsonify({'success': True})

@app.route('/api/trusted-devices', methods=['GET'])
@login_required
def get_trusted_devices():
    """获取用户的受信任设备列表"""
    devices = TrustedDevice.query.filter_by(user_id=current_user.id, is_active=True).all()
    device_list = []
    
    for device in devices:
        device_list.append({
            'id': device.id,
            'ip_address': device.ip_address,
            'user_agent': device.user_agent,
            'last_used': device.last_used.strftime('%Y-%m-%d %H:%M:%S') if device.last_used else None,
            'created_at': device.created_at.strftime('%Y-%m-%d %H:%M:%S') if device.created_at else None
        })
    
    return jsonify(device_list)

@app.route('/api/trusted-devices/<int:device_id>', methods=['DELETE'])
@login_required
def remove_trusted_device(device_id):
    """移除受信任设备"""
    device = TrustedDevice.query.filter_by(
        id=device_id,
        user_id=current_user.id
    ).first()
    
    if not device:
        return jsonify({'success': False, 'error': '设备不存在'}), 404
    
    device.is_active = False
    db.session.commit()
    
    log_action('移除受信任设备', f'移除了设备: {device.ip_address}')
    
    return jsonify({'success': True})

@app.route('/api/security-events', methods=['GET'])
@login_required
def get_security_events():
    """获取安全事件（仅管理员）"""
    if current_user.role != 'manager':
        return jsonify({'error': '无权限'}), 403
    
    # 获取查询参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    event_type = request.args.get('event_type', '')
    ip_address = request.args.get('ip_address', '')
    
    # 构建查询
    query = SecurityEvent.query
    
    if event_type:
        query = query.filter(SecurityEvent.event_type.contains(event_type))
    if ip_address:
        query = query.filter(SecurityEvent.ip_address.contains(ip_address))
    
    # 按时间倒序排列
    query = query.order_by(SecurityEvent.created_at.desc())
    
    # 分页
    events = query.paginate(page=page, per_page=per_page, error_out=False)
    
    event_list = []
    for event in events.items:
        event_list.append({
            'id': event.id,
            'ip_address': event.ip_address,
            'event_type': event.event_type,
            'event_details': event.event_details,
            'user_agent': event.user_agent,
            'created_at': event.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'is_blocked': event.is_blocked
        })
    
    return jsonify({
        'events': event_list,
        'total': events.total,
        'pages': events.pages,
        'current_page': page
    })

@app.route('/api/block-ip/<ip_address>', methods=['POST'])
@login_required
def block_ip(ip_address):
    """阻止IP地址（仅管理员）"""
    if current_user.role != 'manager':
        return jsonify({'error': '无权限'}), 403
    
    # 标记该IP的所有安全事件为阻止状态
    SecurityEvent.query.filter_by(ip_address=ip_address).update({'is_blocked': True})
    db.session.commit()
    
    log_action('阻止IP', f'管理员阻止了IP: {ip_address}')
    
    return jsonify({'success': True})



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

@app.route('/security-settings')
@login_required
def security_settings():
    return render_template('security_settings.html')

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
        
        # 检查是否需要初始化数据
        if not User.query.filter_by(username='admin').first():
            print("初始化数据库...")
            
            # 创建管理员账户
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                name='系统管理员',
                role='manager'
            )
            db.session.add(admin)
            
            # 创建25个员工账户
            employees = []
            for i in range(1, 26):
                employee = User(
                    username=f'employee{i:02d}',
                    password_hash=generate_password_hash('123456'),
                    name=f'员工{i:02d}',
                    role='employee'
                )
                employees.append(employee)
                db.session.add(employee)
            
            db.session.commit()
            print(f"已创建管理员和 {len(employees)} 个员工账户")
            
            # 为员工生成测试任务数据
            print("生成测试任务数据...")
            task_titles = [
                '完成项目报告', '客户会议', '代码审查', '系统测试', '文档编写',
                '数据分析', '产品设计', '市场调研', '培训课程', '会议准备',
                '问题排查', '性能优化', '安全检查', '备份维护', '用户支持',
                '需求分析', '原型设计', '测试用例', '部署上线', '监控维护'
            ]
            
            task_descriptions = [
                '完成本周的项目进度报告，包括完成情况和下周计划',
                '与客户进行项目进度沟通，了解需求和反馈',
                '对团队成员的代码进行审查，确保代码质量',
                '对系统进行全面测试，发现并修复问题',
                '编写技术文档和用户手册',
                '分析用户数据，生成分析报告',
                '设计新产品功能，制定设计方案',
                '进行市场调研，了解竞争对手情况',
                '准备培训材料，进行员工培训',
                '准备会议材料，安排会议议程',
                '排查系统问题，找出根本原因',
                '优化系统性能，提升用户体验',
                '进行安全检查，确保系统安全',
                '定期备份数据，确保数据安全',
                '处理用户反馈，提供技术支持',
                '分析用户需求，制定解决方案',
                '设计产品原型，验证功能可行性',
                '编写测试用例，确保功能正确性',
                '部署新版本，确保系统稳定',
                '监控系统运行状态，及时处理异常'
            ]
            
            priorities = ['low', 'medium', 'high']
            
            # 为每个员工生成过去30天的任务
            for employee in employees:
                # 每个员工随机生成15-25个任务
                num_tasks = random.randint(15, 25)
                
                for _ in range(num_tasks):
                    # 随机选择过去30天内的日期
                    days_ago = random.randint(0, 30)
                    task_date = date.today() - timedelta(days=days_ago)
                    
                    # 随机选择任务信息
                    title = random.choice(task_titles)
                    description = random.choice(task_descriptions)
                    priority = random.choice(priorities)
                    
                    task = Task(
                        title=title,
                        description=description,
                        date=task_date,
                        status='in_progress',
                        priority=priority,
                        user_id=employee.id
                    )
                    db.session.add(task)
            
            db.session.commit()
            
            total_users = User.query.count()
            total_tasks = Task.query.count()
            print(f"数据初始化完成！")
            print(f"总用户数: {total_users}")
            print(f"总任务数: {total_tasks}")
            print(f"管理员账户: admin / admin123")
            print(f"员工账户示例: employee01 / 123456")
        else:
            print("数据库已存在，跳过初始化")
    
    app.run(debug=True, host='0.0.0.0', port=5000) 