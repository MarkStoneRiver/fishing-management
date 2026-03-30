"""
chat.py - AIチャット機能（Ollama + SQLite）
"""
import re
import sqlite3
import urllib.request
import urllib.error
import json

from flask import Blueprint, render_template, request, jsonify
from db import DB_PATH, get_connection

chat_bp = Blueprint('chat', __name__)

OLLAMA_URL = "http://192.168.3.64:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:14b"

SCHEMA_DESC = """
以下のSQLiteデータベースのテーブル構成です。

テーブル一覧:
- fish_receipts: id, receipt_no, receipt_date, company_id, fisherman_name, market_name, total_weight, created_at
  （漁獲伝票のヘッダ情報。receipt_dateはYYYY-MM-DD形式）
- fish_receipt_details: id, receipt_id, line_no, fish_code, fish_name, container, quantity, weight, unit_price, destination
  （伝票の明細行。receipt_id が fish_receipts.id に対応）
- fish_types: id, code, name, per_unit_weight
  （魚種マスタ）
- buyers: id, code, name
  （買受人マスタ）
- containers: id, code, name
  （容器マスタ）
- companies: id, company_name
  （会社マスタ）

リレーション:
- fish_receipt_details.receipt_id = fish_receipts.id
"""

SQL_PROMPT_TEMPLATE = """{schema}

ユーザーの質問に答えるためのSQLite用SELECT文を1つだけ生成してください。

【必須ルール】
- SELECT文のみ生成してください（INSERT/UPDATE/DELETEは禁止）
- コードブロック（```sql ... ``` や ``` ... ```）で囲んでください
- SQL以外の説明文は不要です

【日付処理ルール（SQLite専用）】
- DATE_PART関数は使用禁止。日付処理は必ずstrftime関数を使うこと
- 「昨年」= strftime('%Y', date('now', '-1 year'))
- 「今年」= strftime('%Y', 'now')
- 「先月」= strftime('%Y-%m', date('now', '-1 month'))
- 「今月」= strftime('%Y-%m', 'now')
- 年の比較例: strftime('%Y', receipt_date) = strftime('%Y', date('now', '-1 year'))
- 月の比較例: strftime('%Y-%m', receipt_date) = strftime('%Y-%m', 'now')

質問: {question}
"""

ANSWER_PROMPT_TEMPLATE = """以下のSQL実行結果をもとに、ユーザーの質問に日本語で簡潔に回答してください。

質問: {question}

実行したSQL:
{sql}

実行結果（JSON形式）:
{result}

回答:"""


def call_ollama(prompt: str) -> str:
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("response", "")


def extract_sql(text: str) -> str | None:
    """コードブロックからSQLを抽出する。"""
    # ```sql ... ``` または ``` ... ``` を探す
    pattern = r"```(?:sql)?\s*([\s\S]*?)```"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # コードブロックがない場合、SELECT で始まる行を探す
    for line in text.splitlines():
        if line.strip().upper().startswith("SELECT"):
            return line.strip()
    return None


def is_safe_sql(sql: str) -> bool:
    """SELECTのみ許可する。"""
    normalized = sql.strip().upper()
    if not normalized.startswith("SELECT"):
        return False
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "TRUNCATE"]
    for keyword in forbidden:
        if re.search(r'\b' + keyword + r'\b', normalized):
            return False
    return True


def run_sql(sql: str) -> list[dict]:
    """SQLを実行してdictのリストを返す。"""
    conn = get_connection()
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@chat_bp.route("/chat")
def chat_page():
    return render_template("chat.html")


@chat_bp.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "質問が空です"}), 400

    # Step 1: SQLを生成
    sql_prompt = SQL_PROMPT_TEMPLATE.format(schema=SCHEMA_DESC, question=question)
    try:
        sql_response = call_ollama(sql_prompt)
    except Exception as e:
        return jsonify({"error": f"Ollamaへの接続に失敗しました: {e}"}), 500

    sql = extract_sql(sql_response)
    if not sql:
        return jsonify({"error": "SQLの生成に失敗しました。", "raw": sql_response}), 500

    # Step 2: 安全チェック
    if not is_safe_sql(sql):
        return jsonify({"error": "安全でないSQLが生成されました。SELECT文のみ許可されています。", "sql": sql}), 400

    # Step 3: SQL実行
    try:
        rows = run_sql(sql)
    except sqlite3.Error as e:
        return jsonify({"error": f"SQL実行エラー: {e}", "sql": sql}), 500

    # Step 4: 回答生成
    result_json = json.dumps(rows, ensure_ascii=False, default=str)
    # 結果が大きすぎる場合は先頭50件に絞る
    if len(rows) > 50:
        result_json = json.dumps(rows[:50], ensure_ascii=False, default=str)
        result_json += f"\n（全{len(rows)}件中、先頭50件を表示）"

    answer_prompt = ANSWER_PROMPT_TEMPLATE.format(
        question=question,
        sql=sql,
        result=result_json
    )
    try:
        answer = call_ollama(answer_prompt)
    except Exception as e:
        return jsonify({"error": f"回答生成に失敗しました: {e}", "sql": sql, "rows": rows}), 500

    return jsonify({
        "answer": answer.strip(),
        "sql": sql,
        "row_count": len(rows)
    })
