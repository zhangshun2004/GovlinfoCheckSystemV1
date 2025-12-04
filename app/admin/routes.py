from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models import User, Role, SystemSetting
from app.extensions import db
from functools import wraps

bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.role or current_user.role.name != 'Administrator':
            flash('您没有权限执行此操作', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/users')
@login_required
@admin_required
def users():
    users_list = User.query.all()
    roles = Role.query.all()
    return render_template('admin/users.html', users=users_list, roles=roles)

@bp.route('/users/add', methods=['POST'])
@login_required
@admin_required
def add_user():
    username = request.form.get('username')
    password = request.form.get('password')
    role_id = request.form.get('role_id')
    
    if User.query.filter_by(username=username).first():
        flash('用户已存在', 'error')
    else:
        new_user = User(username=username, role_id=role_id)
        new_user.password = password
        db.session.add(new_user)
        db.session.commit()
        flash('用户添加成功', 'success')
    return redirect(url_for('admin.users'))

@bp.route('/users/delete/<int:user_id>')
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('不能删除自己', 'error')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('用户删除成功', 'success')
    return redirect(url_for('admin.users'))

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    setting = SystemSetting.query.first()
    if not setting:
        setting = SystemSetting()
        db.session.add(setting)
        db.session.commit()
    
    if request.method == 'POST':
        setting.app_name = request.form.get('app_name')
        # 这里可以添加文件上传处理逻辑用于LOGO
        db.session.commit()
        flash('设置已更新', 'success')
        return redirect(url_for('admin.settings'))
        
    return render_template('admin/settings.html', setting=setting)
