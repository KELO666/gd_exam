import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# 数据库配置
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "notices.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"file:{DB_PATH}")
DATABASE_AUTH_TOKEN = os.getenv("DATABASE_AUTH_TOKEN", "")

# 目标爬取源
SOURCES = [
    {
        "name": "sydw1",
        "url": "https://www.sydw1.com/guangdong/",
        "encoding": "utf-8",
    },
    {
        "name": "qgsydw",
        "url": "https://www.qgsydw.com/qgsydw/index.html",
        "encoding": "gb2312",
    },
]

# 分类关键词
CATEGORY_KEYWORDS = {
    "公务员": ["公务员", "选调生", "公考", "国考", "省考"],
    "事业编": ["事业单位", "医院", "学校", "人才引进", "中心", "局", "研究所", "馆", "辅导员"],
    "编外人员": ["编外", "劳务派遣", "合同制", "临时工", "辅助", "外包", "协警", "辅警", "社工"],
}

# 广东地域关键词（qgsydw 过滤用）
GUANGDONG_KEYWORDS = [
    "广东", "广州", "深圳", "东莞", "佛山", "珠海", "中山", "惠州",
    "江门", "汕头", "湛江", "肇庆", "茂名", "揭阳", "梅州", "清远",
    "韶关", "河源", "阳江", "潮州", "汕尾", "云浮", "顺德", "南沙",
]

# 请求配置
REQUEST_TIMEOUT = 10
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 专业大类映射（标题/正文关键词 → 标准化大类）
# 注意：关键词必须是"实质性专业名词"，避免通用表述（如"法律法规"、"信息化"）
MAJOR_MAPPING = {
    "计算机类": [
        "计算机", "软件工程", "软件开发", "网络工程", "信息安全",
        "大数据", "人工智能", "电子工程", "通信工程", "自动化",
        "编程", "数据库", "运维工程师",
    ],
    "财务审计类": [
        "会计学", "财务管理", "审计学", "财税", "金融学",
        "经济学", "统计学",
    ],
    "医疗卫生类": [
        "医学", "护理学", "药学", "临床医学", "医学检验",
        "医学影像", "中医", "预防医学", "公共卫生", "口腔医学",
        "康复治疗", "卫生检验",
    ],
    "教育师范类": [
        "教育学", "师范", "学前教育", "心理学",
        "教育技术", "学科教学",
    ],
    "法学类": [
        "法学", "法律专业", "司法", "律师", "公证",
    ],
    "汉语言文秘类": [
        "汉语言", "文秘", "新闻学", "传播学", "编辑出版",
        "中国语言文学", "秘书学",
    ],
    "不限专业": ["不限专业", "专业不限"],
}

# 详情页爬取间隔（秒），防止被封
SCRAPE_DELAY_MIN = 1
SCRAPE_DELAY_MAX = 2

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.siliconflow.cn/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-ai/DeepSeek-V3")

# 定时任务：工作日早上 9 点
CRON_HOUR = 9
CRON_MINUTE = 0
