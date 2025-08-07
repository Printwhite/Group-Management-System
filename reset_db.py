#!/usr/bin/env python3
"""
数据库重置脚本
用于清理和重新初始化数据库
"""

import os
from app import app, db, User
from werkzeug.security import generate_password_hash

def reset_database():
    """重置数据库"""
    with app.app_context():
        # 删除现有数据库文件
        db_file = 'instance/workflow.db'
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"已删除数据库文件: {db_file}")
        
        # 重新创建数据库表
        db.create_all()
        print("已重新创建数据库表")
        
        # 创建默认管理员账户
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
        print("已创建默认账户:")
        print("  管理员:")
        print("    用户名: admin")
        print("    密码: admin123")
        print("    角色: 领导")
        print("  员工1:")
        print("    用户名: zhang_san")
        print("    密码: 123456")
        print("    姓名: 张三")
        print("  员工2:")
        print("    用户名: li_si")
        print("    密码: 123456")
        print("    姓名: 李四")

if __name__ == '__main__':
    print("开始重置数据库...")
    reset_database()
    print("数据库重置完成！")
