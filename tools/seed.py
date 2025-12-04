import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.extensions import db
from app.models import User, Role

app = create_app()

with app.app_context():
    # Create Roles
    admin_role = Role.query.filter_by(name='Administrator').first()
    if not admin_role:
        admin_role = Role(name='Administrator')
        db.session.add(admin_role)
    
    user_role = Role.query.filter_by(name='User').first()
    if not user_role:
        user_role = Role(name='User')
        db.session.add(user_role)
    
    db.session.commit()

    # Create Admin User
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', role=admin_role)
        admin.password = 'admin123'
        db.session.add(admin)
        print("Created admin user (admin/admin123)")
    
    db.session.commit()
