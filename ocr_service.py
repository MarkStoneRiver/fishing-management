"""
ocr_service.py - Claude API を使った手書き伝票OCRサービス
"""
import os
import base64
import hashlib
import json
import re

import anthropic

from db import get_connection

# ===== Anthropic クライアント初期化 =====
_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise RuntimeError(
                'ANTHROPIC_API_KEY が環境変数に設定されていません。'
                '.env ファイルを確認してください。'
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ===== 蓄積された修正パターンをプロンプトに追加 =====
def _build_correction_hints():
    """過去のOCR修正履歴から頻出パターンを取得してプロンプト補足文を生成する。
    フィールド名は行番号なし（例: detail_fish_code）で集計する。
    """
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT field_name, ocr_value, corrected_value, COUNT(*) as cnt
            FROM ocr_corrections
            WHERE ocr_value != corrected_value
              AND ocr_value IS NOT NULL
              AND corrected_value IS NOT NULL
            GROUP BY field_name, ocr_value, corrected_value
            HAVING cnt >= 2
            ORDER BY cnt DESC
            LIMIT 10
        ''')
        rows = c.fetchall()
        conn.close()

        if not rows:
            return ''

        lines = ['【過去の修正パターン（参考）】']
        for field_name, ocr_val, correct_val, cnt in rows:
            lines.append(
                f'・{field_name}: 「{ocr_val}」は「{correct_val}」の誤読の可能性あり（{cnt}件の修正実績）'
            )
        return '\n'.join(lines)
    except Exception:
        return ''

# ===== DB登録済み魚種コード一覧を取得 =====
def _get_fish_code_list() -> str:
    """魚種マスタからコード一覧を取得してプロンプト用の文字列を返す。"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('SELECT code, name FROM fish_types ORDER BY code')
        rows = c.fetchall()
        conn.close()
        if not rows:
            return ''
        lines = ['このシステムに登録されている魚種コードの一覧（魚種コードを読み取る際はこの一覧と照合し、最も近いコードを選んでください）:']
        for code, name in rows:
            lines.append(f'  {code}: {name}')
        return '\n'.join(lines)
    except Exception:
        return ''


# ===== メインOCR関数 =====
def extract_slip_data(image_bytes: bytes, company_name: str = '') -> dict:
    """
    伝票画像のバイト列を受け取り、Claude APIで解析してJSONを返す。

    Returns:
        {
          "receipt_date": "YYYY-MM-DD",
          "fisherman_name": "氏名",
          "details": [
            {
              "fish_code": "007",
              "fish_name": "ハマチ",
              "container": 1,
              "quantity": 2,
              "weight": 23.0,
              "unit_price": 30,
              "destination": 137
            },
            ...
          ],
          "image_hash": "sha256ハッシュ値"
        }
    """
    # 画像ハッシュ（修正履歴の紐付けに使用）
    image_hash = hashlib.sha256(image_bytes).hexdigest()[:16]

    # base64エンコード
    image_b64 = base64.standard_b64encode(image_bytes).decode('utf-8')

    # MIMEタイプを簡易判定
    if image_bytes[:3] == b'\xff\xd8\xff':
        media_type = 'image/jpeg'
    elif image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        media_type = 'image/png'
    elif image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        media_type = 'image/webp'
    else:
        media_type = 'image/jpeg'  # デフォルト

    # 修正ヒントの取得
    correction_hints = _build_correction_hints()

    # DB登録済み魚種コード一覧
    fish_code_list = _get_fish_code_list()

    # プロンプト組み立て
    prompt = f"""あなたは日本語の手書き鮮魚受入伝票を読み取る専門のOCRシステムです。

添付した伝票画像から情報を読み取り、必ず以下のJSON形式のみで返答してください。
説明文や前置きは一切不要です。JSONだけを出力してください。

【読み取る項目】
- 荷受日（receipt_date）: YYYY-MM-DD形式
- 明細行（details）: 最大20行。「-」のみの行はスキップ

【伝票の列構成（左から右の順番）】
明細列は左から以下の順に並んでいます。列を絶対に混同しないでください:

  列1: 魚種コード → fish_code  （例: 20-11, 2-07）
  列2: 魚種名補足 → fish_name  （例: スレ, 小, 大 ※魚種名ではなくメモのみ）
  列3: 容器     → container  ★必ず3列目を読む。値は0〜9の1桁整数★
  列4: 個（尾）数 → quantity   ★必ず4列目を読む。尾数・個数（10〜200程度の整数）★
  列5: 数量（読み取り不要→スキップ）  ※この列は登録しない
  列6、8: 籠・荷袋・水目（読み取り不要→スキップ）
  列9: 正味数量   → weight     ★kg単位の重量。小数がない場合は整数で返す★
  列10: 単価      → unit_price （例: 250, 140）
  列11: 売先      → destination（例: 108, 107）

【列の区別が特に重要な3つのフィールド】
- container（容器）: 左から3列目。必ず1桁の整数。値は0、5（1=ポリ笥, 2=木笥, 3=うに折, 4=ハッポー, 5=バラ, 0=タンク）
  ※上3列目。必ず3列目の値を読む（75や110などの大きな数字は容器ではなく4列目指数）
- quantity（個尾数）: 左から4列目。魚の尾数・個数。容器列の即右隣
  ※4列目。必ず4列目の値を読む（5列目の「数量」は読み取らない）
- weight（正味数量）: kg単位の重量。小数あり（例: 68.5）、整数の場合は小数点不要（例: 75）
  ※个数列より右側の列

【特に重要な注意事項】
■ 荷受日の元号変換（必ず西暦に変換すること）:
  令和1年=2019, 令和2年=2020, 令和3年=2021, 令和4年=2022
  令和5年=2023, 令和6年=2024, 令和7年=2025, 令和8年=2026
  平成31年/令和元年=2019, 平成30年=2018, 平成29年=2017

■ 魚種コードの読み取り（重要）:
  - 数字とハイフンのみ。文字Oはゼロ（0）として読む
  - 下記の登録済み魚種コード一覧と照合し、最も近いコードを選ぶ

{fish_code_list}

{correction_hints}

【出力形式（このJSONのみ返す）】
{{
  "receipt_date": "YYYY-MM-DD",
  "details": [
    {{
      "fish_code": "20-11",
      "fish_name": "スレ",
      "container": 5,
      "quantity": 75,
      "weight": 75.0,
      "unit_price": 250,
      "destination": 108
    }}
  ]
}}"""

    # Claude API 呼び出し
    # claude-sonnet-4-5: 高精度・vision対応（手書きOCRに推奨）
    client = get_client()
    message = client.messages.create(
        model='claude-sonnet-4-5',
        max_tokens=2048,
        messages=[
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': media_type,
                            'data': image_b64,
                        },
                    },
                    {
                        'type': 'text',
                        'text': prompt,
                    },
                ],
            }
        ],
    )

    # レスポンスのテキストを取得
    response_text = message.content[0].text.strip()

    # JSONブロック（```json ... ```）が含まれる場合は抽出
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response_text)
    if json_match:
        response_text = json_match.group(1).strip()

    # JSONパース
    raw = json.loads(response_text)

    # ===== 構造チェック（Geminiレビュー #6 対応） =====
    if not isinstance(raw, dict):
        raise ValueError('Claude のレスポンスが辞書形式ではありません')
    if 'details' not in raw:
        raw['details'] = []
    if not isinstance(raw['details'], list):
        raw['details'] = []
    # 各明細が辞書でなければスキップ
    raw['details'] = [d for d in raw['details'] if isinstance(d, dict)]

    raw['image_hash'] = image_hash

    # weightの整形: 小数点以下が 0 の場合は整数に変換（例: 75.0 → 75）
    for row in raw.get('details', []):
        w = row.get('weight')
        if isinstance(w, float) and w == int(w):
            row['weight'] = int(w)

    # 空欄の魚種コードを直上行から引き継ぐ
    _propagate_fish_codes(raw['details'])

    return raw


# ===== 魚種コードの引き継ぎ処理 =====
def _propagate_fish_codes(details: list):
    """
    明細行を走査し、fish_code が null/空の行に直上行の fish_code を引き継がせる。
    同じ魚種で複数の売先・容器がある場合のフォーマットに対応。
    """
    last_code = None
    last_name = None
    for row in details:
        code = row.get('fish_code')
        if code:  # 値があれば記憶して次へ
            last_code = code
            last_name = row.get('fish_name') or last_name
        else:
            # 空欄（null）なら直上行の値を引き継ぐ
            if last_code is not None:
                row['fish_code'] = last_code
            if not row.get('fish_name') and last_name:
                row['fish_name'] = last_name


# ===== 修正内容の保存 =====
def save_corrections(ocr_data: dict, confirmed_data: dict, image_hash: str):
    """
    OCR結果とユーザーが確認・修正したデータを比較して差分をDBに保存する。

    行番号なしの共通フィールド名（例: detail_fish_code）で保存し、
    _build_correction_hints の集計が効きやすいようにする（Geminiレビュー #3 対応）。

    ocr_data: Claude が返した元の解析結果
    confirmed_data: ユーザーが確認・修正した確定データ
    """
    corrections = []

    # ヘッダー部分の比較
    header_fields = ['receipt_date', 'fisherman_name']
    for field in header_fields:
        ocr_val = str(ocr_data.get(field) or '')
        confirmed_val = str(confirmed_data.get(field) or '')
        corrections.append((field, ocr_val, confirmed_val, image_hash))

    # 明細行の比較（インデックスベース・行番号なしフィールド名で保存）
    # Geminiレビュー #2: zip ではなく、フォーム送信の行インデックス(1〜20)で
    # 元のOCR結果と突き合わせる。
    # confirmed_data の details は {index: {...}} 形式で格納されている。
    ocr_details = ocr_data.get('details', [])
    confirmed_details = confirmed_data.get('details', [])

    detail_fields = ['fish_code', 'fish_name', 'container',
                     'quantity', 'weight', 'unit_price', 'destination']

    # OCR結果は0始まりのリスト。確定データも同数（確認画面は全20行固定表示）
    # → インデックス対応で比較する
    for i in range(max(len(ocr_details), len(confirmed_details))):
        ocr_row = ocr_details[i] if i < len(ocr_details) else {}
        conf_row = confirmed_details[i] if i < len(confirmed_details) else {}
        for field in detail_fields:
            ocr_val = str(ocr_row.get(field) or '')
            confirmed_val = str(conf_row.get(field) or '')
            # 行番号なし・フィールド名のみで保存（集計しやすい）
            corrections.append((
                f'detail_{field}',
                ocr_val,
                confirmed_val,
                image_hash
            ))

    # DBに保存
    try:
        conn = get_connection()
        c = conn.cursor()
        c.executemany(
            'INSERT INTO ocr_corrections (field_name, ocr_value, corrected_value, image_hash) '
            'VALUES (?, ?, ?, ?)',
            corrections
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'OCR修正データの保存に失敗しました: {e}')
