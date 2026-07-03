import os
import re
import time
import random
import logging
import tempfile
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from backend.config import (
    SOURCES, CATEGORY_KEYWORDS, GUANGDONG_KEYWORDS,
    SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX,
    REQUEST_TIMEOUT, USER_AGENT,
)
from backend.models import insert_notice, init_db, get_connection, query_notice_by_url
from backend.llm_processor import extract_info

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

HEADERS = {"User-Agent": USER_AGENT}

# 附件下载临时目录（使用系统标准 /tmp，兼容 Vercel Serverless）
TEMP_DIR = os.path.join(tempfile.gettempdir(), "gd_exam_downloads")
os.makedirs(TEMP_DIR, exist_ok=True)


# ─── 工具函数 ─────────────────────────────────────────────

def classify(title):
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in title:
                return category
    return "未分类"


def is_guangdong(title):
    return any(kw in title for kw in GUANGDONG_KEYWORDS)


def extract_majors(title):
    match = re.search(r'[（(]([^)）]+)[）)]', title)
    return match.group(1) if match else ""


def _normalize_date(date_str):
    """统一日期格式为 YYYY-MM-DD"""
    date_str = date_str.strip().replace("年", "-").replace("月", "-").replace("日", "")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if 2024 <= dt.year <= 2027:
                return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def extract_publish_date(soup):
    """从详情页提取真实发布时间"""
    text = soup.get_text()
    patterns = [
        r'(?:发布时间|发布日期|信息时间|公告时间)[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)',
        r'(?:发布时间|发布日期|信息时间|公告时间)\s*[:：]?\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            result = _normalize_date(match.group(1))
            if result:
                return result
    for meta in soup.find_all("meta"):
        if meta.get("name") in ("publishdate", "publish_date", "article:published_time"):
            content = meta.get("content", "")
            result = _normalize_date(content)
            if result:
                return result
    for el in soup.find_all(["span", "time", "em", "div"]):
        cls = " ".join(el.get("class", []))
        if any(k in cls for k in ("date", "time", "publish")):
            result = _normalize_date(el.get_text(strip=True))
            if result:
                return result
    return None


def _extract_core_content(soup):
    """提取详情页核心正文内容（排除导航、页脚等干扰）"""
    for selector in [".content_c", ".article-content", ".content", ".news-content",
                     ".detail-content", "#content", "article", ".main-content",
                     ".entry-content", ".post-content"]:
        el = soup.select_one(selector)
        if el:
            for tag in el.find_all(["script", "style", "nav", "footer", "aside"]):
                tag.decompose()
            return el.get_text(separator="\n")
    body = soup.find("body")
    if body:
        for tag in body.find_all(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        return body.get_text(separator="\n")
    return ""


def _extract_attachments(soup, base_url):
    """从详情页提取 PDF/Excel 附件链接"""
    attachments = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        lower_href = href.lower()
        if any(lower_href.endswith(ext) for ext in (".pdf", ".xls", ".xlsx")):
            full_url = urljoin(base_url, href)
            filename = os.path.basename(href.split("?")[0])
            if not filename:
                filename = f"attachment_{hash(href) % 10000}.pdf"
            attachments.append({"url": full_url, "filename": filename})
    return attachments


def _download_file(url, filename):
    """下载文件到临时目录，返回文件路径"""
    filepath = os.path.join(TEMP_DIR, filename)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)
        return filepath
    except Exception as e:
        log.debug("附件下载失败 %s: %s", url, e)
        return None


def _parse_pdf(filepath):
    """用 pdfplumber 提取 PDF 文本"""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                for table in page.extract_tables():
                    for row in table:
                        row_text = " ".join(str(cell or "") for cell in row)
                        text_parts.append(row_text)
        return "\n".join(text_parts)
    except Exception as e:
        log.debug("PDF 解析失败 %s: %s", filepath, e)
        return ""


def _parse_excel(filepath):
    """用 pandas 提取 Excel 文本"""
    try:
        import pandas as pd
        df = pd.read_excel(filepath, dtype=str)
        return df.to_string(index=False)
    except Exception as e:
        log.debug("Excel 解析失败 %s: %s", filepath, e)
        return ""


def _cleanup_temp():
    """清理临时目录中的所有文件"""
    try:
        for f in os.listdir(TEMP_DIR):
            fp = os.path.join(TEMP_DIR, f)
            if os.path.isfile(fp):
                os.remove(fp)
    except Exception:
        pass


# ─── 详情页深度爬取 ──────────────────────────────────────

def scrape_detail_page(url, title="", source_encoding="utf-8"):
    """
    抓取详情页，通过 LLM 提取截止日期、学科门类和具体专业。
    返回字典：{"deadline", "publish_date", "is_unlimited", "disciplines", "major_names"}
    """
    result = {
        "deadline": None, "publish_date": None,
        "is_unlimited": False, "disciplines": [], "major_names": [],
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.encoding = source_encoding
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. 提取核心正文
        core_text = _extract_core_content(soup)

        # 2. 提取真实发布时间（正则，稳定可靠）
        result["publish_date"] = extract_publish_date(soup)

        # 3. LLM 提取多维信息
        llm_result = extract_info(core_text, title)
        if llm_result:
            result["deadline"] = llm_result.get("deadline")
            result["is_unlimited"] = llm_result.get("is_unlimited", False)
            result["disciplines"] = llm_result.get("disciplines", [])
            result["major_names"] = llm_result.get("major_names", [])

        # 4. 附件下载与解析（用附件内容重新调用 LLM 覆盖）
        attachments = _extract_attachments(soup, url)
        if attachments:
            for att in attachments[:3]:
                filepath = _download_file(att["url"], att["filename"])
                if not filepath:
                    continue
                try:
                    if filepath.lower().endswith(".pdf"):
                        att_text = _parse_pdf(filepath)
                    elif filepath.lower().endswith((".xls", ".xlsx")):
                        att_text = _parse_excel(filepath)
                    else:
                        att_text = ""
                    if att_text:
                        att_llm = extract_info(att_text, title)
                        if att_llm:
                            if att_llm.get("deadline"):
                                result["deadline"] = att_llm["deadline"]
                            if att_llm.get("is_unlimited"):
                                result["is_unlimited"] = True
                            if att_llm.get("disciplines"):
                                result["disciplines"] = att_llm["disciplines"]
                            if att_llm.get("major_names"):
                                result["major_names"] = att_llm["major_names"]
                finally:
                    try:
                        os.remove(filepath)
                    except OSError:
                        pass
    except Exception as e:
        log.debug("详情页抓取失败 %s: %s", url, e)

    return result


# ─── 脏数据清理 ──────────────────────────────────────────

def clean_dirty_data():
    """清理 qgsydw 中不含广东地域关键字的脏数据"""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT COUNT(*) FROM exam_notices WHERE source = 'qgsydw'"
    )
    total_qgsydw = cursor.fetchone()[0]
    cursor = conn.execute(
        "SELECT id, title FROM exam_notices WHERE source = 'qgsydw'"
    )
    delete_ids = []
    for row in cursor.fetchall():
        if not is_guangdong(row[1]):
            delete_ids.append(row[0])
    if delete_ids:
        placeholders = ",".join("?" * len(delete_ids))
        conn.execute(
            f"DELETE FROM exam_notices WHERE id IN ({placeholders})",
            delete_ids,
        )
        conn.commit()
        log.info("清理 qgsydw 脏数据 %d 条（保留 %d 条广东数据）",
                 len(delete_ids), total_qgsydw - len(delete_ids))
    else:
        log.info("qgsydw 无脏数据需要清理")
    conn.close()


def safe_date(date_text):
    date_text = date_text.strip()
    today = datetime.now().strftime("%Y-%m-%d")
    if not date_text or date_text in ("刚刚", "置顶", "今天"):
        return today
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(date_text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return today


# ─── 列表页爬取 ──────────────────────────────────────────

def scrape_sydw1(source):
    """
    爬取 sydw1 广东事业单位列表页。
    URL 匹配规则：支持任意深度的城市子目录，如
      /guangdong/foshan/195863.html
      /guangdong/guangzhou/149274.html
      /guangdong/195858.html
    """
    items = []
    url = source["url"]
    log.info("正在爬取: %s", url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.encoding = source["encoding"]
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("请求失败 %s: %s", url, e)
        return items

    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        title = a.get_text(strip=True)
        if not title or not href:
            continue
        # 匹配 /guangdong/ 下任意深度的 .html 链接（含城市子目录）
        if not re.search(r'/guangdong/(?:[\w-]+/)*[\w-]+\.html$', href):
            continue
        if len(title) < 10:
            continue
        if href.startswith("/"):
            href = "https://www.sydw1.com" + href
        elif not href.startswith("http"):
            continue
        items.append({
            "title": title,
            "url": href,
            "source": source["name"],
        })
    log.info("sydw1 抓取到 %d 条", len(items))
    return items


def scrape_qgsydw(source):
    """爬取全国事业单位招聘网列表页"""
    items = []
    url = source["url"]
    log.info("正在爬取: %s", url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.encoding = "gb2312"
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("请求失败 %s: %s", url, e)
        return items

    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        raw_text = a.get_text(strip=True)
        if not raw_text or not href:
            continue
        if "/recruit/" not in href or "/index." in href:
            continue
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})\s*$', raw_text)
        publish_date = date_match.group(1) if date_match else ""
        title = re.sub(r'\d{4}-\d{2}-\d{2}\s*$', '', raw_text).strip()
        if not title or len(title) < 5:
            continue
        if re.match(r'^[\d/\s:]+$', title):
            continue
        if not is_guangdong(title):
            continue
        if href.startswith("/"):
            href = "https://www.qgsydw.com" + href
        elif not href.startswith("http"):
            continue
        items.append({
            "title": title,
            "url": href,
            "source": source["name"],
            "publish_date": publish_date,
        })
    log.info("qgsydw 抓取到 %d 条", len(items))
    return items


SCRAPERS = {
    "sydw1": scrape_sydw1,
    "qgsydw": scrape_qgsydw,
}


# ─── 主入口 ──────────────────────────────────────────────

def run_scrape():
    """主入口：逐源爬取并入库，含详情页 LLM 深度嗅探"""
    init_db()
    clean_dirty_data()
    today = datetime.now().strftime("%Y-%m-%d")
    total_new = 0
    total_updated = 0
    detail_count = 0
    llm_success = 0
    publish_date_success = 0

    for source in SOURCES:
        scraper_fn = SCRAPERS.get(source["name"])
        if not scraper_fn:
            log.warning("未找到 %s 的爬取函数，跳过", source["name"])
            continue
        items = scraper_fn(source)
        new_count = 0
        updated_count = 0
        for item in items:
            category = classify(item["title"])
            if category == "未分类" and not is_guangdong(item["title"]):
                log.debug("跳过无地域信息的未分类公告: %s", item["title"][:40])
                continue
            majors = extract_majors(item["title"])

            # 详情页 LLM 深度嗅探
            deadline = None
            major_category = "其他专业"
            real_publish_date = None
            is_unlimited = False
            disciplines = []
            major_names = []
            try:
                encoding = source.get("encoding", "utf-8")
                detail = scrape_detail_page(item["url"], item["title"], encoding)
                deadline = detail["deadline"]
                real_publish_date = detail["publish_date"]
                is_unlimited = detail.get("is_unlimited", False)
                disciplines = detail.get("disciplines", [])
                major_names = detail.get("major_names", [])
                detail_count += 1
                if deadline or disciplines or major_names or is_unlimited:
                    llm_success += 1
                if real_publish_date:
                    publish_date_success += 1
            except Exception as e:
                log.debug("详情页处理异常 %s: %s", item["url"], e)

            # 标题括号专业回退
            if not disciplines and not major_names:
                major_from_title = extract_majors(item["title"])
                if major_from_title:
                    major_category = "其他专业"  # LLM 已判断，不再用正则覆盖

            final_date = real_publish_date or item.get("publish_date") or today

            existing = query_notice_by_url(item["url"])
            insert_notice(
                title=item["title"],
                url=item["url"],
                source=item["source"],
                category=category,
                majors=majors,
                publish_date=final_date,
                deadline=deadline,
                major_category=major_category,
                is_unlimited=is_unlimited,
                disciplines=disciplines,
                major_names=major_names,
            )
            if existing:
                updated_count += 1
            else:
                new_count += 1
            time.sleep(random.uniform(SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX))

        total_new += new_count
        total_updated += updated_count
        log.info("%s 新增 %d 条，更新 %d 条", source["name"], new_count, updated_count)

    _cleanup_temp()

    log.info("详情页抓取 %d 条，LLM 提取成功 %d 条（%.0f%%），真实发布日期 %d 条（%.0f%%）",
             detail_count, llm_success,
             llm_success / detail_count * 100 if detail_count else 0,
             publish_date_success,
             publish_date_success / detail_count * 100 if detail_count else 0)
    log.info("本次爬取共新增 %d 条，更新 %d 条", total_new, total_updated)
    return total_new


if __name__ == "__main__":
    run_scrape()
