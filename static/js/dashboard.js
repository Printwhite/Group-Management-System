// 全局变量
let currentDate = new Date();
let tasks = [];
let editingTaskId = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeNavigation();
    loadTasks();
    renderCalendar();
    setupEventListeners();
});

// 初始化导航
function initializeNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            const viewName = this.getAttribute('data-view');
            switchView(viewName);
        });
    });
}

// 切换视图
function switchView(viewName) {
    // 更新导航状态
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-view="${viewName}"]`).classList.add('active');
    
    // 更新视图显示
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });
    document.getElementById(`${viewName}-view`).classList.add('active');
    
    // 检查是否为管理员，添加相应的CSS类
    const isManager = document.querySelector('[data-view="users"]') !== null;
    const mainContent = document.querySelector('.main-content');
    if (isManager) {
        mainContent.classList.add('manager-view');
    } else {
        mainContent.classList.remove('manager-view');
    }
    
    // 根据视图加载数据
    if (viewName === 'calendar') {
        renderCalendar();
    } else if (viewName === 'tasks') {
        renderTasksList();
    } else if (viewName === 'users') {
        loadUsers();
    }
}

// 设置事件监听器
function setupEventListeners() {
    // 任务表单提交
    document.getElementById('task-form').addEventListener('submit', function(e) {
        e.preventDefault();
        saveTask();
    });
    
    // 模态框关闭
    document.getElementById('task-modal').addEventListener('click', function(e) {
        if (e.target === this) {
            closeTaskModal();
        }
    });
}

// 加载任务数据
async function loadTasks() {
    try {
        const response = await fetch('/api/tasks');
        tasks = await response.json();
        renderCalendar();
        renderTasksList();
    } catch (error) {
        console.error('加载任务失败:', error);
    }
}

// 渲染日历
function renderCalendar() {
    const calendarDays = document.getElementById('calendar-days');
    const currentMonthElement = document.getElementById('current-month');
    
    if (!calendarDays) return;
    
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    // 更新月份显示
    currentMonthElement.textContent = `${year}年${month + 1}月`;
    
    // 获取月份的第一天和最后一天
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startDate = new Date(firstDay);
    startDate.setDate(startDate.getDate() - firstDay.getDay());
    
    let calendarHTML = '';
    
    // 检查当前用户是否为领导
    const isManager = document.querySelector('[data-view="users"]') !== null;
    
    // 生成日历网格
    for (let i = 0; i < 42; i++) {
        const currentDay = new Date(startDate);
        currentDay.setDate(startDate.getDate() + i);
        
        const isOtherMonth = currentDay.getMonth() !== month;
        const isToday = isSameDay(currentDay, new Date());
        const dayTasks = getTasksForDate(currentDay);
        
        const clickHandler = isManager ? `onclick="showDaySchedule('${formatDate(currentDay)}')"` : `onclick="openTaskModal('${formatDate(currentDay)}')"`;
        
        // 如果是管理员，按用户分组显示任务
        let tasksHTML = '';
        if (isManager) {
            // 按用户分组任务
            const tasksByUser = {};
            dayTasks.forEach(task => {
                if (!tasksByUser[task.user_username]) {
                    tasksByUser[task.user_username] = [];
                }
                tasksByUser[task.user_username].push(task);
            });
            
            // 为每个用户生成任务显示
            Object.keys(tasksByUser).forEach(username => {
                const userTasks = tasksByUser[username];
                const userTask = userTasks[0]; // 获取第一个任务来获取用户信息
                tasksHTML += `
                    <div class="calendar-user-section">
                        <div class="calendar-user-name">${userTask.user_name}</div>
                                                 ${userTasks.map(task => `
                             <div class="calendar-task priority-${task.priority}" 
                                  onclick="event.stopPropagation();">
                                 ${task.title}
                             </div>
                         `).join('')}
                    </div>
                `;
            });
        } else {
            // 普通员工显示自己的任务
            tasksHTML = dayTasks.map(task => `
                <div class="calendar-task priority-${task.priority}" 
                     onclick="event.stopPropagation(); editTask(${task.id})">
                    ${task.title}
                </div>
            `).join('');
        }
        
        calendarHTML += `
            <div class="calendar-day ${isOtherMonth ? 'other-month' : ''} ${isToday ? 'today' : ''}" 
                 ${clickHandler}>
                <div class="calendar-day-number">${currentDay.getDate()}</div>
                <div class="calendar-tasks">
                    ${tasksHTML}
                </div>
            </div>
        `;
    }
    
    calendarDays.innerHTML = calendarHTML;
}

// 渲染任务列表
function renderTasksList() {
    const tasksList = document.getElementById('tasks-list');
    const startDateFilter = document.getElementById('start-date-filter')?.value;
    const endDateFilter = document.getElementById('end-date-filter')?.value;
    
    if (!tasksList) return;
    
    let filteredTasks = tasks;
    
    // 按日期筛选
    if (startDateFilter) {
        filteredTasks = filteredTasks.filter(task => task.date >= startDateFilter);
    }
    if (endDateFilter) {
        filteredTasks = filteredTasks.filter(task => task.date <= endDateFilter);
    }
    
    // 按日期排序
    filteredTasks.sort((a, b) => new Date(b.date) - new Date(a.date));
    
    // 检查当前用户是否为管理员
    const isManager = document.querySelector('[data-view="users"]') !== null;
    
    const tasksHTML = filteredTasks.map(task => `
        <div class="task-card">
            <div class="task-header">
                <div>
                    <div class="task-title">${task.title}</div>
                    <div class="task-meta">
                        <span>${task.user_name}</span>
                        <span>${formatDate(new Date(task.date))}</span>
                        <span class="task-priority ${task.priority}">${getPriorityText(task.priority)}</span>
                        <span class="task-status ${task.status}">${getStatusText(task.status)}</span>
                    </div>
                </div>
                ${!isManager ? `
                <div class="task-actions">
                    <button class="btn btn-small btn-outline" onclick="editTask(${task.id})">编辑</button>
                    <button class="btn btn-small btn-outline" onclick="deleteTask(${task.id})">删除</button>
                </div>
                ` : ''}
            </div>
            ${task.description ? `<div class="task-description">${task.description}</div>` : ''}
        </div>
    `).join('');
    
    tasksList.innerHTML = tasksHTML;
}

// 筛选任务
function filterTasks() {
    renderTasksList();
}

// 导出CSV
function exportCSV() {
    const startDate = document.getElementById('start-date-filter')?.value;
    const endDate = document.getElementById('end-date-filter')?.value;
    
    let url = '/api/export-csv';
    const params = [];
    
    if (startDate) params.push(`start_date=${startDate}`);
    if (endDate) params.push(`end_date=${endDate}`);
    
    if (params.length > 0) {
        url += '?' + params.join('&');
    }
    
    // 创建下载链接
    const link = document.createElement('a');
    link.href = url;
    link.download = `tasks_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// 加载用户列表（仅领导可见）
