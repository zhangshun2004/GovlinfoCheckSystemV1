import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app

if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5000)), debug=True)
