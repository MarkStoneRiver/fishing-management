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


# ===== メインOCR関数 =====
def extract_slip_data(image_bytes: bytes) -> dict:
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

    # プロンプト組み立て
    prompt = f"""あなたは日本語の手書き鮮魚受入伝票を読み取る専門のOCRシステムです。

添付した伝票画像から情報を読み取り、必ず以下のJSON形式のみで返答してください。
説明文や前置きは一切不要です。JSONだけを出力してください。

【読み取る項目】
- 荷受日（receipt_date）: YYYY-MM-DD形式
- 漁業者名（fisherman_name）: 氏名のみ（「様」「係」などの敬称は除外）
- 明細行（details）: 最大20行。「-」のみの行はスキップ

【明細の各フィールド】
- fish_code: 魚種コード（数字・ハイフン含む）。「-」のみの行は行自体をスキップ。完全に空欄の場合はnull（直上行と同じ魚種を意味する）
- fish_name: 魚種名の補足（コード横に書かれた魚種名）。なければnull
- container: 容器番号（整数1〜9、タンクは0）。不明はnull
- quantity: 個（尾）数（数値）。不明はnull
- weight: 正味数量（小数可）。不明はnull
- unit_price: 単価（整数）。不明はnull
- destination: 売先コード（整数）。「〃」マークは直前行と同じ値。不明はnull

【注意事項】
- 魚種コードが完全に空欄の行は「直上行と同じ魚種」を意味するため、fish_codeはnullで返す
- 「々」「〃」は直前行の同フィールド値を引き継ぐ
- 荷受日の年が元号（令和・平成など）の場合は西暦に変換
- 魚種コードは「007」のように読めても「0O7」（文字Oではなくゼロ）の可能性を考慮
- 手書きのため判読困難な文字はnullで返す

{correction_hints}

【出力形式（このJSONのみ返す）】
{{
  "receipt_date": "YYYY-MM-DD",
  "fisherman_name": "氏名",
  "details": [
    {{
      "fish_code": "007",
      "fish_name": "ハマチ",
      "container": 1,
      "quantity": 2,
      "weight": 23.0,
      "unit_price": 30,
      "destination": 137
    }}
  ]
}}"""

    # Claude API 呼び出し（claude-3-5-haiku-20241022: コスト最適・vision対応）
    # 精度が不十分な場合は claude-3-5-sonnet-20241022 に変更を検討
    client = get_client()
    message = client.messages.create(
        model='claude-haiku-4-5-20251001',
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
