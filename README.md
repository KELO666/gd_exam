# 广东考编情报站

公务员 / 事业编 / 编外人员 · 招聘公告实时聚合平台

## 项目简介

一站式广东考编信息聚合工具，自动抓取事业单位招聘公告，通过 DeepSeek 大模型智能提取报名截止日期、专业要求等关键信息，支持按分类、专业、三不限等多维度筛选。

## 功能特性

- **双源爬取**：sydw1（广东事业单位招聘网）+ qgsydw（全国事业单位招聘网），自动抓取并入库
- **LLM 智能提取**：接入 DeepSeek-V3，自动提取报名截止日期、是否三不限、具体专业名称
- **本地字典映射**：特征词子串匹配，将具体专业自动归类到学科门类（农学、管理学等）
- **逾期自动过滤**：超过截止日期的公告自动隐藏
- **宽屏网格布局**：PC 端三列卡片流，移动端自适应单列
- **专业下拉筛选**：`<optgroup>` 树状分组，按学科门类组织具体专业
- **Serverless 部署**：支持 Vercel/Render 等无服务器环境，数据持久化至 Turso 云端

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+ / FastAPI / SQLite (LibSQL) |
| 前端 | Vue 3 / TailwindCSS / CDN 零构建 |
| AI | DeepSeek-V3 (硅基流动) / OpenAI 兼容接口 |
| 部署 | Vercel / GitHub Actions / Turso Serverless DB |

## 快速开始

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example backend/.env
# 编辑 backend/.env，填入 DEEPSEEK_API_KEY 等配置

# 启动服务
cd backend && python3 -m uvicorn main:app --reload --port 8000

# 浏览器打开 http://localhost:8000
```

### 手动爬取

```bash
cd backend && python3 scraper.py
```

## 项目结构

```
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 环境变量配置
│   ├── models.py            # 数据库模型与查询
│   ├── scraper.py           # 爬虫引擎
│   ├── llm_processor.py     # DeepSeek LLM 提取
│   ├── notifier.py          # 邮件推送
│   ├── scheduler.py         # 定时调度（本地用）
│   ├── run_scraper.py       # GitHub Actions 爬虫脚本
│   ├── core/
│   │   └── major_mapping.py # 专业→学科门类特征词映射
│   └── scripts/             # 数据回洗/穿透脚本
├── frontend/
│   └── index.html           # Vue3 单页应用
├── .github/workflows/
│   └── scraper.yml          # GitHub Actions 定时爬虫
├── vercel.json              # Vercel 部署配置
├── requirements.txt         # Python 依赖
└── DEV_LOG.md               # 开发日志
```

## API 接口

| 接口 | 说明 |
|------|------|
| `GET /api/notices` | 获取公告列表（支持 category/major_name/is_unlimited 筛选） |
| `GET /api/filters` | 获取专业下拉框数据 |
| `GET /api/cron/scrape` | 受密钥保护的爬虫触发接口 |
| `GET /health` | 健康检查 |

## 部署

### Vercel

1. Fork 本仓库
2. 在 Vercel 导入项目
3. 配置环境变量（DATABASE_URL、DEEPSEEK_API_KEY 等）
4. 部署完成

### GitHub Actions（定时爬虫）

在仓库 Settings → Secrets 中配置：

- `DATABASE_URL` / `DATABASE_AUTH_TOKEN`（Turso）
- `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL`
- `SMTP_HOST` / `SMTP_USER` / `SMTP_PASS` / `ADMIN_EMAIL`（邮件推送）

工作流默认周一至周五北京时间 09:00 自动执行。

## 环境变量

```env
# DeepSeek API
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.siliconflow.cn/v1
DEEPSEEK_MODEL=deepseek-ai/DeepSeek-V3

# 数据库（默认本地 SQLite，部署时切换 Turso）
DATABASE_URL=file:./data/notices.db
DATABASE_AUTH_TOKEN=

# Serverless Cron 密钥
CRON_SECRET=your_secret

# 邮件推送（可选）
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=
SMTP_PASS=
ADMIN_EMAIL=
```

## License

MIT
