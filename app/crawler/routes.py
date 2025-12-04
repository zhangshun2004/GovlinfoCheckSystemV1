from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required
from app.crawler.baidu import BaiduCrawler
from app.models import CollectedData
from app.extensions import db

bp = Blueprint('crawler', __name__)

@bp.route('/manager')
@login_required
def manager():
    return render_template('crawler/manager.html')

@bp.route('/search_page')
@login_required
def search_page():
    return render_template('crawler/search.html')

@bp.route('/api/search', methods=['GET'])
@login_required
def search_api():
    keyword = request.args.get('keyword')
    if not keyword:
        return jsonify({"code": 400, "msg": "关键字不能为空", "data": []})
    
    crawler = BaiduCrawler()
    results = crawler.search(keyword)
    
    return jsonify({
        "code": 0,
        "msg": "success",
        "count": len(results),
        "data": results
    })

@bp.route('/api/deep_collect', methods=['POST'])
@login_required
def deep_collect_api():
    url = request.form.get('url')
    if not url:
        return jsonify({"code": 400, "msg": "URL不能为空"})
        
    crawler = BaiduCrawler()
    content = crawler.fetch_content(url)
    
    return jsonify({
        "code": 0,
        "msg": "success",
        "data": {"content": content}
    })

@bp.route('/api/collected_data', methods=['GET'])
@login_required
def get_collected_data():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    
    pagination = CollectedData.query.order_by(CollectedData.created_at.desc()).paginate(
        page=page, per_page=limit, error_out=False
    )
    
    data = []
    for item in pagination.items:
        data.append({
            "id": item.id,
            "title": item.title,
            "source": item.source,
            "original_url": item.original_url,
            "cover": item.cover_url,
            "is_deep_collected": item.is_deep_collected,
            "created_at": item.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    return jsonify({
        "code": 0,
        "msg": "",
        "count": pagination.total,
        "data": data
    })

@bp.route('/api/delete_data', methods=['POST'])
@login_required
def delete_data():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({"code": 400, "msg": "请选择要删除的数据"})
        
    try:
        CollectedData.query.filter(CollectedData.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({"code": 0, "msg": "删除成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": str(e)})
