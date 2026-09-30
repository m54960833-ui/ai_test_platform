"""
很简陋的一个 sqlite 封装，被测服务用的，够用就行。

本来想上 SQLAlchemy，想想被测服务而已，没必要搞那么重，
直接 sqlite3 + 一个全局锁就完事了。
"""
import os
import sqlite3
import threading
from pathlib import Path

# 数据库文件放在项目根目录下的 data/ 里
_DB_DIR = Path(__file__).resolve().parent.parent / "data"
_DB_PATH = _DB_DIR / "aitest.db"

# 多线程下 sqlite 的 connection 不能跨线程共用，
# 所以每条请求单独建一个连接，用锁防止写并发打架。
_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """建表 + 塞一点初始数据，重复调用是安全的。"""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    with _lock, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT,
                nickname TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT DEFAULT '',
                quantity INTEGER NOT NULL DEFAULT 1,
                amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            """
        )
        # 种子用户：demo / demo1234，方便登录测试
        conn.execute(
            "INSERT OR IGNORE INTO users (username, password, email, nickname) VALUES (?,?,?,?)",
            ("demo", "demo1234", "demo@aitest.dev", "演示用户"),
        )


def query(sql, args=()):
    with _lock, _connect() as conn:
        cur = conn.execute(sql, args)
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def query_one(sql, args=()):
    rows = query(sql, args)
    return rows[0] if rows else None


def execute(sql, args=()):
    """写操作，返回影响行数。"""
    with _lock, _connect() as conn:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.rowcount


def insert(sql, args=()):
    """插入并返回自增主键。"""
    with _lock, _connect() as conn:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.lastrowid
