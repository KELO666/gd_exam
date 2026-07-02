#!/usr/bin/env python3
"""
Phase 6.2 数据回洗脚本：
重新计算所有记录的 disciplines 字段（基于特征词子串匹配）。

使用方式：
    cd backend && python3 scripts/data_backfill_6_2.py
"""

import os
import sys
import json
import shutil

# 将 backend 目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.config import DB_PATH
from backend.models import get_connection
from backend.core.major_mapping import map_majors_to_disciplines


def backup_database():
    """备份数据库文件（仅本地模式）"""
    from config import DATABASE_URL
    if DATABASE_URL.startswith("libsql://") or DATABASE_URL.startswith("https://"):
        print("⚠️  云端数据库跳过本地备份")
        return True
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        return False
    backup_path = DB_PATH + ".bak"
    shutil.copy2(DB_PATH, backup_path)
    print(f"✅ 数据库已备份到: {backup_path}")
    return True


def _row_to_dict(row, columns=("id", "title", "major_names", "disciplines")):
    """兼容 sqlite3.Row 和普通 tuple"""
    try:
        return dict(row)
    except Exception:
        return {col: row[i] for i, col in enumerate(columns)}


def backfill():
    """重新计算所有记录的 disciplines"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, title, major_names, disciplines FROM exam_notices"
    ).fetchall()

    print(f"📊 共找到 {len(rows)} 条记录")

    updated = 0
    unchanged = 0
    errors = 0

    for row in rows:
        try:
            r = _row_to_dict(row)
            major_names_raw = r["major_names"] or "[]"
            try:
                major_names = json.loads(major_names_raw)
            except (json.JSONDecodeError, TypeError):
                major_names = []

            new_disciplines = map_majors_to_disciplines(major_names)
            new_disciplines_json = json.dumps(new_disciplines, ensure_ascii=False)

            old_disciplines = r["disciplines"] or "[]"
            if old_disciplines == new_disciplines_json:
                unchanged += 1
                continue

            conn.execute(
                "UPDATE exam_notices SET disciplines = ? WHERE id = ?",
                (new_disciplines_json, r["id"]),
            )
            updated += 1
            print(f"  #{r['id']} {r['title'][:35]}...")
            print(f"    major_names: {major_names}")
            print(f"    disciplines: {old_disciplines} → {new_disciplines_json}")
        except Exception as e:
            errors += 1
            print(f"  ❌ 处理失败: {e}")

    conn.commit()
    conn.close()

    print()
    print(f"✅ 回洗完成：更新 {updated} 条，未变 {unchanged} 条，失败 {errors} 条")


if __name__ == "__main__":
    print("=== Phase 6.2 数据回洗脚本（特征词子串匹配）===")
    print()

    if not backup_database():
        sys.exit(1)

    print()
    backfill()
