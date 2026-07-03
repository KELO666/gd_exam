#!/bin/bash

PROJECT_DIR="/Users/jc/Documents/AI_Coding/考公资讯助手"

# 自动加载环境变量
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

cd "$PROJECT_DIR"

# 优先使用系统级别的 python3，确保定时任务能在无交互环境下运行
/usr/local/bin/python3 backend/run_scraper.py >> /tmp/gd_scraper.log 2>&1
