from .extensions import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    users = db.relationship('User', backref='role', lazy='dynamic')

    def __repr__(self):
        return f'<Role {self.name}>'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    app_name = db.Column(db.String(128), default='政企智能舆情分析报告生成智能体应用系统')
    logo_url = db.Column(db.String(256), nullable=True)

    def __repr__(self):
        return f'<SystemSetting {self.app_name}>'

class CollectedData(db.Model):
    __tablename__ = 'collected_data'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256))
    summary = db.Column(db.Text)
    source = db.Column(db.String(64))
    original_url = db.Column(db.String(512))
    cover_url = db.Column(db.String(512))
    publish_date = db.Column(db.String(64))
    
    # 深度采集字段
    is_deep_collected = db.Column(db.Boolean, default=False)
    content = db.Column(db.Text) # 完整内容
    
    created_at = db.Column(db.DateTime, default=db.func.now())
    keyword = db.Column(db.String(64)) # 来源关键词

    def __repr__(self):
        return f'<CollectedData {self.title}>'

