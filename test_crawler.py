import sys
import os
import requests
sys.path.append(os.getcwd())
from app.crawler.baidu import BaiduCrawler

def test():
    print("开始测试爬虫，关键字：北京")
    crawler = BaiduCrawler()
    # 保存 HTML 以供调试
    try:
        response = crawler.session.get(crawler.base_url, params={"wd": "北京"}, timeout=10)
        with open("debug_baidu.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("HTML 已保存到 debug_baidu.html")
    except Exception as e:
        print(f"获取调试HTML失败: {e}")

    results = crawler.search('北京')
    print(f"共找到 {len(results)} 条结果：")
    print("-" * 50)
    for i, res in enumerate(results, 1):
        print(f"[{i}] {res['title']}")
        print(f"    链接: {res['original_url']}")
        print(f"    来源: {res['source']}")
        print(f"    摘要: {res['summary'][:50]}...")
        print("-" * 50)

if __name__ == "__main__":
    test()
