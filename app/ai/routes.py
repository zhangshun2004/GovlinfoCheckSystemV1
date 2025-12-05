from flask import render_template, request, jsonify
from flask_login import login_required
from app.ai import bp
from app.models import AIEngine
from app.extensions import db
import requests

@bp.route('/manager')
@login_required
def manager():
    return render_template('ai/manager.html')

@bp.route('/api/engines', methods=['GET'])
@login_required
def list_engines():
    try:
        engines = AIEngine.query.order_by(AIEngine.created_at.desc()).all()
        data = [{
            "id": e.id,
            "provider_name": e.provider_name,
            "api_url": e.api_url,
            "api_key": e.api_key[:4] + "****" + e.api_key[-4:] if len(e.api_key) > 8 else "****", # Mask key
            "model_name": e.model_name,
            "is_active": e.is_active,
            "created_at": e.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for e in engines]
        return jsonify({"code": 0, "msg": "success", "data": data})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取引擎列表失败: {str(e)}"})

@bp.route('/api/engines', methods=['POST'])
@login_required
def create_engine():
    data = request.json
    try:
        engine = AIEngine(
            provider_name=data.get('provider_name'),
            api_url=data.get('api_url'),
            api_key=data.get('api_key'),
            model_name=data.get('model_name'),
            is_active=data.get('is_active', True)
        )
        db.session.add(engine)
        db.session.commit()
        return jsonify({"code": 0, "msg": "创建成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"创建失败: {str(e)}"})

@bp.route('/api/engines', methods=['PUT'])
@login_required
def update_engine():
    data = request.json
    id = data.get('id')
    engine = AIEngine.query.get(id)
    if not engine:
        return jsonify({"code": 404, "msg": "引擎不存在"})
        
    try:
        engine.provider_name = data.get('provider_name', engine.provider_name)
        engine.api_url = data.get('api_url', engine.api_url)
        # Only update key if provided and not empty/masked
        new_key = data.get('api_key')
        if new_key and not new_key.startswith('****'):
             engine.api_key = new_key
             
        engine.model_name = data.get('model_name', engine.model_name)
        if 'is_active' in data:
            engine.is_active = data.get('is_active')
            
        db.session.commit()
        return jsonify({"code": 0, "msg": "更新成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"更新失败: {str(e)}"})

@bp.route('/api/engines', methods=['DELETE'])
@login_required
def delete_engine():
    ids = request.json.get('ids', [])
    try:
        AIEngine.query.filter(AIEngine.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({"code": 0, "msg": "删除成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"删除失败: {str(e)}"})

@bp.route('/api/test', methods=['POST'])
@login_required
def test_engine():
    data = request.json
    api_url = data.get('api_url')
    api_key = data.get('api_key')
    model_name = data.get('model_name')
    
    if not all([api_url, api_key, model_name]):
        return jsonify({"code": 400, "msg": "参数不完整"})
        
    # Simple test using OpenAI format
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Hello, confirm you are working."}],
        "max_tokens": 10
    }
    
    try:
        # Normalize URL
        target_url = api_url.rstrip('/')
        if 'v1' not in target_url and 'chat/completions' not in target_url:
             target_url += '/v1/chat/completions'
        elif target_url.endswith('/v1'):
             target_url += '/chat/completions'
             
        response = requests.post(target_url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
             return jsonify({"code": 0, "msg": "连接测试成功"})
        else:
             return jsonify({"code": 1, "msg": f"测试失败: HTTP {response.status_code} - {response.text[:100]}"})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"连接异常: {str(e)}"})

@bp.route('/api/chat_test', methods=['POST'])
@login_required
def chat_test():
    data = request.json
    engine_id = data.get('engine_id')
    messages = data.get('messages', [])
    
    if not engine_id or not messages:
        return jsonify({"code": 400, "msg": "参数不完整"})
        
    engine = AIEngine.query.get(engine_id)
    if not engine:
        return jsonify({"code": 404, "msg": "引擎不存在"})
        
    headers = {
        "Authorization": f"Bearer {engine.api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": engine.model_name,
        "messages": messages,
        "stream": False
    }
    
    try:
        # Normalize URL
        target_url = engine.api_url.rstrip('/')
        if 'v1' not in target_url and 'chat/completions' not in target_url:
             target_url += '/v1/chat/completions'
        elif target_url.endswith('/v1'):
             target_url += '/chat/completions'
             
        response = requests.post(target_url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                return jsonify({"code": 0, "msg": "success", "data": {"content": content}})
            else:
                return jsonify({"code": 1, "msg": "API返回格式异常", "raw": result})
        else:
            return jsonify({"code": 1, "msg": f"请求失败: HTTP {response.status_code} - {response.text[:200]}"})
            
    except Exception as e:
        return jsonify({"code": 500, "msg": f"请求异常: {str(e)}"})
