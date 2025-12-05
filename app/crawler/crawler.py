import json
import requests
from bs4 import BeautifulSoup
from lxml import html as lxml_html
from urllib.parse import urlparse
import urllib3
from app.models import CollectionRule, CrawlerSource
import importlib
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.crawler.baidu import BaiduCrawler
from app.crawler.xinhua import XinhuaCrawler

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CrawlerService:
    def __init__(self):
        self.baidu = BaiduCrawler()
        self.xinhua = XinhuaCrawler()
        self.registry = {
            'baidu': self.baidu,
            'xinhua': self.xinhua
        }
        self._load_db_sources()

    def _load_db_sources(self):
        try:
            sources = CrawlerSource.query.filter_by(enabled=True).all()
            for s in sources:
                try:
                    if s.module and s.module != 'generic':
                        module = importlib.import_module(s.module)
                        cls = getattr(module, s.class_name)
                        instance = cls()
                        if hasattr(instance, 'configure'):
                            cfg = {
                                'base_url': s.base_url,
                                'headers': json.loads(s.headers) if s.headers else {}
                            }
                            instance.configure(cfg)
                        self.registry[s.key] = instance
                    else:
                        instance = GenericCrawler({
                            'base_url': s.base_url,
                            'headers': json.loads(s.headers) if s.headers else {},
                            'search_url': s.search_url,
                            'search_method': s.search_method or 'GET',
                            'search_params': json.loads(s.search_params) if s.search_params else {},
                            'search_headers': json.loads(s.search_headers) if s.search_headers else {},
                            'result_is_json': bool(s.result_is_json),
                            'result_item_xpath': s.result_item_xpath,
                            'field_map': json.loads(s.field_map) if s.field_map else {},
                            'deep_headers': json.loads(s.deep_headers) if s.deep_headers else {}
                        })
                        self.registry[s.key] = instance
                except Exception:
                    continue
        except Exception:
            pass

    def search(self, keyword, source='baidu', pages=1, limit=None):
        self._load_db_sources()
        crawler = self.registry.get(source)
        if not crawler:
            return []
        # Support both unified search and xinhua-specific fetch_news
        if hasattr(crawler, 'search'):
            try:
                return crawler.search(keyword, pages=pages)
            except TypeError:
                return crawler.search(keyword)
        if hasattr(crawler, 'fetch_news'):
            all_results = crawler.fetch_news(limit=None)
            filtered = [r for r in all_results if (keyword in r.get('title', '') or keyword in r.get('summary', ''))] if keyword else all_results
            final_limit = limit if limit else 20
            return filtered[:final_limit]
        return []

    def deep_collect(self, url):
        # Try domain-based mapping first among registered crawlers
        self._load_db_sources()
        result = None
        for key, crawler in self.registry.items():
            try:
                if hasattr(crawler, 'can_handle') and crawler.can_handle(url):
                    result = crawler.deep_collect(url)
                    break
            except Exception:
                continue
        if result is None:
            if 'news.cn' in url or 'xinhuanet' in url:
                result = self.xinhua.deep_collect(url)
            else:
                result = self.baidu.deep_collect(url)
        content = result.get('content', '') if isinstance(result, dict) else ''
        if not content or len(content) < 20:
            fallback = self.extract_detail_fallback(url)
            if fallback:
                return fallback
        return result

    def extract_detail_fallback(self, url):
        rule = self._get_rule_for_url(url)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if rule and rule.headers:
            try:
                custom = json.loads(rule.headers)
                if isinstance(custom, dict):
                    headers.update(custom)
            except:
                pass
        try:
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            resp.encoding = resp.apparent_encoding
            if resp.status_code != 200:
                return {"content": "", "publish_time": ""}
            tree = lxml_html.fromstring(resp.content)
            title = ""
            if rule and rule.title_xpath:
                try:
                    titles = tree.xpath(rule.title_xpath)
                    if titles:
                        if isinstance(titles[0], str):
                            title = titles[0].strip()
                        else:
                            title = titles[0].text_content().strip()
                except:
                    pass
            if not title:
                try:
                    h1s = tree.xpath('//h1')
                    if h1s:
                        title = h1s[0].text_content().strip()
                except:
                    pass
            content = ""
            if rule and rule.content_xpath:
                try:
                    els = tree.xpath(rule.content_xpath)
                    if els:
                        if isinstance(els[0], str):
                            content = "\n".join([str(c).strip() for c in els])
                        else:
                            content = "\n".join([e.text_content().strip() for e in els])
                except:
                    pass
            if not content or len(content) < 20:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for t in soup(["script", "style", "iframe", "noscript", "svg"]):
                    t.extract()
                selectors = [
                    'article', '.article', '.post', '.content', '.main-content',
                    '.news-content', '.article-content', '#content', '.detail-content',
                    '.txt', '.text'
                ]
                block = None
                for sel in selectors:
                    block = soup.select_one(sel)
                    if block and len(block.get_text(strip=True)) > 20:
                        break
                if block:
                    content = block.get_text(separator='\n', strip=True)
                else:
                    paras = soup.find_all('p')
                    valid = [p.get_text(strip=True) for p in paras if len(p.get_text(strip=True)) > 10]
                    content = '\n\n'.join(valid)
            return {"content": content[:5000], "publish_time": "", "title": title}
        except Exception:
            return {"content": "", "publish_time": ""}

    def _get_rule_for_url(self, url):
        try:
            domain = urlparse(url).netloc
            rules = CollectionRule.query.all()
            for r in rules:
                if r.domain and r.domain in domain:
                    return r
        except Exception:
            return None
        return None

