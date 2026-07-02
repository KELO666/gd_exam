import os
import json
import sqlite3
from backend.config import DB_DIR, DB_PATH, DATABASE_URL, DATABASE_AUTH_TOKEN


def get_connection():
    """
    获取数据库连接。
    - 若 DATABASE_URL 以 libsql:// 或 https:// 开头，连接 Turso 云端
    - 否则回退到本地 SQLite 文件
    """
    if DATABASE_URL.startswith("libsql://") or DATABASE_URL.startswith("https://"):
        import libsql_experimental as libsql
        conn = libsql.connect(database=DATABASE_URL, auth_token=DATABASE_AUTH_TOKEN)
        return conn
    else:
        os.makedirs(DB_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exam_notices (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT    NOT NULL,
            url             TEXT    NOT NULL UNIQUE,
            source          TEXT    NOT NULL,
            category        TEXT    DEFAULT '',
            majors          TEXT    DEFAULT '',
            publish_date    TEXT    DEFAULT '',
            deadline        TEXT    DEFAULT NULL,
            major_category  TEXT    DEFAULT '',
            is_unlimited    INTEGER DEFAULT 0,
            disciplines     TEXT    DEFAULT '[]',
            major_names     TEXT    DEFAULT '[]',
            created_at      TEXT    DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON exam_notices(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON exam_notices(source)")
    # 迁移：为旧表补充新字段
    try:
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(exam_notices)").fetchall()}
        for col, definition in [
            ("deadline", "TEXT DEFAULT NULL"),
            ("major_category", "TEXT DEFAULT ''"),
            ("is_unlimited", "INTEGER DEFAULT 0"),
            ("disciplines", "TEXT DEFAULT '[]'"),
            ("major_names", "TEXT DEFAULT '[]'"),
        ]:
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE exam_notices ADD COLUMN {col} {definition}")
    except Exception:
        pass  # Turso 不支持 PRAGMA，跳过迁移检查
    conn.commit()
    conn.close()


def _to_json_list(val):
    """安全地将值转为 JSON 字符串数组"""
    if isinstance(val, list):
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return json.dumps(parsed, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pass
    return "[]"


def _from_json_list(val):
    """安全地从 JSON 字符串解析为 Python 列表"""
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return []


def insert_notice(title, url, source, category, majors, publish_date,
                  deadline=None, major_category="",
                  is_unlimited=False, disciplines=None, major_names=None):
    conn = get_connection()
    try:
        disciplines_json = _to_json_list(disciplines or [])
        major_names_json = _to_json_list(major_names or [])
        is_unlimited_int = 1 if is_unlimited else 0
        cursor = conn.execute(
            """INSERT INTO exam_notices
               (title, url, source, category, majors, publish_date,
                deadline, major_category, is_unlimited, disciplines, major_names)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(url) DO UPDATE SET
                 deadline = COALESCE(excluded.deadline, exam_notices.deadline),
                 major_category = COALESCE(NULLIF(excluded.major_category, ''), exam_notices.major_category),
                 is_unlimited = CASE
                   WHEN excluded.is_unlimited = 1 THEN 1
                   ELSE exam_notices.is_unlimited
                 END,
                 disciplines = CASE
                   WHEN excluded.disciplines != '[]' THEN excluded.disciplines
                   ELSE exam_notices.disciplines
                 END,
                 major_names = CASE
                   WHEN excluded.major_names != '[]' THEN excluded.major_names
                   ELSE exam_notices.major_names
                 END,
                 publish_date = CASE
                   WHEN excluded.publish_date != '' AND excluded.publish_date != exam_notices.publish_date
                     THEN excluded.publish_date
                   ELSE exam_notices.publish_date
                 END""",
            (title, url, source, category, majors, publish_date,
             deadline, major_category, is_unlimited_int,
             disciplines_json, major_names_json),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def query_notices(category=None, major_category=None, skip_expired=False,
                  discipline=None, major_name=None, is_unlimited=None):
    conn = get_connection()
    try:
        conn.row_factory = sqlite3.Row
    except Exception:
        pass  # libsql 不支持 row_factory，后续手动转换
    sql = "SELECT * FROM exam_notices WHERE 1=1"
    params = []
    if category:
        sql += " AND category = ?"
        params.append(category)
    if major_category:
        sql += " AND major_category = ?"
        params.append(major_category)
    if skip_expired:
        sql += " AND (deadline IS NULL OR deadline = '' OR deadline >= date('now', 'localtime'))"
    sql += " AND is_unlimited = 0"
    sql += " ORDER BY publish_date DESC, id DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    results = []
    for row in rows:
        # 兼容 sqlite3.Row 和普通 tuple
        try:
            r = dict(row)
        except Exception:
            r = {
                "id": row[0], "title": row[1], "url": row[2], "source": row[3],
                "category": row[4], "majors": row[5], "publish_date": row[6],
                "deadline": row[7], "major_category": row[8],
                "is_unlimited": row[9], "disciplines": row[10], "major_names": row[11],
                "created_at": row[12] if len(row) > 12 else "",
            }
        r["disciplines"] = _from_json_list(r.get("disciplines", "[]"))
        r["major_names"] = _from_json_list(r.get("major_names", "[]"))
        r["is_unlimited"] = bool(r.get("is_unlimited", 0))

        if is_unlimited is not None:
            if is_unlimited and not r["is_unlimited"]:
                continue
            if not is_unlimited and r["is_unlimited"]:
                continue

        if discipline:
            if discipline not in r["disciplines"]:
                continue

        if major_name:
            if major_name not in r["major_names"]:
                continue

        results.append(r)

    return results


def query_notice_by_url(url):
    """查询单条记录"""
    conn = get_connection()
    try:
        conn.row_factory = sqlite3.Row
    except Exception:
        pass
    row = conn.execute("SELECT * FROM exam_notices WHERE url = ?", (url,)).fetchone()
    conn.close()
    if row:
        try:
            r = dict(row)
        except Exception:
            r = {
                "id": row[0], "title": row[1], "url": row[2], "source": row[3],
                "category": row[4], "majors": row[5], "publish_date": row[6],
                "deadline": row[7], "major_category": row[8],
                "is_unlimited": row[9], "disciplines": row[10], "major_names": row[11],
                "created_at": row[12] if len(row) > 12 else "",
            }
        r["disciplines"] = _from_json_list(r.get("disciplines", "[]"))
        r["major_names"] = _from_json_list(r.get("major_names", "[]"))
        r["is_unlimited"] = bool(r.get("is_unlimited", 0))
        return r
    return None


def query_all_filters():
    """返回所有去重的学科门类和具体专业"""
    conn = get_connection()
    rows = conn.execute("SELECT disciplines, major_names FROM exam_notices").fetchall()
    conn.close()

    all_disciplines = set()
    all_majors = set()
    for row in rows:
        for d in _from_json_list(row[0]):
            all_disciplines.add(d)
        for m in _from_json_list(row[1]):
            all_majors.add(m)

    return {
        "disciplines": sorted(all_disciplines),
        "majors": sorted(all_majors),
    }
