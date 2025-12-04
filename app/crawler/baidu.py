import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

class BaiduCrawler:
    def __init__(self):
        self.base_url = "https://www.baidu.com/s"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Host": "www.baidu.com",
            "Referer": "https://www.baidu.com/",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
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

        # 初始化访问，获取Cookies
        try:
            self.session.get("https://www.baidu.com/", timeout=5)
        except Exception:
            pass

    def fetch_content(self, url):
        """深度采集：获取页面正文"""
        if not url or not url.startswith('http'):
            return ""
        
        try:
            response = self.session.get(url, timeout=15)
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 简单提取：移除脚本和样式，提取所有文本
            for script in soup(["script", "style"]):
                script.extract()
            
            # 提取所有 p 标签文本
            paragraphs = soup.find_all('p')
            text_content = "\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 10])
            
            if not text_content:
                # 如果没找到 p 标签，尝试直接获取 body 文本
                text_content = soup.get_text(separator='\n', strip=True)
                
            return text_content[:5000] # 限制长度
            
        except Exception as e:
            print(f"Deep collect error for {url}: {e}")
            return ""
    def search(self, keyword):
        params = {
            "wd": keyword,
            "rsv_spt": "1",
            "rsv_iqid": "0xb2cda4270000990a",
            "issp": "1",
            "f": "8",
            "rsv_bp": "1",
            "rsv_idx": "2",
            "ie": "utf-8",
            "tn": "baiduhome_pg",
            "rsv_dl": "tb",
            "rsv_enter": "1",
            "rsv_sug3": "7",
            "rsv_sug1": "5",
            "rsv_sug7": "101",
            "rsv_btype": "i",
            "inputT": "1832",
            "rsv_sug4": "2565"
        }
        
        try:
            response = self.session.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            return self._parse_results(response.text)
        except Exception as e:
            print(f"Error during crawling: {e}")
            return []

    def _parse_results(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        # 尝试解析不同结构的百度搜索结果
        # 1. 传统结构：.result.c-container
        # 2. 新版结构：.new-pmd.c-container
        items = soup.select('.result.c-container, .new-pmd.c-container')
        
        if not items:
            # 尝试更宽泛的选择器，避免反爬导致的结构变化
            items = soup.select('div[class*="c-container"]')

        for item in items:
            try:
                # 标题
                title_elem = item.select_one('h3.t a, h3.c-title a')
                title = title_elem.get_text().strip() if title_elem else "无标题"
                original_url = title_elem.get('href') if title_elem else ""
                
                # 概要
                summary_elem = (
                    item.select_one('.c-abstract') or 
                    item.select_one('.content-right_8Zs40') or 
                    item.select_one('.c-span18') or
                    item.select_one('.c-color-text') or
                    item.select_one('div[class*="content"]') or
                    item.select_one('.c-font-normal')
                )
                summary = summary_elem.get_text().strip() if summary_elem else "暂无概要"
                
                # 来源
                source_elem = (
                    item.select_one('.c-color-gray.c-font-normal') or 
                    item.select_one('.source-name_3n0Jb') or
                    item.select_one('.c-showurl') or
                    item.select_one('a.c-showurl') or
                    item.select_one('.c-footer-showurl')
                )
                source = source_elem.get_text().strip() if source_elem else "百度搜索"
                
                # 封面 (百度搜索结果通常不直接包含大封面，尝试获取相关图片)
                # 这里尝试获取左侧缩略图
                img_elem = item.select_one('.c-img.c-img6') or item.select_one('img')
                cover = img_elem.get('src') if img_elem else ""
                
                if title and title != "无标题":
                    results.append({
                        "title": title,
                        "summary": summary,
                        "cover": cover,
                        "original_url": original_url,
                        "source": source
                    })
            except Exception as parse_error:
                continue
                
        return results

if __name__ == "__main__":
    # 测试爬虫
    crawler = BaiduCrawler()
    results = crawler.search("宜宾")
    for res in results:
        print(res)
