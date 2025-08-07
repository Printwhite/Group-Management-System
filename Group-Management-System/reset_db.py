#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
重置数据库脚本
删除现有数据库文件并重新初始化
"""

import os
from app import app, db, User, Task, Log
from werkzeug.security import generate_password_hash
from datetime import datetime, date, timedelta
import random

def reset_database():
    """重置数据库"""
    with app.app_context():
        print("正在重置数据库...")
        
        # 删除数据库文件
        db_path = 'instance/workflow.db'
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"已删除数据库文件: {db_path}")
        
        # 重新创建数据库
        db.create_all()
        print("已重新创建数据库")
        
        # 创建管理员账户
        admin = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            name='系统管理员',
            role='manager',
            email='admin@company.com',
            phone='13800000000'
        )
        db.session.add(admin)
        
        # 创建25个员工账户
        employees = []
        for i in range(1, 26):
            employee = User(
                username=f'employee{i:02d}',
                password_hash=generate_password_hash('123456'),
                name=f'员工{i:02d}',
                role='employee',
                email=f'employee{i:02d}@company.com',
                phone=f'138{i:06d}'
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
        managers = User.query.filter_by(role='manager').count()
        employees_count = User.query.filter_by(role='employee').count()
        
        print(f"\n数据库重置完成！")
        print(f"总用户数: {total_users}")
        print(f"管理员数: {managers}")
        print(f"员工数: {employees_count}")
        print(f"总任务数: {total_tasks}")
        print(f"\n管理员账户:")
        print(f"用户名: admin")
        print(f"密码: admin123")
        print(f"\n员工账户示例:")
        print(f"用户名: employee01")
        print(f"密码: 123456")

if __name__ == '__main__':
    reset_database()