class GenericCrawler:
    def __init__(self, config):
        self.cfg = config or {}
    def configure(self, cfg):
        self.cfg.update(cfg or {})
    def search(self, keyword, pages=1):
        url = self.cfg.get('search_url') or ''
        if not url:
            return []
        headers = {}
        headers.update(self.cfg.get('headers') or {})
        headers.update(self.cfg.get('search_headers') or {})
        params = dict(self.cfg.get('search_params') or {})
        for k, v in list(params.items()):
            if isinstance(v, str):
                v = v.replace('{keyword}', keyword).replace('{page}', str(pages))
                params[k] = v
        method = (self.cfg.get('search_method') or 'GET').upper()
        try:
            if method == 'POST':
                resp = requests.post(url, headers=headers, data=params, timeout=15, verify=False)
            else:
                resp = requests.get(url, headers=headers, params=params, timeout=15, verify=False)
            resp.encoding = resp.apparent_encoding
            if self.cfg.get('result_is_json', True):
                data = resp.json()
                items = data
                fm = self.cfg.get('field_map') or {}
                if isinstance(data, dict) and fm.get('items_key'):
                    items = data.get(fm.get('items_key')) or []
                results = []
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    results.append({
                        'title': it.get(fm.get('title')) if fm.get('title') else it.get('title'),
                        'summary': it.get(fm.get('summary')) if fm.get('summary') else it.get('summary'),
                        'source': self.cfg.get('source_name') or '',
                        'original_url': it.get(fm.get('original_url')) if fm.get('original_url') else it.get('url'),
                        'publish_time': it.get(fm.get('publish_time')) if fm.get('publish_time') else it.get('publish_time'),
                        'cover': it.get(fm.get('cover')) if fm.get('cover') else it.get('cover')
                    })
                return results
            else:
                tree = lxml_html.fromstring(resp.content)
                item_xpath = self.cfg.get('result_item_xpath')
                if not item_xpath:
                    return []
                nodes = tree.xpath(item_xpath)
                fm = self.cfg.get('field_map') or {}
                results = []
                for n in nodes:
                    def xp(x):
                        arr = n.xpath(x) if x else []
                        if not arr:
                            return ''
                        v = arr[0]
                        return v if isinstance(v, str) else v.text_content().strip()
                    cover_val = xp(fm.get('cover_xpath'))
                    if not cover_val:
                        attrs = n.xpath('.//img/@src | .//img/@data-src | .//img/@data-actualsrc | .//img/@data-thumb | .//img/@data-url | .//img/@srcset')
                        if attrs:
                            cover_val = str(attrs[0]).split(' ')[0]
                            if cover_val.startswith('//'):
                                cover_val = 'https:' + cover_val
                            if self.cfg.get('base_url') and cover_val and not cover_val.startswith('http'):
                                try:
                                    from urllib.parse import urljoin
                                    cover_val = urljoin(self.cfg.get('base_url'), cover_val)
                                except:
                                    pass
                    results.append({
                        'title': xp(fm.get('title_xpath')),
                        'summary': xp(fm.get('summary_xpath')),
                        'source': self.cfg.get('source_name') or '',
                        'original_url': xp(fm.get('url_xpath')),
                        'publish_time': xp(fm.get('time_xpath')),
                        'cover': cover_val
                    })
                return results
        except Exception:
            return []
    def deep_collect(self, url):
        headers = {}
        headers.update(self.cfg.get('headers') or {})
        headers.update(self.cfg.get('deep_headers') or {})
        try:
            headers.setdefault("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
            headers.setdefault("Accept-Language", "zh-CN,zh;q=0.9")
            headers.setdefault("Cache-Control", "no-cache")
            try:
                u = urlparse(url)
                headers.setdefault("Referer", f"{u.scheme}://{u.netloc}/")
            except:
                pass
            session = requests.Session()
            retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[429,500,502,503,504])
            adapter = HTTPAdapter(max_retries=retry)
            session.mount('https://', adapter)
            session.mount('http://', adapter)
            resp = session.get(url, headers=headers, timeout=15, verify=False, allow_redirects=True)
            resp.encoding = resp.apparent_encoding
            if resp.status_code != 200 or ('wappass.baidu.com' in (resp.url or '')) or ('captcha' in (resp.text or '').lower()):
                try:
                    proxy_url = 'https://r.jina.ai/http://' + url.split('://', 1)[1]
                    r2 = requests.get(proxy_url, timeout=15)
                    if r2.status_code == 200 and len(r2.text) > 50:
                        content = r2.text
                        return {'content': content, 'publish_time': ''}
                except:
                    pass
            tree = lxml_html.fromstring(resp.content)
            content = tree.text_content().strip()
            if not content or len(content) < 20:
                bs = BeautifulSoup(resp.text, 'html.parser')
                for t in bs(["script","style","iframe","noscript","svg"]):
                    t.extract()
                paras = bs.find_all('p')
                valid = [p.get_text(strip=True) for p in paras if len(p.get_text(strip=True)) > 10]
                content = '\n\n'.join(valid)
            return {'content': content, 'publish_time': ''}
        except Exception:
            return {'content': '', 'publish_time': ''}
