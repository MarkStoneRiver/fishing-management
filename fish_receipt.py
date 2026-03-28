from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from db import get_connection
from datetime import datetime

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
            for i in range(1, 11):
                fish_code = request.form.get(f'fish_code_{i}')
                fish_name = request.form.get(f'fish_name_{i}')
                container = request.form.get(f'container_{i}')
                quantity = request.form.get(f'quantity_{i}')
                weight = request.form.get(f'weight_{i}')
                unit_price = request.form.get(f'unit_price_{i}')
                destination = request.form.get(f'destination_{i}')

                if fish_code and fish_name and container and quantity and weight and unit_price and destination:
                    try:
                        weight_f = float(weight)
                        quantity_f = float(quantity)
                        unit_price_i = int(unit_price)
                        total_weight += weight_f
                        c.execute("""
                            INSERT INTO fish_receipt_details
                            (receipt_id, line_no, fish_code, fish_name, container, quantity, weight, unit_price, destination, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """, (receipt_id, i, fish_code, fish_name, container, quantity_f, weight_f, unit_price_i, destination))
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
