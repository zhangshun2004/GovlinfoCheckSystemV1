import json
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required
from app.crawler.baidu import BaiduCrawler
from app.crawler.xinhua import XinhuaCrawler
from app.models import CollectedData, CollectionRule, ArticleDetail
from app.extensions import db
from datetime import datetime
import requests
from lxml import html as lxml_html
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

bp = Blueprint('crawler', __name__)

def _process_headers(headers_text):
    """
    Process raw headers text into JSON string.
    Supports:
    1. JSON string
    2. "Key: Value" format (standard raw)
    3. Key and Value on alternating lines (Chrome DevTools copy)
    """
    if not headers_text:
        return None
        
    headers_text = headers_text.strip()
    if not headers_text:
        return None

    # 1. Try JSON
    try:
        json_obj = json.loads(headers_text)
        if isinstance(json_obj, dict):
            return json.dumps(json_obj, ensure_ascii=False, indent=2)
    except:
        pass

    headers = {}
    lines = [line.strip() for line in headers_text.split('\n') if line.strip()]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Case: "Key: Value"
        if ':' in line:
            parts = line.split(':', 1)
            key_candidate = parts[0].strip()
            # Basic validation: Header keys usually don't have spaces
            if ' ' not in key_candidate: 
                headers[key_candidate] = parts[1].strip()
                i += 1
                continue
        
        # Case: Key \n Value
        if i + 1 < len(lines):
            key = line
            value = lines[i+1]
            headers[key] = value
            i += 2
        else:
            # Dangling line
            i += 1
            
    if headers:
        return json.dumps(headers, ensure_ascii=False, indent=2)
        
    return headers_text

def _extract_content(tree, xpath):
    try:
        elements = tree.xpath(xpath)
        if not elements:
            return ""
        
        # Join all matching elements
        content_list = []
        for el in elements:
            if isinstance(el, str):
                content_list.append(el.strip())
            else:
                # Get text content, preserving some structure if possible
                # For now, simple text_content()
                content_list.append(el.text_content().strip())
                
        return "\n".join([c for c in content_list if c])
    except Exception:
        return ""

def _fetch_and_parse_detail(url, rule):
    # Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    if rule.headers:
        try:
            custom_headers = json.loads(rule.headers)
            if isinstance(custom_headers, dict):
                headers.update(custom_headers)
        except:
            pass
            
    try:
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        response.encoding = response.apparent_encoding
        
        if response.status_code != 200:
            return None
            
        tree = lxml_html.fromstring(response.content)
        
        # Title
        title = ""
        if rule.title_xpath:
            try:
                titles = tree.xpath(rule.title_xpath)
                if titles:
                    if isinstance(titles[0], str):
                        title = titles[0].strip()
                    else:
                        title = titles[0].text_content().strip()
            except:
                pass
        
        # Content
        content = ""
        
        if rule.content_xpath:
            content = _extract_content(tree, rule.content_xpath)
            
        # Auto-update logic (Simple Version)
        if not content or len(content) < 50:
            # Try fallbacks
            fallbacks = [
                "//div[@class='content']",
                "//div[@id='content']", 
                "//div[@class='article']",
                "//article",
                "//div[contains(@class, 'detail')]",
                "//div[contains(@class, 'news_txt')]",
                "//div[contains(@class, 'main_content')]"
            ]
            
            for fb in fallbacks:
                if fb == rule.content_xpath:
                    continue
                    
                candidate = _extract_content(tree, fb)
                if candidate and len(candidate) > 50:
                    content = candidate
                    # Update Rule!
                    rule.content_xpath = fb
                    # Note: We rely on the caller to commit the session
                    break
        
        if content:
            return {"title": title, "content": content}
        return None
        
    except Exception as e:
        print(f"Detail collect error: {e}")
        return None

@bp.route('/search_page')
@login_required
def search_page():
    return render_template('crawler/search.html')

@bp.route('/manager')
@login_required
def manager():
    return render_template('crawler/manager.html')

@bp.route('/warehouse')
@login_required
def warehouse():
    return render_template('crawler/warehouse.html')

