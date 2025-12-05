import requests
from bs4 import BeautifulSoup
from lxml import etree
from urllib.parse import urljoin, urlparse
import re
import urllib3
import json
from app.models import CollectionRule

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class XinhuaCrawler:
    def __init__(self):
        self.base_url = "http://sc.news.cn/scyw.htm"
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
            "Referer": "http://sc.news.cn/"
        }
        self.session = requests.Session()
        self.session.headers.update(self.default_headers)
        
        # 增加重试机制
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _get_rule_headers(self, rule_headers):
        if not rule_headers:
            return {}
        try:
            return json.loads(rule_headers)
        except:
            # Try parsing line by line "Key: Value"
            headers = {}
            for line in rule_headers.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
            return headers

    def fetch_news(self, limit=None):
        """
        采集新华网四川要闻
        """
        try:
            response = self.session.get(self.base_url, timeout=10, verify=False)
            response.encoding = 'utf-8'
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # 查找所有链接
            links = soup.find_all('a')
            
            # 日期正则
            date_pattern = re.compile(r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})')
            
            for link in links:
                text = link.get_text(strip=True)
                href = link.get('href')
                
                if not href or not text:
                    continue
                    
                # 检查是否包含日期
                match = date_pattern.search(text)
                if match:
                    date_str = match.group(1)
                    # 标题通常是日期前面的部分
                    title = text.replace(date_str, '').strip()
                    
                    # 处理相对URL
                    full_url = urljoin(self.base_url, href)
                    
                    # 尝试获取摘要（有些新闻列表会有摘要在链接附近，这里简化处理）
                    summary = title # 默认摘要同标题
                    
                    # 尝试获取封面（如果有img标签在a标签内）
                    img = link.find('img')
                    cover = ""
                    if img:
                        cover = urljoin(self.base_url, img.get('src'))
                    
                    results.append({
                        "title": title,
                        "summary": summary,
                        "cover": cover,
                        "original_url": full_url,
                        "source": "新华网",
                        "publish_time": date_str
                    })
            
            # 去重
            unique_results = []
            seen_urls = set()
            for item in results:
                if item['original_url'] not in seen_urls and len(item['title']) > 5:
                    seen_urls.add(item['original_url'])
                    unique_results.append(item)
            
            if limit:
                return unique_results[:limit]
            
            return unique_results
            
        except Exception as e:
            print(f"Error during Xinhua crawling: {e}")
            return []

    def deep_collect(self, url):
        """
        深度采集：获取URL正文内容
        """
        try:
            # 尝试查找匹配的规则
            domain = urlparse(url).netloc
            # remove www. or other prefix if needed, but for now strict match or contains
            # Let's try to find a rule where the rule's domain is in the URL's domain
            rule = None
            try:
                # Check for exact domain match or if rule domain is part of url domain
                # This is a bit simplistic, might need better matching logic
                rules = CollectionRule.query.all()
                for r in rules:
                    if r.domain and r.domain in domain:
                        rule = r
                        break
            except Exception as db_err:
                print(f"Warning: Could not query rules: {db_err}")
            
            # Apply headers from rule if available
            request_headers = self.default_headers.copy()
            if rule and rule.headers:
                custom_headers = self._get_rule_headers(rule.headers)
                request_headers.update(custom_headers)

            response = self.session.get(url, headers=request_headers, timeout=15, verify=False)
            response.raise_for_status()
            response.encoding = response.apparent_encoding # 自动检测编码
            
            content = ""
            publish_time = ""

            # Use Rule XPath if available
            if rule and (rule.content_xpath or rule.title_xpath):
                html = etree.HTML(response.text)
                
                if rule.content_xpath:
                    try:
                        # XPath returns a list of elements or strings
                        content_elements = html.xpath(rule.content_xpath)
                        if content_elements:
                            # Join text from all matched elements
                            if isinstance(content_elements[0], str): # xpath returned string
                                content = "\n".join([str(c).strip() for c in content_elements])
                            else: # xpath returned elements
                                content = "\n".join([elem.xpath('string(.)').strip() for elem in content_elements])
                    except Exception as xpath_err:
                        print(f"XPath error for content: {xpath_err}")

                # If content found via xpath, we are good. If not, fall back to auto extraction.
            
            # Fallback to auto extraction if no content found via rule
            if not content:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 移除无关标签
                for tag in soup(["script", "style", "iframe", "noscript", "svg"]):
                    tag.extract()
                
                # 提取发布时间 (如果列表页没获取到，或者需要更精确)
                time_elem = soup.select_one('.h-p2 .h-time, .info, .time')
                if time_elem:
                    publish_time = time_elem.get_text(strip=True)
                
                # 提取正文
                article = soup.select_one('#p-detail, .main-content, .article')
                if article:
                    content = article.get_text(separator='\n', strip=True)
                else:
                    # 降级策略
                    paragraphs = soup.find_all('p')
                    valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 10]
                    content = '\n\n'.join(valid_paragraphs)
                
            return {
                "content": content[:5000],
                "publish_time": publish_time
            }
            
        except Exception as e:
            print(f"Error during deep collection: {e}")
            return {"content": f"深度采集失败: {str(e)}", "publish_time": ""}
