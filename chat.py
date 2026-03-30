"""
chat.py - AIチャット機能（Ollama + SQLite）
"""
import re
import sqlite3
import urllib.request
import urllib.error
import json
import uuid

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

【金額計算ルール】
- 水揚げ金額は必ず fish_receipt_details.unit_price × fish_receipt_details.weight の合計で計算する
- SUM(unit_price * weight) AS total_amount
- fish_receipts.total_weight は総重量であり金額ではないため、金額計算には使用禁止
- 金額を求める場合は必ず fish_receipt_details テーブルをJOINして SUM(frd.unit_price * frd.weight) を使う
- 正しい例:
  SELECT ft.name, SUM(frd.unit_price * frd.weight) AS total_amount
  FROM fish_receipts fr
  JOIN fish_receipt_details frd ON fr.id = frd.receipt_id
  JOIN fish_types ft ON frd.fish_code = ft.code
  WHERE strftime('%Y', fr.receipt_date) = strftime('%Y', date('now', '-1 year'))
  GROUP BY ft.name
  HAVING ft.name IN ('ときさけ', 'ぶり')

【魚名の検索ルール】
- 魚名の検索は完全一致ではなく部分一致（LIKE）を使用する
- 例：「あきさけ」で検索する場合は frd.fish_name LIKE '%あきさけ%'
- これにより「あきさけ（おす）」「あきさけ（めす）」なども含めて抽出できる

【「キズ」の扱い】
- 魚名に「キズ」または「きず」が含まれる場合は別グループとして集計する
- SQLiteは日本語のUPPER/LOWERが効かないため、LIKEを2つORで繋げる
- キズ判定条件：(frd.fish_name LIKE '%キズ%' OR frd.fish_name LIKE '%きず%')
- 正しい例:
  SELECT
      CASE
          WHEN (frd.fish_name LIKE '%キズ%' OR frd.fish_name LIKE '%きず%') THEN frd.fish_name
          ELSE REPLACE(REPLACE(frd.fish_name, '（おす）', ''), '（めす）', '')
      END AS fish_group,
      CASE
          WHEN (frd.fish_name LIKE '%キズ%' OR frd.fish_name LIKE '%きず%') THEN 'キズあり'
          ELSE 'キズなし'
      END AS kizu_flag,
      SUM(frd.unit_price * frd.weight) AS total_amount,
      SUM(frd.weight) AS total_weight,
      SUM(frd.quantity) AS total_quantity
  FROM fish_receipts fr
  JOIN fish_receipt_details frd ON fr.id = frd.receipt_id
  WHERE frd.fish_name LIKE '%あきさけ%'
  AND strftime('%Y', fr.receipt_date) = strftime('%Y', date('now', '-1 year'))
  GROUP BY fish_group, kizu_flag
  ORDER BY kizu_flag, fish_group

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
    pattern = r"```(?:sql)?\s*([\s\S]*?)```"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
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


# ── スレッド管理 API ──────────────────────────────────────────

@chat_bp.route("/api/chat/threads", methods=["GET"])
def get_threads():
    """スレッド一覧を返す。"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT thread_id, thread_name, created_at FROM chat_threads ORDER BY created_at DESC"
        )
        return jsonify([dict(row) for row in cursor.fetchall()])
    finally:
        conn.close()


@chat_bp.route("/api/chat/threads", methods=["POST"])
def create_thread():
    """新しいスレッドを作成する。"""
    data = request.get_json(force=True)
    thread_name = (data.get("thread_name") or "").strip()
    if not thread_name:
        return jsonify({"error": "スレッド名が必要です"}), 400
    thread_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO chat_threads (thread_id, thread_name) VALUES (?, ?)",
            (thread_id, thread_name)
        )
        conn.commit()
        return jsonify({"thread_id": thread_id, "thread_name": thread_name})
    finally:
        conn.close()


@chat_bp.route("/api/chat/threads/<thread_id>", methods=["GET"])
def get_thread_history(thread_id):
    """スレッドのチャット履歴を返す。"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT question, answer, sql_query, created_at FROM chat_history "
            "WHERE thread_id = ? ORDER BY id ASC",
            (thread_id,)
        )
        return jsonify([dict(row) for row in cursor.fetchall()])
    finally:
        conn.close()


@chat_bp.route("/api/chat/threads/<thread_id>", methods=["DELETE"])
def delete_thread(thread_id):
    """スレッドとその履歴を削除する。"""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM chat_history WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM chat_threads WHERE thread_id = ?", (thread_id,))
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()


# ── チャット API ──────────────────────────────────────────────

@chat_bp.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    question = (data.get("question") or "").strip()
    thread_id = (data.get("thread_id") or "").strip()
    thread_name = (data.get("thread_name") or "新しいスレッド").strip()
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

    # Step 5: 履歴保存
    if thread_id:
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO chat_history (thread_id, thread_name, question, answer, sql_query) "
                "VALUES (?, ?, ?, ?, ?)",
                (thread_id, thread_name, question, answer.strip(), sql)
            )
            conn.commit()
        finally:
            conn.close()

    return jsonify({
        "answer": answer.strip(),
        "sql": sql,
        "row_count": len(rows)
    })
