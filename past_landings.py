from flask import Blueprint, render_template, request, jsonify
from db import get_connection
from datetime import datetime

past_landings_bp = Blueprint('past_landings', __name__, url_prefix='/past_landings')


def format_fish_code(code):
    if code is None:
        return ""
    try:
        code_str = str(code).zfill(4)
        return f"{code_str[:2]}-{code_str[2:]}"
    except Exception:
        return str(code)


def parse_fish_code(code_str):
    if not code_str:
        return None
    try:
        return int(code_str.replace('-', ''))
    except Exception:
        return None


@past_landings_bp.route("/", methods=['GET'])
def past_landings():
    conn = get_connection()
    c = conn.cursor()

    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))

    today = datetime.now()
    current_year = today.year
    if today.month < 4:
        fiscal_year_start = datetime(current_year - 1, 4, 1)
    else:
        fiscal_year_start = datetime(current_year, 4, 1)

    start_date = request.args.get('start_date', fiscal_year_start.strftime('%Y-%m-%d'))
    fish_code_str = request.args.get('fish_code', None)
    fish_code = parse_fish_code(fish_code_str) if fish_code_str else None

    c.execute("SELECT code, name FROM fish_types ORDER BY code")
    fish_types_raw = c.fetchall()
    fish_types = [(format_fish_code(code), name) for code, name in fish_types_raw]

    query = """
        SELECT
            r.receipt_date, d.fish_code, f.name AS fish_type_name, d.fish_name,
            SUM(d.weight) AS total_weight, SUM(d.quantity) AS total_quantity,
            AVG(d.unit_price) AS avg_unit_price,
            SUM(d.weight * d.unit_price) AS total_amount
        FROM fish_receipt_details d
        JOIN fish_receipts r ON d.receipt_id = r.id
        LEFT JOIN fish_types f ON d.fish_code = f.code
        WHERE r.receipt_date BETWEEN ? AND ?
    """
    params = [start_date, end_date]

    if fish_code:
        query += " AND d.fish_code = ?"
        params.append(fish_code)

    query += " GROUP BY r.receipt_date, d.fish_code, d.fish_name ORDER BY r.receipt_date, d.fish_code, d.fish_name"
    c.execute(query, params)
    fish_data = c.fetchall()

    results = []
    grand_total = {"total_weight": 0, "total_quantity": 0, "total_amount": 0}

    for row in fish_data:
        receipt_date, fc, fish_type_name, fish_name, total_weight, total_quantity, avg_unit_price, total_amount = row
        avg_weight_per_fish = total_weight / total_quantity if total_quantity > 0 else 0
        avg_price_per_fish = total_amount / total_quantity if total_quantity > 0 else 0
        formatted_fish_code = format_fish_code(fc)

        formatted_date = receipt_date
        if receipt_date:
            try:
                formatted_date = datetime.strptime(receipt_date, '%Y-%m-%d').strftime('%Y/%m/%d')
            except Exception:
                pass

        results.append({
            "receipt_date": formatted_date,
            "fish_code": formatted_fish_code,
            "fish_type_name": fish_type_name,
            "fish_name": fish_name,
            "total_weight": total_weight,
            "total_quantity": total_quantity,
            "avg_unit_price": avg_unit_price,
            "avg_weight_per_fish": avg_weight_per_fish,
            "avg_price_per_fish": avg_price_per_fish,
            "total_amount": total_amount,
        })

        grand_total["total_weight"] += total_weight
        grand_total["total_quantity"] += total_quantity
        grand_total["total_amount"] += total_amount

    conn.close()

    return render_template(
        "past_landings.html",
        results=results,
        grand_total=grand_total,
        fish_types=fish_types,
        start_date=start_date,
        end_date=end_date,
        selected_fish_code=fish_code_str,
    )


@past_landings_bp.route("/get_fish_types", methods=['GET'])
def get_fish_types():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        return jsonify({'error': '開始日と終了日を指定してください'}), 400

    try:
        conn = get_connection()
        c = conn.cursor()

        query = """
            SELECT DISTINCT d.fish_code, f.name
            FROM fish_receipt_details d
            JOIN fish_receipts r ON d.receipt_id = r.id
            LEFT JOIN fish_types f ON d.fish_code = f.code
            WHERE r.receipt_date BETWEEN ? AND ?
            ORDER BY d.fish_code
        """
        c.execute(query, (start_date, end_date))
        fish_types_in_period = c.fetchall()
        conn.close()

        fish_types_list = [
            {"code": format_fish_code(code) if code else "", "name": name or "不明"}
            for code, name in fish_types_in_period
        ]
        return jsonify(fish_types_list)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
