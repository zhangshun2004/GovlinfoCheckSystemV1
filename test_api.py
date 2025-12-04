import requests
import json

def test_api():
    # 1. Login to get cookie
    session = requests.Session()
    login_url = 'http://127.0.0.1:5000/auth/login'
    # Assuming you have CSRF protection disabled or handled? 
    # Flask-WTF enables it by default, but we didn't set it up explicitly in forms?
    # Wait, the login form didn't use form.hidden_tag() in previous turns?
    # Let's check login.html content from previous turns. 
    # It used standard <form> without CSRF token explicitly.
    # So we can try simple post.
    
    login_data = {
        'username': 'admin',
        'password': 'admin123'
    }
    
    print("Attempting login...")
    r = session.post(login_url, data=login_data)
    if r.status_code != 200:
        # It might redirect to index on success
        if r.url.endswith('/auth/login'):
             print("Login failed (still on login page).")
             # Check if it's a CSRF issue.
             if 'csrf_token' in r.text:
                 print("CSRF token might be required.")
        else:
             print(f"Login redirect/success? URL: {r.url}")
    else:
        # Check if we are redirected
        pass

    # 2. Call Search API
    search_url = 'http://127.0.0.1:5000/crawler/api/search'
    params = {'keyword': '成都'}
    
    print(f"Calling API: {search_url}")
    try:
        r = session.get(search_url, params=params)
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            try:
                data = r.json()
                print("Response JSON:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print("Response is not JSON:")
                print(r.text[:500])
        else:
            print("Request failed.")
            print(r.text[:500])
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == '__main__':
    test_api()