@bp.route('/api/search', methods=['GET'])
@login_required
def search_api():
    keyword = request.args.get('keyword')
    source = request.args.get('source', 'baidu')
    limit = request.args.get('limit', type=int) # Limit for Xinhua
    pages = request.args.get('pages', 1, type=int) # Pages for Baidu
    
    # 如果是百度，关键词不能为空
    if source == 'baidu' and not keyword:
        return jsonify({"code": 400, "msg": "关键字不能为空", "data": []})
    
    results = []
    if source == 'baidu':
        crawler = BaiduCrawler()
        results = crawler.search(keyword, pages=pages)
    elif source == 'xinhua':
        crawler = XinhuaCrawler()
        # For Xinhua, we fetch all available news first to ensure keyword filtering works effectively
        # The homepage usually has a limited number of items (e.g., 20-50), so this is safe.
        all_results = crawler.fetch_news(limit=None)
        
        if keyword:
            # Filter by keyword
            results = [r for r in all_results if keyword in r['title'] or keyword in r['summary']]
        else:
            results = all_results
            
        # Apply limit to the final results
        # Default limit is 20 if not specified
        final_limit = limit if limit else 20
        results = results[:final_limit]
    
    return jsonify({
        "code": 0,
        "msg": "success",
        "count": len(results),
        "data": results
    })

