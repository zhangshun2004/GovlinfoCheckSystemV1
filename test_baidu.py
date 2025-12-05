import sys
import os
import time

# Add current directory to path
sys.path.append(os.getcwd())

from app.crawler.baidu import BaiduCrawler

class DebugBaiduCrawler(BaiduCrawler):
    def search(self, keyword, pages=1):
        # Copy of the search method but with saving HTML
        all_results = []
        for page in range(pages):
            pn = page * 10
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
                print(f"Requesting page {page+1}...")
                response = self.session.get(self.base_url, params=params, timeout=10, verify=False)
                print(f"Status Code: {response.status_code}")
                print(f"Response Length: {len(response.text)}")
                
                # Save HTML for inspection
                with open(f"debug_baidu_{page}.html", "w", encoding="utf-8") as f:
                    f.write(response.text)
                print(f"Saved HTML to debug_baidu_{page}.html")
                
                results = self._parse_results(response.text)
                print(f"Parsed {len(results)} results from page {page+1}")
                all_results.extend(results)
            except Exception as e:
                print(f"Error during crawling page {page+1}: {e}")
                import traceback
                traceback.print_exc()
                
        return all_results

if __name__ == "__main__":
    try:
        print("开始测试百度资讯爬虫(Debug模式)，关键字：成都")
        crawler = DebugBaiduCrawler()
        results = crawler.search("成都", pages=1)
        
        print(f"总共采集到 {len(results)} 条数据")
        
        for i, res in enumerate(results):
            print(f"\nResult {i+1}:")
            print(f"Title: {res.get('title')}")
            print(f"Source: {res.get('source')}")
            print(f"Time: {res.get('publish_time')}")
            print(f"URL: {res.get('original_url')}")
            print(f"Summary: {res.get('summary')[:50]}..." if res.get('summary') else "Summary: None")
    except Exception as e:
        print(f"测试出错: {e}")
