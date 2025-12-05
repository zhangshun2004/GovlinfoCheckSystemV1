import sys
import os
from urllib.parse import urlparse

# Add current directory to path
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from app.models import CollectionRule
from app.crawler.baidu import BaiduCrawler

def test_deep_collect():
    app = create_app()
    with app.app_context():
        # 1. Define the target URL
        target_url = "https://www.scpublic.cn/news/getNewsDatail?id=850087"
        domain = "scpublic.cn"
        
        # 2. Create or Update the CollectionRule
        print(f"Checking for existing rule for domain: {domain}")
        rule = CollectionRule.query.filter(CollectionRule.domain.like(f"%{domain}%")).first()
        
        if not rule:
            print("Creating new collection rule...")
            rule = CollectionRule(
                site_name="四川发布",
                domain=domain,
                title_xpath='//div[contains(@class, "title")]/text()',
                content_xpath='//div[@class="article"]',
                headers=None # No special headers needed based on curl test
            )
            db.session.add(rule)
            db.session.commit()
            print(f"Rule created with ID: {rule.id}")
        else:
            print(f"Updating existing rule ID: {rule.id}")
            rule.title_xpath = '//div[contains(@class, "title")]/text()'
            rule.content_xpath = '//div[@class="article"]'
            db.session.commit()
            
        # 3. Perform Deep Collection
        print(f"\nStarting deep collection for: {target_url}")
        crawler = BaiduCrawler()
        result = crawler.deep_collect(target_url)
        
        # 4. Output Results
        print("\n--- Deep Collection Result ---")
        print(f"Publish Time: {result.get('publish_time')}")
        print(f"Content Length: {len(result.get('content', ''))}")
        print("Content Preview (first 200 chars):")
        print(result.get('content', '')[:200])
        
        if "施小琳主持召开省政府常务会议" in result.get('content', ''):
            print("\n[SUCCESS] Content verification passed: Key phrase found.")
        else:
            print("\n[WARNING] Content verification: Key phrase NOT found.")

if __name__ == "__main__":
    test_deep_collect()
