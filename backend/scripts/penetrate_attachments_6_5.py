#!/usr/bin/env python3
"""
Phase 6.5 附件穿透抢救脚本：
重新处理数据库中已有附件文本的记录，按优先级提取三不限和核心专业。

优先级策略：
  P1: 三不限判定（"不限专业"/"专业不限"/"无专业限制"/"专业不作要求"）
  P2: 核心门类提取（农学、管理学等细分专业）

使用方式：
    cd backend && python3 scripts/penetrate_attachments_6_5.py
"""

import os
import sys
import json
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.config import DB_PATH
from backend.models import get_connection
from backend.core.major_mapping import map_majors_to_disciplines

# ─── 三不限特征词库（P1）──────────────────────────────────

UNLIMITED_KEYWORDS = ["不限专业", "专业不限", "无专业限制", "专业不作要求"]

# ─── 核心专业词库（P2）────────────────────────────────────
# 精简版：聚焦业务目标的核心专业

FULL_MAJOR_TREE = {
    # 农学
    "农学": ["农学", "园艺", "园艺学", "植物", "植物学", "植物保护",
             "动物", "动物科学", "动物医学", "水产", "水产养殖",
             "林学", "园林", "林业", "种子", "烟草", "草业"],
    # 管理学
    "管理学": ["行政管理", "公共事业管理", "工商管理", "人力资源管理",
              "会计", "会计学", "财务管理", "审计", "审计学",
              "市场营销", "物流管理", "电子商务", "旅游管理",
              "土地资源管理", "城市管理", "农林经济管理",
              "健康服务与管理", "养老服务管理", "信息管理"],
    # 经济学
    "经济学": ["经济学", "金融学", "金融工程", "财政学", "税收学",
              "国际经济与贸易", "投资学", "保险学"],
    # 法学
    "法学": ["法学", "社会工作", "社会学", "思想政治教育",
            "政治学", "公安", "治安", "侦查"],
    # 教育学
    "教育学": ["教育学", "学前教育", "小学教育", "特殊教育",
              "教育技术", "体育教育", "心理学"],
    # 文学
    "文学": ["汉语言文学", "汉语言", "秘书学", "新闻学",
            "传播学", "编辑出版", "英语", "翻译"],
    # 工学
    "工学": ["计算机", "软件工程", "电子信息", "通信工程",
            "土木工程", "建筑学", "电气工程", "自动化",
            "机械工程", "水利工程"],
    # 理学
    "理学": ["数学", "物理学", "化学", "生物科学", "生物技术",
            "地理科学", "统计学", "生态学"],
    # 医学
    "医学": ["临床医学", "口腔医学", "中医学", "药学", "护理学",
            "医学检验", "医学影像", "预防医学", "公共卫生",
            "康复治疗", "卫生检验"],
}


def check_unlimited(text):
    """P1: 三不限判定"""
    if not text:
        return False
    return any(kw in text for kw in UNLIMITED_KEYWORDS)


def extract_majors_from_text(text):
    """P2: 从文本中提取核心专业名称"""
    if not text:
        return []
    found = []
    for discipline, keywords in FULL_MAJOR_TREE.items():
        for kw in keywords:
            if kw in text:
                if kw not in found:
                    found.append(kw)
    return found


def backup_database():
    """备份数据库（仅本地模式）"""
    from config import DATABASE_URL
    if DATABASE_URL.startswith("libsql://") or DATABASE_URL.startswith("https://"):
        print("⚠️  云端数据库跳过本地备份")
        return True
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库不存在: {DB_PATH}")
        return False
    backup_path = DB_PATH + ".bak6_5"
    shutil.copy2(DB_PATH, backup_path)
    print(f"✅ 已备份到: {backup_path}")
    return True


def _row_to_dict(row, columns):
    """兼容 sqlite3.Row 和普通 tuple"""
    try:
        return dict(row)
    except Exception:
        return {col: row[i] for i, col in enumerate(columns)}


def penetrate():
    """执行附件穿透"""
    conn = get_connection()

    cols = ("id", "title", "url", "major_names", "disciplines", "is_unlimited")
    rows = conn.execute(
        """SELECT id, title, url, major_names, disciplines, is_unlimited
           FROM exam_notices
           WHERE major_names IS NOT NULL AND major_names != '[]'
           ORDER BY id"""
    ).fetchall()

    print(f"📊 找到 {len(rows)} 条有专业数据的记录")

    updated = 0
    unchanged = 0
    errors = 0

    for row in rows:
        try:
            r = _row_to_dict(row, cols)
            old_majors = json.loads(r["major_names"] or "[]")
            old_disciplines = json.loads(r["disciplines"] or "[]")
            old_unlimited = bool(r["is_unlimited"])

            combined_text = " ".join(old_majors)

            is_unlimited = check_unlimited(combined_text) or old_unlimited
            new_majors = extract_majors_from_text(combined_text)
            all_majors = list(dict.fromkeys(old_majors + new_majors))
            new_disciplines = map_majors_to_disciplines(all_majors)

            new_majors_json = json.dumps(all_majors, ensure_ascii=False)
            new_disciplines_json = json.dumps(new_disciplines, ensure_ascii=False)
            new_unlimited_int = 1 if is_unlimited else 0

            old_majors_json = json.dumps(old_majors, ensure_ascii=False)
            old_disciplines_json = json.dumps(old_disciplines, ensure_ascii=False)

            if (old_majors_json == new_majors_json and
                old_disciplines_json == new_disciplines_json and
                bool(old_unlimited) == is_unlimited):
                unchanged += 1
                continue

            conn.execute(
                """UPDATE exam_notices
                   SET major_names = ?, disciplines = ?, is_unlimited = ?
                   WHERE id = ?""",
                (new_majors_json, new_disciplines_json, new_unlimited_int, r["id"]),
            )
            updated += 1
            print(f"  #{r['id']} {r['title'][:40]}...")
            if is_unlimited and not old_unlimited:
                print(f"    ★ 三不限标记: True")
            if new_majors != old_majors:
                print(f"    专业: {old_majors} → {all_majors}")
            if new_disciplines != old_disciplines:
                print(f"    学科: {old_disciplines} → {new_disciplines}")
        except Exception as e:
            errors += 1
            print(f"  ❌ 失败: {e}")

    conn.commit()
    conn.close()

    print()
    print(f"✅ 完成：更新 {updated} 条，未变 {unchanged} 条，失败 {errors} 条")


if __name__ == "__main__":
    print("=== Phase 6.5 附件穿透抢救脚本 ===")
    print("优先级: P1 三不限 > P2 核心专业提取")
    print()

    if not backup_database():
        sys.exit(1)

    print()
    penetrate()
