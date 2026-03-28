"""
db.py - DB接続の共通ヘルパー
環境変数 DB_PATH でDBのパスを上書き可能（デフォルト: /data/gyokaku.db）
"""
import os
import sqlite3

DB_PATH = os.environ.get('DB_PATH', '/data/gyokaku.db')


def get_connection():
    """SQLite接続を返す。row_factory を sqlite3.Row に設定済み。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
