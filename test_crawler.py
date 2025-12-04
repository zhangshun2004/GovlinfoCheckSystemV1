import sys
import os
import requests
sys.path.append(os.getcwd())
from app.crawler.baidu import BaiduCrawler

def test():
    print("开始测试爬虫，关键字：成都")
    crawler = BaiduCrawler()
    
    try:
        results = crawler.search('成都')
        print(f"共找到 {len(results)} 条结果：")
        print("-" * 50)
        for i, res in enumerate(results, 1):
            print(f"[{i}] {res['title']}")
            print(f"    链接: {res['original_url']}")
            print(f"    来源: {res['source']}")
            print(f"    摘要: {res['summary'][:50]}...")
            print("-" * 50)
    except Exception as e:
        print(f"测试出错: {e}")

if __name__ == "__main__":
    test()