@bp.route('/api/deep_collect', methods=['POST'])
@login_required
def deep_collect_api():
    url = request.json.get('url')
    if not url:
        return jsonify({"code": 400, "msg": "URL不能为空"})
        
    # 根据URL选择爬虫
    if 'news.cn' in url or 'xinhuanet' in url:
        crawler = XinhuaCrawler()
    else:
        crawler = BaiduCrawler()
        
    result = crawler.deep_collect(url)
    
    return jsonify({
        "code": 0,
        "msg": "success",
        "data": {
            "content": result.get('content', ''),
            "publish_time": result.get('publish_time', ''),
            "collected_at": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
    })

@bp.route('/api/save', methods=['POST'])
@login_required
def save_data_api():
    items = request.json.get('items', [])
    if not items:
        return jsonify({"code": 400, "msg": "没有数据需要保存"})
        
    saved_count = 0
    updated_count = 0
    for item in items:
        # 检查是否已存在（根据URL）
        existing = CollectedData.query.filter_by(original_url=item.get('original_url')).first()
        if existing:
            # 如果已存在，且当前数据包含深度采集内容，则更新
            if item.get('is_deep_collected') and not existing.is_deep_collected:
                existing.is_deep_collected = True
                existing.deep_collected_at = datetime.strptime(item.get('deep_collected_at'), '%Y-%m-%d %H:%M:%S') if item.get('deep_collected_at') else datetime.utcnow()
                
                # Save deep content to ArticleDetail
                detail = ArticleDetail.query.filter_by(collected_data_id=existing.id).first()
                if not detail:
                    detail = ArticleDetail(collected_data_id=existing.id)
                    db.session.add(detail)
                detail.title = item.get('title') or existing.title
                detail.content = item.get('deep_content')
                
                updated_count += 1
        else:
            new_data = CollectedData(
                title=item.get('title'),
                summary=item.get('summary'),
                source=item.get('source'),
                original_url=item.get('original_url'),
                cover=item.get('cover'),
                keyword=item.get('keyword'),
                is_deep_collected=item.get('is_deep_collected', False),
                deep_content=None, # Use ArticleDetail instead
                deep_collected_at=datetime.strptime(item.get('deep_collected_at'), '%Y-%m-%d %H:%M:%S') if item.get('deep_collected_at') else None
            )
            db.session.add(new_data)
            db.session.flush() # Get ID
            
            # Save deep content if available
            if new_data.is_deep_collected:
                detail = ArticleDetail(collected_data_id=new_data.id)
                detail.title = new_data.title
                detail.content = item.get('deep_content')
                db.session.add(detail)
                
            saved_count += 1
            
    db.session.commit()
    
    msg = f"成功保存 {saved_count} 条新增数据"
    if updated_count > 0:
        msg += f"，更新 {updated_count} 条深度采集数据"
    
    return jsonify({
        "code": 0,
        "msg": msg,
        "saved_count": saved_count + updated_count
    })

# --- Warehouse APIs ---

@bp.route('/api/warehouse/list', methods=['GET'])
@login_required
def warehouse_list_api():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    keyword = request.args.get('keyword', '')
    
    query = CollectedData.query.order_by(CollectedData.created_at.desc())
    
    if keyword:
        query = query.filter(CollectedData.title.contains(keyword) | CollectedData.summary.contains(keyword))
    
    pagination = query.paginate(page=page, per_page=limit, error_out=False)
    
    data = []
    for item in pagination.items:
        data.append({
            "id": item.id,
            "title": item.title,
            "summary": item.summary,
            "source": item.source,
            "original_url": item.original_url,
            "cover": item.cover,
            "keyword": item.keyword,
            "is_deep_collected": item.is_deep_collected,
            "deep_content": item.deep_content,
            "deep_collected_at": item.deep_collected_at.strftime('%Y-%m-%d %H:%M:%S') if item.deep_collected_at else None,
            "created_at": item.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    # Calculate stats
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    stats = {
        "total": CollectedData.query.count(),
        "deep_collected": CollectedData.query.filter_by(is_deep_collected=True).count(),
        "today_new": CollectedData.query.filter(CollectedData.created_at >= today_start).count()
    }
        
    return jsonify({
        "code": 0,
        "msg": "",
        "count": pagination.total,
        "data": data,
        "stats": stats
    })

@bp.route('/api/warehouse/delete', methods=['POST'])
@login_required
def warehouse_delete_api():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({"code": 400, "msg": "请选择要删除的数据"})
        
    try:
        # count the items to be deleted for feedback
        count = CollectedData.query.filter(CollectedData.id.in_(ids)).count()
        
        # Delete associated ArticleDetails first
        ArticleDetail.query.filter(ArticleDetail.collected_data_id.in_(ids)).delete(synchronize_session=False)
        
        # Then delete CollectedData
        CollectedData.query.filter(CollectedData.id.in_(ids)).delete(synchronize_session=False)
        
        db.session.commit()
        return jsonify({"code": 0, "msg": f"成功删除 {count} 条数据"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"删除失败: {str(e)}"})

@bp.route('/api/rules/copy', methods=['POST'])
@login_required
def rules_copy_api():
    data = request.json
    id = data.get('id')
    
    if not id:
        return jsonify({"code": 400, "msg": "ID不能为空"})
        
    rule = CollectionRule.query.get(id)
    if not rule:
        return jsonify({"code": 404, "msg": "规则不存在"})
        
    try:
        # Generate new site name
        base_name = rule.site_name
        new_name = f"{base_name}_复制"
        
        # Check for duplicates and append counter if needed
        counter = 1
        while CollectionRule.query.filter_by(site_name=new_name).first():
            new_name = f"{base_name}_复制{counter}"
            counter += 1
            
        new_rule = CollectionRule(
            site_name=new_name,
            domain=rule.domain,
            title_xpath=rule.title_xpath,
            content_xpath=rule.content_xpath,
            headers=rule.headers
        )
        
        db.session.add(new_rule)
        db.session.commit()
        
        return jsonify({"code": 0, "msg": "复制成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"复制失败: {str(e)}"})

@bp.route('/api/warehouse/copy', methods=['POST'])
@login_required
def warehouse_copy_api():
    data = request.json
    id = data.get('id')
    
    if not id:
        return jsonify({"code": 400, "msg": "ID不能为空"})
        
    item = CollectedData.query.get(id)
    if not item:
        return jsonify({"code": 404, "msg": "数据不存在"})
        
    try:
        new_item = CollectedData(
            title=f"{item.title}_复制",
            summary=item.summary,
            source=item.source,
            original_url=item.original_url,
            cover=item.cover,
            keyword=item.keyword,
            is_deep_collected=item.is_deep_collected,
            deep_content=item.deep_content,
            deep_collected_at=item.deep_collected_at
        )
        
        db.session.add(new_item)
        db.session.flush()
        
        # Copy Detail if exists
        detail = ArticleDetail.query.filter_by(collected_data_id=item.id).first()
        if detail:
            new_detail = ArticleDetail(
                collected_data_id=new_item.id,
                title=detail.title,
                content=detail.content
            )
            db.session.add(new_detail)
            
        db.session.commit()
        return jsonify({"code": 0, "msg": "复制成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"复制失败: {str(e)}"})

@bp.route('/api/warehouse/get', methods=['GET'])
@login_required
def warehouse_get_api():
    id = request.args.get('id', type=int)
    if not id:
        return jsonify({"code": 400, "msg": "ID不能为空"})
        
    item = CollectedData.query.get(id)
    if not item:
        return jsonify({"code": 404, "msg": "数据不存在"})
    
    # Fetch detail from new table
    detail = ArticleDetail.query.filter_by(collected_data_id=item.id).first()
    content = detail.content if detail else item.deep_content # Fallback to old field if needed
    
    return jsonify({
        "code": 0,
        "msg": "success",
        "data": {
            "id": item.id,
            "title": item.title,
            "summary": item.summary,
            "source": item.source,
            "original_url": item.original_url,
            "keyword": item.keyword,
            "deep_content": content,
            "is_deep_collected": True if detail else False # Or use item.is_deep_collected
        }
    })

@bp.route('/api/warehouse/update', methods=['POST'])
@login_required
def warehouse_update_api():
    data = request.json
    id = data.get('id')
    
    if not id:
        return jsonify({"code": 400, "msg": "ID不能为空"})
        
    item = CollectedData.query.get(id)
    if not item:
        return jsonify({"code": 404, "msg": "数据不存在"})
        
    try:
        item.title = data.get('title', item.title)
        item.summary = data.get('summary', item.summary)
        item.deep_content = data.get('deep_content', item.deep_content)
        db.session.commit()
        return jsonify({"code": 0, "msg": "更新成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"更新失败: {str(e)}"})

@bp.route('/api/warehouse/analyze', methods=['POST'])
@login_required
def warehouse_analyze_api():
    # Placeholder for AI analysis
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({"code": 400, "msg": "请选择要分析的数据"})
        
    return jsonify({
        "code": 0, 
        "msg": "AI分析请求已提交（功能开发中...）",
        "data": {"task_id": "mock_task_123"}
    })

@bp.route('/api/warehouse/analyze_rules', methods=['POST'])
@login_required
def warehouse_analyze_rules_api():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({"code": 400, "msg": "请选择要分析的数据"})
        
    # 1. Fetch items
    items = CollectedData.query.filter(CollectedData.id.in_(ids)).all()
    
    # 2. Group by Source
    groups = {} # source -> { ids: [], sample_url: ... }
    for item in items:
        source = item.source or "未知来源"
        if source not in groups:
            groups[source] = {
                "ids": [],
                "sample_url": item.original_url,
                "sample_title": item.title
            }
        groups[source]["ids"].append(item.id)
        
    # 3. Match Rules & Prepare Response
    result_groups = []
    all_rules = CollectionRule.query.all()
    rules_data = [{"id": r.id, "site_name": r.site_name, "domain": r.domain} for r in all_rules]
    
    for source, data in groups.items():
        # Try to find a default rule
        matched_rule_id = None
        
        # Strategy 1: Exact Site Name Match
        for r in all_rules:
            if r.site_name == source:
                matched_rule_id = r.id
                break
                
        # Strategy 2: Domain Match (if no exact name match)
        if not matched_rule_id and data['sample_url']:
            try:
                domain = urlparse(data['sample_url']).netloc
                for r in all_rules:
                    if r.domain and r.domain in domain:
                        matched_rule_id = r.id
                        break
            except:
                pass
                
        result_groups.append({
            "source": source,
            "count": len(data['ids']),
            "ids": data['ids'],
            "sample_title": data['sample_title'],
            "suggested_rule_id": matched_rule_id
        })
        
    return jsonify({
        "code": 0,
        "msg": "success",
        "data": {
            "groups": result_groups,
            "rules": rules_data
        }
    })

@bp.route('/api/warehouse/collect_detail', methods=['POST'])
@login_required
def warehouse_collect_detail_api():
    # Supports two formats:
    # 1. Legacy: { "ids": [1, 2, 3] } -> Auto-match
    # 2. New: { "tasks": [ { "ids": [1,2], "rule_id": 10 }, ... ] } -> Explicit
    
    data = request.json
    tasks = data.get('tasks')
    
    success_count = 0
    fail_count = 0
    errors = []
    
    # Normalize to list of tasks
    normalized_tasks = []
    
    if tasks:
        normalized_tasks = tasks
    else:
        ids = data.get('ids', [])
        if not ids:
            return jsonify({"code": 400, "msg": "请选择要采集的数据"})
        # Legacy mode: treat as one task with no explicit rule (auto-match)
        normalized_tasks.append({"ids": ids, "rule_id": None})
        
    for task in normalized_tasks:
        task_ids = task.get('ids', [])
        rule_id = task.get('rule_id')
        
        # Pre-fetch rule if specified
        explicit_rule = None
        if rule_id:
            explicit_rule = CollectionRule.query.get(rule_id)
            
        items = CollectedData.query.filter(CollectedData.id.in_(task_ids)).all()
        
        for item in items:
            rule = explicit_rule
            
            # If no explicit rule, try auto-match
            if not rule:
                rule = CollectionRule.query.filter_by(site_name=item.source).first()
                # Fallback to domain match if needed? 
                # For now, keep legacy behavior strict on site_name or improve it:
                if not rule and item.original_url:
                     try:
                        domain = urlparse(item.original_url).netloc
                        rule = CollectionRule.query.filter(CollectionRule.domain.like(f"%{domain}%")).first()
                     except:
                        pass

            if not rule:
                errors.append(f"ID {item.id} ({item.source}): 未找到匹配规则且未指定规则")
                fail_count += 1
                continue
                
            try:
                # Fetch and parse
                result = _fetch_and_parse_detail(item.original_url, rule)
                if result:
                    # Save to ArticleDetail table
                    detail = ArticleDetail.query.filter_by(collected_data_id=item.id).first()
                    if not detail:
                        detail = ArticleDetail(collected_data_id=item.id)
                        db.session.add(detail)
                    
                    detail.title = result.get('title') or item.title
                    detail.content = result.get('content')
                    
                    # Update CollectedData status
                    item.is_deep_collected = True
                    item.deep_collected_at = datetime.utcnow()
                    
                    # Optionally update title
                    new_title = result.get('title')
                    if new_title:
                        item.title = new_title
                        
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append(f"ID {item.id}: 采集失败，未获取到内容")
            except Exception as e:
                fail_count += 1
                errors.append(f"ID {item.id}: {str(e)}")
            
    try:
        db.session.commit()
        msg = f"成功采集 {success_count} 条"
        if fail_count > 0:
            msg += f"，失败 {fail_count} 条"
        return jsonify({
            "code": 0 if fail_count == 0 else 1,
            "msg": msg,
            "errors": errors
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"保存失败: {str(e)}"})

# --- Collection Rule Library APIs ---

@bp.route('/rules')
@login_required
def rules_page():
    return render_template('crawler/rules.html')

@bp.route('/api/rules', methods=['GET'])
@login_required
def rules_list_api():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    
    query = CollectionRule.query.order_by(CollectionRule.created_at.desc())
    
    pagination = query.paginate(page=page, per_page=limit, error_out=False)
    
    data = []
    for item in pagination.items:
        data.append({
            "id": item.id,
            "site_name": item.site_name,
            "domain": item.domain,
            "title_xpath": item.title_xpath,
            "content_xpath": item.content_xpath,
            "headers": item.headers,
            "created_at": item.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "updated_at": item.updated_at.strftime('%Y-%m-%d %H:%M:%S') if item.updated_at else None
        })
        
    return jsonify({
        "code": 0,
        "msg": "",
        "count": pagination.total,
        "data": data
    })

@bp.route('/api/rules', methods=['POST'])
@login_required
def rules_create_api():
    data = request.json
    site_name = data.get('site_name')
    
    if not site_name:
        return jsonify({"code": 400, "msg": "站点名称不能为空"})
        
    existing = CollectionRule.query.filter_by(site_name=site_name).first()
    if existing:
        return jsonify({"code": 400, "msg": "该站点规则已存在"})
        
    try:
        new_rule = CollectionRule(
            site_name=site_name,
            domain=data.get('domain'),
            title_xpath=data.get('title_xpath'),
            content_xpath=data.get('content_xpath'),
            headers=_process_headers(data.get('headers'))
        )
        db.session.add(new_rule)
        db.session.commit()
        return jsonify({"code": 0, "msg": "创建成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"创建失败: {str(e)}"})

@bp.route('/api/rules/<int:id>', methods=['GET'])
@login_required
def rules_get_api(id):
    rule = CollectionRule.query.get_or_404(id)
    return jsonify({
        "code": 0,
        "msg": "success",
        "data": {
            "id": rule.id,
            "site_name": rule.site_name,
            "domain": rule.domain,
            "title_xpath": rule.title_xpath,
            "content_xpath": rule.content_xpath,
            "headers": rule.headers
        }
    })

@bp.route('/api/rules', methods=['PUT'])
@login_required
def rules_update_api():
    data = request.json
    id = data.get('id')
    
    if not id:
        return jsonify({"code": 400, "msg": "ID不能为空"})
        
    rule = CollectionRule.query.get(id)
    if not rule:
        return jsonify({"code": 404, "msg": "规则不存在"})
        
    try:
        rule.site_name = data.get('site_name', rule.site_name)
        rule.domain = data.get('domain', rule.domain)
        rule.title_xpath = data.get('title_xpath', rule.title_xpath)
        rule.content_xpath = data.get('content_xpath', rule.content_xpath)
        if 'headers' in data:
            rule.headers = _process_headers(data.get('headers'))
        
        db.session.commit()
        return jsonify({"code": 0, "msg": "更新成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"更新失败: {str(e)}"})

@bp.route('/api/rules', methods=['DELETE'])
@login_required
def rules_delete_api():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({"code": 400, "msg": "请选择要删除的规则"})
        
    try:
        CollectionRule.query.filter(CollectionRule.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({"code": 0, "msg": "删除成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"删除失败: {str(e)}"})
