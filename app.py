from flask import Flask, render_template, request, redirect, url_for, jsonify
from init_db import init_db
from gyoba import gyoba_bp
from fish_code_list import fish_code_list_bp
from fish_code import fish_code_bp
from fish_receipt import fish_receipt_bp
from data_compare import data_compare_bp
from past_landings import past_landings_bp
from buyers import buyers_bp
from db import get_connection, DB_PATH

import sqlite3
import os
import secrets
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
# セッション用のシークレットキーを設定
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

# アップロードフォルダの設定
UPLOAD_DIR = os.path.join(os.path.abspath("."), 'static', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# カスタムフィルタ：数値を3桁ごとにコンマ区切りで表示
@app.template_filter('currency')
def currency_filter(value):
    try:
        return f"{int(value):,d}"
    except (ValueError, TypeError):
        return "0"


# カスタムフィルタ：魚種コードをハイフン形式で表示（例：04-00）
@app.template_filter('fish_code_format')
def fish_code_format(value):
    try:
        code_str = str(int(value)).zfill(4)
        return f"{code_str[:2]}-{code_str[2:]}"
    except (ValueError, TypeError):
        return ""


# DBファイルの存在チェックと初期化
if not os.path.exists(DB_PATH):
    init_db()
    print("✅ データベースを初期化しました。")

app.register_blueprint(gyoba_bp)
app.register_blueprint(fish_code_list_bp)
app.register_blueprint(fish_code_bp)
app.register_blueprint(fish_receipt_bp)
app.register_blueprint(data_compare_bp)
app.register_blueprint(past_landings_bp)
app.register_blueprint(buyers_bp)


@app.route("/")
def index():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT company_name FROM companies LIMIT 1")
    result = c.fetchone()
    company_name = result[0] if result else ""
    conn.close()
    return render_template("index.html", company_name=company_name)


@app.route("/compare")
def compare():
    return redirect(url_for('data_compare.data_compare'))


@app.route("/fish_code_list")
def fish_code_list():
    return redirect(url_for('fish_code_list.fish_code_list'))


@app.route("/gyoba", methods=["GET", "POST"])
def gyoba():
    return redirect(url_for('gyoba.gyoba'))


@app.route("/buyers")
def buyers():
    return redirect(url_for('buyers.index'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)
