import os
import json
import logging
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Header, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from models import init_db, query_notices, get_connection, _from_json_list
from core.major_mapping import map_majors_to_disciplines
from scheduler import scrape_and_notify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="广东考编情报聚合系统", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/notices")
def get_notices(
    category: str | None = Query(None, description="分类过滤"),
    major_category: str | None = Query(None, description="专业大类精确匹配（兼容旧版）"),
    major_name: str | None = Query(None, description="具体专业筛选"),
    is_unlimited: bool | None = Query(None, description="仅看三不限岗位"),
    skip_expired: bool = Query(True, description="是否过滤已过期公告"),
):
    rows = query_notices(
        category=category,
        major_category=major_category,
        skip_expired=skip_expired,
        major_name=major_name,
        is_unlimited=is_unlimited,
    )
    return {"total": len(rows), "data": rows}


@app.get("/api/filters")
def get_filters():
    # 极简模式：直接写死静态树，屏蔽所有动态脏数据
    return {
        "major_tree": {
            "农学大类": [
                "农学", "农业管理", "农村发展", "园艺学", "植物保护",
                "农业资源与环境", "动物科学", "动物医学", "林学", "水产养殖学"
            ],
            "管理学大类": [
                "管理学", "行政管理", "公共事业管理", "工商管理",
                "会计学", "财务管理", "人力资源管理", "审计学", "工程管理"
            ]
        }
    }


@app.get("/api/cron/scrape")
def trigger_scrape(background_tasks: BackgroundTasks, authorization: str = Header(None)):
    """受密钥保护的 Serverless Cron 触发接口"""
    expected_secret = os.getenv("CRON_SECRET", "dev_secret")
    if not authorization or authorization != f"Bearer {expected_secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(scrape_and_notify)
    return {"status": "ok", "message": "Scraping task triggered in background."}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")