async function loadUsers() {
    try {
        const response = await fetch('/api/users');
        const users = await response.json();
        
        const usersList = document.getElementById('users-list');
        if (usersList) {
            if (users.length === 0) {
                usersList.innerHTML = '<div class="no-users">暂无员工账户</div>';
                return;
            }
            
            // 添加搜索功能
            const searchHTML = `
                <div class="users-search-container">
                    <div class="search-box">
                        <input type="text" id="user-search" placeholder="搜索员工..." onkeyup="filterUsers()">
                        <span class="search-icon">🔍</span>
                    </div>
                    <div class="users-summary">
                        <span>总员工数: <strong>${users.length}</strong></span>
                    </div>
                </div>
            `;
            
            const usersHTML = users.map(user => `
                <div class="user-card" data-username="${user.username}" data-name="${user.name}">
                    <div class="user-info">
                        <div class="user-details">
                            <h4>${user.name}</h4>
                            <p>用户名: ${user.username}</p>
                        </div>
                        <div class="user-status">
                            <span class="user-role">员工</span>
                            <span class="read-only-badge">只读</span>
                        </div>
                    </div>
                </div>
            `).join('');
            
            usersList.innerHTML = searchHTML + '<div class="users-grid">' + usersHTML + '</div>';
        }
    } catch (error) {
        console.error('加载用户失败:', error);
    }
}

