from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from db import get_connection
from datetime import datetime
import json
import ocr_service

fish_receipt_bp = Blueprint('fish_receipt', __name__, url_prefix='/fish_receipt')


@fish_receipt_bp.route("/", methods=['GET', 'POST'])
def fish_receipt():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM companies")
    company_count = c.fetchone()[0]

    if company_count == 0:
        conn.close()
        return render_template("fish_receipt.html",
                               error="漁場名を登録してください",
                               today=datetime.now().strftime('%Y-%m-%d'))

    if request.method == 'POST':
        receipt_date = request.form.get('receipt_date')
        fisherman_name = request.form.get('fisherman_name')
        edit_mode = 'receipt_id' in request.form

        try:
            if edit_mode:
                receipt_id = request.form.get('receipt_id')
                c.execute("""
                    SELECT receipt_no, receipt_date, fisherman_name, company_id
                    FROM fish_receipts WHERE id = ?
                """, (receipt_id,))
                receipt_data = c.fetchone()

                if not receipt_data:
                    conn.close()
                    return render_template("fish_receipt.html",
                                           error="伝票が見つかりません",
                                           today=receipt_date)

                receipt_no, old_receipt_date, old_fisherman_name, company_id = receipt_data
                c.execute("""
                    UPDATE fish_receipts
                    SET receipt_date = ?, fisherman_name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (receipt_date, fisherman_name, receipt_id))
                c.execute("DELETE FROM fish_receipt_details WHERE receipt_id = ?", (receipt_id,))

            else:
                c.execute("SELECT id FROM companies LIMIT 1")
                company_result = c.fetchone()
                if not company_result:
                    conn.close()
                    return render_template("fish_receipt.html",
                                           error="漁場名が登録されていません",
                                           today=receipt_date)

                company_id = company_result[0]
                today = datetime.now().strftime('%Y%m%d')
                c.execute("SELECT MAX(receipt_no) FROM fish_receipts WHERE receipt_no LIKE ?", (f"{today}%",))
                max_receipt_no = c.fetchone()[0]
                sequence = int(max_receipt_no[-4:]) + 1 if max_receipt_no else 1
                receipt_no = f"{today}{sequence:04d}"

                c.execute("""
                    INSERT INTO fish_receipts
                    (receipt_no, receipt_date, company_id, fisherman_name, total_weight, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (receipt_no, receipt_date, company_id, fisherman_name))
                receipt_id = c.lastrowid

            total_weight = 0
            for i in range(1, 101):
                fish_code = request.form.get(f'fish_code_{i}')
                fish_name = request.form.get(f'fish_name_{i}')
                container = request.form.get(f'container_{i}')
                quantity = request.form.get(f'quantity_{i}')
                weight = request.form.get(f'weight_{i}')
                unit_price = request.form.get(f'unit_price_{i}')
                destination = request.form.get(f'destination_{i}')

                if fish_code and weight and unit_price:
                    try:
                        weight_f = float(weight)
                        quantity_f = float(quantity) if quantity else 0.0
                        unit_price_i = int(unit_price)
                        container_v = container or ''
                        fish_name_v = fish_name or ''
                        destination_v = destination or ''
                        total_weight += weight_f
                        c.execute("""
                            INSERT INTO fish_receipt_details
                            (receipt_id, line_no, fish_code, fish_name, container, quantity, weight, unit_price, destination, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """, (receipt_id, i, fish_code, fish_name_v, container_v, quantity_f, weight_f, unit_price_i, destination_v))
                    except ValueError:
                        pass

            c.execute("UPDATE fish_receipts SET total_weight = ? WHERE id = ?", (total_weight, receipt_id))
            conn.commit()

            c.execute("""
                SELECT r.id, r.receipt_no, r.receipt_date, r.fisherman_name, r.total_weight
                FROM fish_receipts r WHERE r.id = ?
            """, (receipt_id,))
            receipt_info = c.fetchone()

            c.execute("""
                SELECT fish_code, fish_name, container, quantity, weight, unit_price, destination
                FROM fish_receipt_details WHERE receipt_id = ? ORDER BY id
            """, (receipt_id,))
            receipt_details = c.fetchall()
            conn.close()

            return render_template("fish_receipt.html",
                                   receipt_id=receipt_info[0],
                                   receipt_no=receipt_info[1],
                                   receipt_date=receipt_info[2],
                                   fisherman_name=receipt_info[3],
                                   total_weight=receipt_info[4],
                                   details=receipt_details,
                                   success=True,
                                   edit_mode=True)

        except Exception as e:
            conn.rollback()
            conn.close()
            return render_template("fish_receipt.html",
                                   error=f"エラーが発生しました: {str(e)}",
                                   today=receipt_date,
                                   fisherman_name=fisherman_name)

    # GETリクエスト
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT company_name FROM companies LIMIT 1")
    result = c.fetchone()
    company_name = result[0] if result else ""
    success = request.args.get('success', False)

    receipt_id = request.args.get('receipt_id')
    if receipt_id:
        try:
            c.execute("""
                SELECT r.id, r.receipt_no, r.receipt_date, r.fisherman_name, r.total_weight
                FROM fish_receipts r WHERE r.id = ?
            """, (receipt_id,))
            receipt_info = c.fetchone()
            if receipt_info:
                c.execute("""
                    SELECT fish_code, fish_name, container, quantity, weight, unit_price, destination
                    FROM fish_receipt_details WHERE receipt_id = ? ORDER BY id
                """, (receipt_info[0],))
                receipt_details = c.fetchall()
                conn.close()
                return render_template("fish_receipt.html",
                                       receipt_id=receipt_info[0],
                                       receipt_no=receipt_info[1],
                                       receipt_date=receipt_info[2],
                                       fisherman_name=receipt_info[3],
                                       total_weight=receipt_info[4],
                                       details=receipt_details,
                                       edit_mode=True)
        except Exception as e:
            conn.close()
            return render_template("fish_receipt.html",
                                   error=f"エラーが発生しました: {str(e)}",
                                   today=today,
                                   fisherman_name=company_name)

    receipt_date = request.args.get('receipt_date', today)
    try:
        c.execute("""
            SELECT r.id, r.receipt_no, r.receipt_date, r.fisherman_name, r.total_weight
            FROM fish_receipts r WHERE r.receipt_date = ?
            ORDER BY r.id DESC LIMIT 1
        """, (receipt_date,))
        receipt_info = c.fetchone()
        if receipt_info:
            c.execute("""
                SELECT fish_code, fish_name, container, quantity, weight, unit_price, destination
                FROM fish_receipt_details WHERE receipt_id = ? ORDER BY id
            """, (receipt_info[0],))
            receipt_details = c.fetchall()
            conn.close()
            return render_template("fish_receipt.html",
                                   receipt_id=receipt_info[0],
                                   receipt_no=receipt_info[1],
                                   receipt_date=receipt_info[2],
                                   fisherman_name=receipt_info[3],
                                   total_weight=receipt_info[4],
                                   details=receipt_details,
                                   edit_mode=True)
    except Exception:
        pass

    conn.close()
    return render_template("fish_receipt.html", today=today, fisherman_name=company_name, success=success)


@fish_receipt_bp.route("/list")
def fish_receipt_list():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT r.receipt_no, r.receipt_date, r.fisherman_name, r.total_weight, c.company_name
        FROM fish_receipts r
        JOIN companies c ON r.company_id = c.id
        ORDER BY r.receipt_date DESC, r.receipt_no DESC
    """)
    receipts = c.fetchall()
    conn.close()
    return render_template("fish_receipt_list.html", receipts=receipts)


@fish_receipt_bp.route("/check_fish_code")
def check_fish_code():
    code = request.args.get('code')
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT code FROM fish_types WHERE code = ?", (code,))
    exists = c.fetchone() is not None
    conn.close()
    return jsonify({'exists': exists})


@fish_receipt_bp.route("/api/fish_types/<code>")
def get_fish_type_by_code(code):
    if not code:
        return jsonify({'error': '魚種コードが指定されていません'}), 400

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM fish_types WHERE code = ?", (code,))
    result = c.fetchone()
    conn.close()

    if result:
        return jsonify({'name': result[0]})
    else:
        return jsonify({'error': '指定された魚種コードは登録されていません'}), 404


# =====================================================
# OCR 関連エンドポイント
# =====================================================

@fish_receipt_bp.route('/ocr', methods=['POST'])
def ocr_upload():
    """カメラ画像を受け取り Claude API で解析して確認画面へリダイレクト。"""
    if 'image' not in request.files:
        return jsonify({'error': '画像ファイルが見つかりません'}), 400

    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'error': '画像が選択されていません'}), 400

    image_bytes = image_file.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10MB上限
        return jsonify({'error': '画像サイズが大きすぎます（10MB以下にしてください）'}), 400

    try:
        result = ocr_service.extract_slip_data(image_bytes)
        # セッションに OCR 結果を保存（確認画面で使用）
        session['ocr_result'] = result
        return jsonify({'status': 'ok', 'redirect': url_for('fish_receipt.ocr_review')})
    except json.JSONDecodeError:
        return jsonify({'error': 'OCR結果の解析に失敗しました。画像を撮り直してください。'}), 500
    except Exception as e:
        return jsonify({'error': f'OCR処理中にエラーが発生しました: {str(e)}'}), 500


@fish_receipt_bp.route('/ocr/review', methods=['GET'])
def ocr_review():
    """OCR確認・修正画面を表示。"""
    ocr_result = session.get('ocr_result')
    if not ocr_result:
        return redirect(url_for('fish_receipt.fish_receipt'))
    return render_template('ocr_review.html', ocr_result=ocr_result)


@fish_receipt_bp.route('/ocr/confirm', methods=['POST'])
def ocr_confirm():
    """確認・修正済みデータをセッション保存し、修正差分をDBに記録して登録画面へ。"""
    ocr_result = session.get('ocr_result', {})
    image_hash = ocr_result.get('image_hash', '')

    # フォームから確定データを取得
    receipt_date = request.form.get('receipt_date', '')
    fisherman_name = request.form.get('fisherman_name', '')

    confirmed_details = []
    for i in range(1, 21):
        fish_code = request.form.get(f'fish_code_{i}')
        if not fish_code and not request.form.get(f'weight_{i}'):
            continue  # 空行はスキップ
        confirmed_details.append({
            'fish_code':   request.form.get(f'fish_code_{i}'),
            'fish_name':   request.form.get(f'fish_name_{i}'),
            'container':   request.form.get(f'container_{i}'),
            'quantity':    request.form.get(f'quantity_{i}'),
            'weight':      request.form.get(f'weight_{i}'),
            'unit_price':  request.form.get(f'unit_price_{i}'),
            'destination': request.form.get(f'destination_{i}'),
        })

    confirmed_data = {
        'receipt_date':    receipt_date,
        'fisherman_name':  fisherman_name,
        'details':         confirmed_details,
    }

    # 修正差分を保存（精度向上用）
    ocr_service.save_corrections(ocr_result, confirmed_data, image_hash)

    # 確定データをセッションに保存して登録画面へ
    session['confirmed_ocr'] = confirmed_data
    session.pop('ocr_result', None)

    # 登録画面へリダイレクト（確定データはセッションから取得）
    return redirect(url_for('fish_receipt.fish_receipt_from_ocr'))


@fish_receipt_bp.route('/from_ocr', methods=['GET'])
def fish_receipt_from_ocr():
    """OCR確認後の登録画面。セッションのデータをフォームに引き渡す。"""
    confirmed = session.pop('confirmed_ocr', None)
    if not confirmed:
        return redirect(url_for('fish_receipt.fish_receipt'))

    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT company_name FROM companies LIMIT 1')
    result = c.fetchone()
    conn.close()
    company_name = result[0] if result else ''

    # details を (fish_code, fish_name, container, quantity, weight, unit_price, destination) タプルに変換
    details = []
    for d in confirmed.get('details', []):
        details.append((
            d.get('fish_code') or '',
            d.get('fish_name') or '',
            d.get('container') or '',
            d.get('quantity') or '',
            d.get('weight') or '',
            d.get('unit_price') or '',
            d.get('destination') or '',
        ))

    return render_template(
        'fish_receipt.html',
        today=confirmed.get('receipt_date', datetime.now().strftime('%Y-%m-%d')),
        receipt_date=confirmed.get('receipt_date', ''),
        fisherman_name=confirmed.get('fisherman_name', company_name),
        details=details,
        edit_mode=False,      # 新規登録モード（「登録」ボタンを表示）
        ocr_prefilled=True,   # OCRからの遷移フラグ（明細データを表示）
    )
