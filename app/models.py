from .extensions import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime

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
    title = db.Column(db.String(256), nullable=False)
    summary = db.Column(db.Text)
    source = db.Column(db.String(64))
    original_url = db.Column(db.String(512))
    cover = db.Column(db.String(512))
    keyword = db.Column(db.String(64))
    
    # 深度采集相关
    is_deep_collected = db.Column(db.Boolean, default=False)
    deep_content = db.Column(db.Text) # 存储深度采集的正文内容
    deep_collected_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CollectedData {self.title}>'

class CollectionRule(db.Model):
    __tablename__ = 'collection_rules'
    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(128), unique=True, nullable=False)
    domain = db.Column(db.String(128)) # e.g., xinhuanet.com
    title_xpath = db.Column(db.String(256))
    content_xpath = db.Column(db.String(256))
    headers = db.Column(db.Text) # Store as JSON string or key-value text
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<CollectionRule {self.site_name}>'

class ArticleDetail(db.Model):
    __tablename__ = 'article_details'
    id = db.Column(db.Integer, primary_key=True)
    collected_data_id = db.Column(db.Integer, db.ForeignKey('collected_data.id'), unique=True)
    title = db.Column(db.String(256))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    collected_data = db.relationship('CollectedData', backref=db.backref('detail', uselist=False))

    def __repr__(self):
        return f'<ArticleDetail {self.title}>'

class AIEngine(db.Model):
    __tablename__ = 'ai_engines'
    id = db.Column(db.Integer, primary_key=True)
    provider_name = db.Column(db.String(128), nullable=False) # e.g. OpenAI, DeepSeek
    api_url = db.Column(db.String(512), nullable=False)
    api_key = db.Column(db.String(512), nullable=False)
    model_name = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<AIEngine {self.provider_name}-{self.model_name}>'

class CrawlerSource(db.Model):
    __tablename__ = 'crawler_sources'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    key = db.Column(db.String(64), unique=True, nullable=False) # e.g. baidu, xinhua, custom key
    module = db.Column(db.String(256), nullable=False) # python import path
    class_name = db.Column(db.String(128), nullable=False) # class to instantiate
    base_url = db.Column(db.String(512))
    headers = db.Column(db.Text) # JSON string
    enabled = db.Column(db.Boolean, default=True)
    search_url = db.Column(db.String(512))
    search_method = db.Column(db.String(16), default='GET')
    search_params = db.Column(db.Text)
    search_headers = db.Column(db.Text)
    result_is_json = db.Column(db.Boolean, default=True)
    result_item_xpath = db.Column(db.String(256))
    field_map = db.Column(db.Text)
    deep_headers = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<CrawlerSource {self.key}>'