// 过滤用户显示
function filterUsers() {
    const searchTerm = document.getElementById('user-search').value.toLowerCase();
    const userCards = document.querySelectorAll('.user-card');
    
    userCards.forEach(card => {
        const username = card.getAttribute('data-username').toLowerCase();
        const name = card.getAttribute('data-name').toLowerCase();
        
        if (username.includes(searchTerm) || name.includes(searchTerm)) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
    
    // 更新统计信息
    const visibleCards = document.querySelectorAll('.user-card[style="display: block"], .user-card:not([style*="display: none"])');
    const summaryElement = document.querySelector('.users-summary span');
    if (summaryElement) {
        summaryElement.innerHTML = `总员工数: <strong>${visibleCards.length}</strong>`;
    }
}

// 打开任务模态框
function openTaskModal(date = null) {
    const modal = document.getElementById('task-modal');
    const modalTitle = document.getElementById('modal-title');
    const taskForm = document.getElementById('task-form');
    const taskDate = document.getElementById('task-date');
    
    editingTaskId = null;
    modalTitle.textContent = '添加任务';
    taskForm.reset();
    
    // 自动设置当前日期为默认值
    const today = new Date();
    const currentDate = formatDate(today);
    
    if (date) {
        taskDate.value = date;
    } else {
        taskDate.value = currentDate;
    }
    
    // 设置日期限制（只能选择最近一天往前5天）
    const minDate = new Date(today);
    minDate.setDate(today.getDate() - 5);
    
    taskDate.max = currentDate;
    taskDate.min = formatDate(minDate);
    
    modal.classList.add('active');
}

// 关闭任务模态框
function closeTaskModal() {
    const modal = document.getElementById('task-modal');
    modal.classList.remove('active');
    editingTaskId = null;
}

// 编辑任务
function editTask(taskId) {
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    
    editingTaskId = taskId;
    
    const modal = document.getElementById('task-modal');
    const modalTitle = document.getElementById('modal-title');
    const taskTitle = document.getElementById('task-title');
    const taskDescription = document.getElementById('task-description');
    const taskDate = document.getElementById('task-date');
    const taskPriority = document.getElementById('task-priority');
    const taskStatus = document.getElementById('task-status');
    
    modalTitle.textContent = '编辑任务';
    taskTitle.value = task.title;
    taskDescription.value = task.description || '';
    taskDate.value = task.date;
    taskPriority.value = task.priority;
    taskStatus.value = task.status;
    
    // 设置日期限制（只能选择最近一天往前5天）
    const today = new Date();
    const currentDate = formatDate(today);
    const minDate = new Date(today);
    minDate.setDate(today.getDate() - 5);
    
    taskDate.max = currentDate;
    taskDate.min = formatDate(minDate);
    
    modal.classList.add('active');
}

// 保存任务
async function saveTask() {
    const taskTitle = document.getElementById('task-title').value;
    const taskDescription = document.getElementById('task-description').value;
    const taskDate = document.getElementById('task-date').value;
    const taskPriority = document.getElementById('task-priority').value;
    const taskStatus = document.getElementById('task-status').value;
    
    const taskData = {
        title: taskTitle,
        description: taskDescription,
        date: taskDate,
        priority: taskPriority,
        status: taskStatus
    };
    
    try {
        let response;
        if (editingTaskId) {
            // 更新任务
            response = await fetch(`/api/tasks/${editingTaskId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(taskData)
            });
        } else {
            // 创建任务
            response = await fetch('/api/tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(taskData)
            });
        }
        
        if (response.ok) {
            closeTaskModal();
            loadTasks();
        } else {
            const error = await response.json();
            alert('保存失败: ' + (error.error || '未知错误'));
        }
    } catch (error) {
        console.error('保存任务失败:', error);
        alert('保存失败，请重试');
    }
}

// 显示日程表（管理员功能）
function showDaySchedule(date) {
    const dayTasks = getTasksForDate(new Date(date));
    const isManager = document.querySelector('[data-view="users"]') !== null;
    
    if (!isManager) return;
    
    // 按用户分组任务
    const tasksByUser = {};
    dayTasks.forEach(task => {
        if (!tasksByUser[task.user_username]) {
            tasksByUser[task.user_username] = [];
        }
        tasksByUser[task.user_username].push(task);
    });
    
    // 创建日程表HTML
    let scheduleHTML = `
        <div class="schedule-header">
            <h3>${formatDateForDisplay(date)} 工作安排</h3>
            <div class="schedule-controls">
                <div class="search-box">
                    <input type="text" id="employee-search" placeholder="搜索员工..." onkeyup="filterEmployees()">
                    <span class="search-icon">🔍</span>
                </div>
                <button class="modal-close" onclick="closeScheduleModal()">&times;</button>
            </div>
        </div>
        <div class="schedule-content">
            <div class="schedule-summary">
                <span class="summary-item">总员工数: <strong>${Object.keys(tasksByUser).length}</strong></span>
                <span class="summary-item">总任务数: <strong>${dayTasks.length}</strong></span>
                <span class="summary-item">有任务的员工: <strong>${Object.keys(tasksByUser).length}</strong></span>
            </div>
    `;
    
    if (Object.keys(tasksByUser).length === 0) {
        scheduleHTML += '<div class="no-tasks">该日期暂无工作安排</div>';
    } else {
        // 按员工姓名排序
        const sortedUsers = Object.keys(tasksByUser).sort((a, b) => {
            const userA = tasksByUser[a][0];
            const userB = tasksByUser[b][0];
            return userA.user_name.localeCompare(userB.user_name, 'zh-CN');
        });
        
        scheduleHTML += '<div class="schedule-users-grid">';
        
        sortedUsers.forEach((username, index) => {
            const userTasks = tasksByUser[username];
            const userTask = userTasks[0]; // 获取第一个任务来获取用户信息
            
            // 计算任务优先级统计
            const priorityStats = {
                high: userTasks.filter(t => t.priority === 'high').length,
                medium: userTasks.filter(t => t.priority === 'medium').length,
                low: userTasks.filter(t => t.priority === 'low').length
            };
            
            scheduleHTML += `
                <div class="schedule-user-section" data-employee="${userTask.user_name}">
                    <div class="schedule-user-header">
                        <div class="user-info">
                            <h4>${userTask.user_name}</h4>
                            <span class="task-count">${userTasks.length} 个任务</span>
                        </div>
                        <div class="priority-stats">
                            ${priorityStats.high > 0 ? `<span class="priority-badge high">${priorityStats.high} 高</span>` : ''}
                            ${priorityStats.medium > 0 ? `<span class="priority-badge medium">${priorityStats.medium} 中</span>` : ''}
                            ${priorityStats.low > 0 ? `<span class="priority-badge low">${priorityStats.low} 低</span>` : ''}
                        </div>
                    </div>
                    <div class="schedule-tasks">
                        ${userTasks.map(task => `
                            <div class="schedule-task priority-${task.priority}">
                                <div class="task-info">
                                    <div class="task-title">${task.title}</div>
                                    ${task.description ? `<div class="task-description">${task.description}</div>` : ''}
                                </div>
                                <div class="task-meta">
                                    <span class="task-priority ${task.priority}">${getPriorityText(task.priority)}</span>
                                    <span class="task-status ${task.status}">${getStatusText(task.status)}</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        });
        
        scheduleHTML += '</div>';
    }
    
    scheduleHTML += '</div>';
    
    // 显示模态框
    const modal = document.getElementById('schedule-modal');
    const modalContent = document.getElementById('schedule-modal-content');
    modalContent.innerHTML = scheduleHTML;
    modal.classList.add('active');
    
    // 聚焦到搜索框
    setTimeout(() => {
        const searchBox = document.getElementById('employee-search');
        if (searchBox) {
            searchBox.focus();
        }
    }, 100);
}

// 关闭日程表模态框
function closeScheduleModal() {
    const modal = document.getElementById('schedule-modal');
    modal.classList.remove('active');
}

// 删除任务
async function deleteTask(taskId) {
    if (!confirm('确定要删除这个任务吗？')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadTasks();
            // 如果日程表模态框是打开的，刷新它
            const scheduleModal = document.getElementById('schedule-modal');
            if (scheduleModal.classList.contains('active')) {
                const currentDate = document.querySelector('.schedule-header h3').textContent.split(' ')[0];
                showDaySchedule(currentDate);
            }
        } else {
            const error = await response.json();
            alert('删除失败: ' + (error.error || '未知错误'));
        }
    } catch (error) {
        console.error('删除任务失败:', error);
        alert('删除失败，请重试');
    }
}

// 日历导航
function previousMonth() {
    currentDate.setMonth(currentDate.getMonth() - 1);
    renderCalendar();
}

function nextMonth() {
    currentDate.setMonth(currentDate.getMonth() + 1);
    renderCalendar();
}

// 工具函数
function formatDate(date) {
    return date.toISOString().split('T')[0];
}

function isSameDay(date1, date2) {
    return date1.toDateString() === date2.toDateString();
}

function getTasksForDate(date) {
    return tasks.filter(task => task.date === formatDate(date));
}

function getPriorityText(priority) {
    const texts = {
        'high': '高',
        'medium': '中',
        'low': '低'
    };
    return texts[priority] || priority;
}

function getStatusText(status) {
    const texts = {
        'in_progress': '进行中'
    };
    return texts[status] || status;
}

// 格式化日期显示
function formatDateForDisplay(dateStr) {
    const date = new Date(dateStr);
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
    const weekday = weekdays[date.getDay()];
    
    return `${year}年${month}月${day}日 星期${weekday}`;
}


