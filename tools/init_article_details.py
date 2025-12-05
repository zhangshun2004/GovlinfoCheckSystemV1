from app import create_app
from app.extensions import db
from app.models import ArticleDetail

app = create_app()

with app.app_context():
    # Create the table
    try:
        ArticleDetail.__table__.create(db.engine)
        print("Table 'article_details' created successfully.")
    except Exception as e:
        print(f"Error creating table: {e}")
        # Likely already exists or other issue
