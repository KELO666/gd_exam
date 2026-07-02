#!/usr/bin/env python3
"""GitHub Actions 独立爬虫脚本"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.scheduler import scrape_and_notify

if __name__ == "__main__":
    print("🚀 [GitHub Actions] 开始执行爬虫与推送任务...")
    scrape_and_notify()
    print("✅ 任务执行完毕")
