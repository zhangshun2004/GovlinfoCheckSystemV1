import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urlparse
import urllib3
import json
from lxml import etree
from app.models import CollectionRule

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class BaiduCrawler:
    def __init__(self):
        self.base_url = "https://www.baidu.com/s"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.97 Safari/537.36 Core/1.116.586.400 QQBrowser/19.8.6883.400",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Not)A;Brand";v="24", "Chromium";v="116"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Cookie": "BIDUPSID=D48AC21A701043225723F7B0416A45A5; PSTM=1749868400; BD_UPN=1a314753; BAIDUID=D48AC21A70104322974B66FAE2F73383:SL=0:NR=10:FG=1; MAWEBCUID=web_YJdcNWbgVAvBDdOlAjnOFGURksbLStlKretXHCZPDmkKBoCWao; MCITY=-75%3A; newlogin=1; BDUSS=Bsb0RmVWp3c0NmMHNwOVpnVTZpSUU1Rn5IU1c1S29EVVJQYVI0ZWFnWEhDazVwSVFBQUFBJCQAAAAAAAAAAAEAAACr7QECeWFuZ2FodWkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMd9JmnHfSZpNX; BDUSS_BFESS=Bsb0RmVWp3c0NmMHNwOVpnVTZpSUU1Rn5IU1c1S29EVVJQYVI0ZWFnWEhDazVwSVFBQUFBJCQAAAAAAAAAAAEAAACr7QECeWFuZ2FodWkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMd9JmnHfSZpNX; BAIDUID_BFESS=D48AC21A70104322974B66FAE2F73383:SL=0:NR=10:FG=1; H_WISE_SIDS_BFESS=60272_63144_66104_66109_66213_66232_66288_66271_66393_66510_66516_66529_66552_66589_66591_66601_66606_66652_66671_66669_66694_66685_66599_66720_66744_66623; __bid_n=19ad5be04673728d3e48c8; PAD_BROWSER=1; ZFY=:BbjM:A1IBjzvZvV4stKekEFIixozKxmgJlX2ZrIwt9J0:C; Hm_lvt_aec699bb6442ba076c8981c6dc490771=1764321838,1764467635,1764522517,1764723037; COOKIE_SESSION=61096_0_9_9_12_35_1_3_9_8_0_1_61094_0_4_0_1764723038_0_1764723034%7C9%2325100_26_1764063190%7C9; sug=3; sugstore=0; ORIGIN=0; bdime=0; pcMainBoxRec=1; BA_HECTOR=2085a1248g0l2h2g2h8g0024ah8g231kivn4c24; H_WISE_SIDS=60272_63144_66104_66109_66213_66232_66288_66271_66393_66510_66516_66529_66552_66589_66591_66601_66606_66652_66671_66669_66694_66685_66720_66744_66623_66772_66787_66792_66747; BDRCVFR[feWj1Vr5u3D]=I67x6TjHwwYf0; BD_CK_SAM=1; PSINO=6; delPer=0; BDORZ=B490B5EBF6F3CD402E515D22BCDA1598; baikeVisitId=bfa83e0b-e066-4f40-86a1-bcc26822fba9; SMARTINPUT=1; arialoadData=false; BDRCVFR[C0p6oIjvx-c]=mk3SLVN4HKm; H_PS_PSSID=60272_63144_66104_66109_66213_66232_66288_66271_66393_66510_66516_66529_66552_66589_66591_66601_66606_66652_66671_66669_66694_66685_66720_66744_66623_66772_66787_66792_66747_66806_66799_66599; BDSVRTM=518"
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

    def search(self, keyword, pages=1):
        all_results = []
        for page in range(pages):
            pn = page * 10
            # Updated parameters for Baidu News Search
            params = {
                "rtt": "1",
                "bsst": "1",
                "cl": "2",
                "tn": "news",
                "rsv_dl": "ns_pc",
                "word": keyword,
                "pn": pn
            }
            
            try:
                # Use headers defined in __init__ which now includes the specific Cookie and User-Agent
                response = self.session.get(self.base_url, params=params, timeout=10, verify=False)
                response.raise_for_status()
                results = self._parse_results(response.text)
                all_results.extend(results)
            except Exception as e:
                print(f"Error during crawling page {page+1}: {e}")
                
        return all_results

    def deep_collect(self, url):
        """
        深度采集：获取URL正文内容及元数据
        支持 CollectionRule 规则匹配
        """
        try:
            # 处理百度跳转链接
            real_url = self._resolve_baidu_link(url)
            
            # 尝试查找匹配的规则
            domain = urlparse(real_url).netloc
            rule = None
            try:
                # Check for exact domain match or if rule domain is part of url domain
                rules = CollectionRule.query.all()
                for r in rules:
                    if r.domain and r.domain in domain:
                        rule = r
                        break
            except Exception as db_err:
                # 可能是上下文问题，或者数据库错误，忽略并使用默认采集
                print(f"Warning: Could not query rules: {db_err}")

            # Apply headers from rule if available
            request_headers = self.headers.copy()
            if rule and rule.headers:
                custom_headers = self._get_rule_headers(rule.headers)
                request_headers.update(custom_headers)

            response = self.session.get(real_url, headers=request_headers, timeout=15, verify=False)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            content = ""
            publish_time = ""

            # Use Rule XPath if available
            if rule and (rule.content_xpath or rule.title_xpath):
                try:
                    html = etree.HTML(response.text)
                    
                    if rule.content_xpath:
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

            # Always try to extract publish time (auto-extraction) since Rule doesn't support it yet
            # And fallback for content if Rule failed
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 移除无关标签
            for tag in soup(["script", "style", "iframe", "noscript", "svg"]):
                tag.extract()
            
            # 尝试提取发布时间
            if not publish_time:
                time_selectors = [
                    'meta[property="article:published_time"]',
                    'meta[name="pubdate"]',
                    '.date', '.time', '.pub-time', '.publish-time'
                ]
                for selector in time_selectors:
                    if selector.startswith('meta'):
                        meta = soup.select_one(selector)
                        if meta:
                            publish_time = meta.get('content')
                            break
                    else:
                        elem = soup.select_one(selector)
                        if elem:
                            publish_time = elem.get_text(strip=True)
                            break

            # Fallback to auto extraction if no content found via rule
            if not content:
                # 尝试提取正文 - 增强版
                # 1. 常见文章容器
                article_selectors = [
                    'article', '.article', '.post', '.content', '.main-content', 
                    '.news-content', '.article-content', '#content', '.detail-content',
                    '.txt', '.text'
                ]
                
                article = None
                for selector in article_selectors:
                    article = soup.select_one(selector)
                    if article and len(article.get_text(strip=True)) > 50:
                        break
                
                if article:
                    # 再次清洗正文中的无关链接等
                    content = article.get_text(separator='\n', strip=True)
                else:
                    # 2. 统计段落文本密度
                    paragraphs = soup.find_all('p')
                    valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 10]
                    content = '\n\n'.join(valid_paragraphs)
                
                # 如果还是太短，尝试获取所有body文本
                if len(content) < 50:
                    content = soup.body.get_text(separator='\n', strip=True) if soup.body else ""

            result = {
                "content": content[:5000],  # 限制长度防止过大
                "publish_time": publish_time
            }
            return result
            
        except Exception as e:
            print(f"Error during deep collection: {e}")
            return {"content": f"深度采集失败: {str(e)}", "publish_time": ""}

    def _resolve_baidu_link(self, url):
        """解析百度加密链接"""
        if "baidu.com/link" not in url:
            return url
            
        try:
            # 禁止自动跳转，手动处理
            # 有些百度链接是HTTP 302跳转
            r = self.session.get(url, allow_redirects=False, timeout=5, verify=False)
            if r.status_code == 302 or r.status_code == 301:
                return r.headers.get('Location', url)
            
            # 有些是JS跳转，通常状态码200
            if r.status_code == 200:
                import re
                # window.location.replace("http://...")
                match = re.search(r'window\.location\.replace\("([^"]+)"\)', r.text)
                if match:
                    return match.group(1)
                # content="0;url=http://..."
                match = re.search(r'content="0;url=([^"]+)"', r.text)
                if match:
                    return match.group(1)
        except Exception:
            pass
            
        return url

    def _get_source_name(self, url, original_source):
        """根据URL和原始来源获取更准确的站点名称"""
        # 优先处理原始来源，如果它看起来是有效的中文来源名
        if original_source and original_source != "百度搜索":
            # 简单的清洗
            src = original_source.strip()
            # 如果包含中文且不包含URL特征
            has_chinese = any(u'\u4e00' <= c <= u'\u9fff' for c in src)
            is_url = '.' in src and ('com' in src or 'cn' in src or 'http' in src or 'www' in src)
            
            if has_chinese and not is_url:
                return src

        if not url:
            return original_source
            
        try:
            domain = urlparse(url).netloc
            
            # 1. 尝试匹配采集规则中的站点名称
            # 注意：这里需要在应用上下文中运行，否则会报错
            # 但BaiduCrawler通常在路由中调用，所以应该没问题
            try:
                # 查找域名包含在当前URL中的规则
                rules = CollectionRule.query.all()
                for rule in rules:
                    if rule.domain and rule.domain in domain:
                        return rule.site_name
            except Exception:
                pass
                
            # 2. 常见站点映射
            domain_map = {
                "sina.com": "新浪网",
                "sohu.com": "搜狐网",
                "qq.com": "腾讯网",
                "163.com": "网易",
                "ifeng.com": "凤凰网",
                "people.com.cn": "人民网",
                "xinhuanet.com": "新华网",
                "cctv.com": "央视网",
                "thepaper.cn": "澎湃新闻",
                "jiemian.com": "界面新闻",
                "caixin.com": "财新网",
                "huanqiu.com": "环球网",
                "chinanews.com": "中国新闻网",
                "bjd.com.cn": "北京日报",
                "gov.cn": "中国政府网",
                "sc.gov.cn": "四川省政府网",
                "yibin.gov.cn": "宜宾市政府网",
                "toutiao.com": "今日头条",
                "weibo.com": "新浪微博",
                "zhihu.com": "知乎"
            }
            
            for d, name in domain_map.items():
                if d in domain:
                    return name
            
            # 3. 如果原始来源看起来是URL，尝试优化
            if original_source and ('www.' in original_source or '.com' in original_source or '.cn' in original_source):
                 # 提取主域名
                 parts = domain.split('.')
                 if len(parts) > 2:
                     return parts[-2] + '.' + parts[-1] # simple guess
                 return domain
                 
            # 4. 如果原始来源为空或通用词，且有域名，显示域名
            if (not original_source or original_source == "百度搜索") and domain:
                 return domain
                 
        except Exception as e:
            print(f"Source name extraction error: {e}")
            
        return original_source

    def _parse_results(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        # Selectors for Baidu News (and fallback to General Search)
        # News results usually have class "result-op" or "news-list_..."
        items = soup.select('.result-op, .c-container, .result')
        
        if not items:
             items = soup.select('div[class*="c-container"]')

        for item in items:
            try:
                # --- Title ---
                # News: h3.news-title_1YtI1 a
                # General: h3.t a
                title_elem = (
                    item.select_one('h3.news-title_1YtI1 a') or
                    item.select_one('h3.c-title a') or
                    item.select_one('h3.t a') or 
                    item.select_one('h3 a')
                )
                title = title_elem.get_text().strip() if title_elem else "无标题"
                
                # --- Original URL ---
                if title_elem:
                    original_url = title_elem.get('href')
                else:
                    original_url = ""

                # --- Summary ---
                # News: .news-detail_3gsKI, .c-font-normal
                summary_elem = (
                    item.select_one('.news-detail_3gsKI') or
                    item.select_one('.c-abstract') or 
                    item.select_one('.content-right_8Zs40') or 
                    item.select_one('.c-span18') or
                    item.select_one('.c-color-text') or
                    item.select_one('div[class*="content"]')
                )
                summary = summary_elem.get_text().strip() if summary_elem else "暂无概要"
                
                # --- Publish Time ---
                # News: .c-color-gray2 (usually contains "x小时前")
                time_elem = (
                    item.select_one('.c-color-gray2') or
                    item.select_one('.c-time') or
                    item.select_one('.news-time')
                )
                publish_time = time_elem.get_text().strip() if time_elem else ""

                # --- Source ---
                # News: .news-source_Xj4Dv, .c-color-gray
                source_elem = (
                    item.select_one('.news-source_Xj4Dv') or
                    item.select_one('.c-color-gray') or 
                    item.select_one('.source-name_3n0Jb') or
                    item.select_one('.c-showurl')
                )
                source_text = source_elem.get_text().strip() if source_elem else "百度资讯"
                
                # Clean source text (often contains time like "Sina 1 hour ago")
                # We only want the source name here, time is separate if possible, but user asked for "Source"
                # Usually format is "Source Name  Time"
                parts = source_text.split()
                if len(parts) > 1:
                    # Simple heuristic: first part is usually source
                    # But sometimes it is "Source Time" without clear delimiter
                    source = parts[0]
                else:
                    source = source_text
                
                # Use our helper to refine source name
                source = self._get_source_name(original_url, source)
                
                # --- Cover ---
                # News: .news-img_1VdF6 img, .c-img
                img_elem = (
                    item.select_one('.news-img_1VdF6 img') or
                    item.select_one('.c-img') or 
                    item.select_one('img')
                )
                cover = img_elem.get('src') if img_elem else ""
                
                if title and title != "无标题":
                    results.append({
                        "title": title,
                        "summary": summary,
                        "cover": cover,
                        "original_url": original_url,
                        "source": source,
                        "publish_time": publish_time
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