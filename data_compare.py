from flask import Blueprint, render_template, request, jsonify
from db import get_connection
from datetime import datetime, timedelta
import calendar

data_compare_bp = Blueprint('data_compare', __name__, url_prefix='/data_compare')


@data_compare_bp.route("/", methods=['GET'])
def data_compare():
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT DISTINCT fisherman_name FROM fish_receipts ORDER BY fisherman_name")
    fishermen_rows = c.fetchall()
    fishermen = [{'name': row[0]} for row in fishermen_rows]

    current_date = datetime.now()
    default_target_month = f"{current_date.year}-{current_date.month:02d}"
    target_month = request.args.get('target_month', default_target_month)

    try:
        year, month = map(int, target_month.split('-'))
        first_day = f"{year}-{month:02d}-01"
        _, last_day_of_month = calendar.monthrange(year, month)
        last_day = f"{year}-{month:02d}-{last_day_of_month}"
    except Exception:
        year = current_date.year
        month = current_date.month
        first_day = f"{year}-{month:02d}-01"
        _, last_day_of_month = calendar.monthrange(year, month)
        last_day = f"{year}-{month:02d}-{last_day_of_month}"

    fisherman = request.args.get('fisherman', '')
    fisher_id = request.args.get('fisher_id', None)

    if not fisherman and fishermen:
        fisherman = fishermen[0]['name']

    c.execute("SELECT code, name FROM buyers ORDER BY code")
    buyers = [{'id': row[0], 'name': row[1]} for row in c.fetchall()]

    results = []
    total_amount = 0

    if fisherman:
        c.execute("SELECT code, name FROM containers ORDER BY code")
        containers = {row[0]: row[1] for row in c.fetchall()}

        query = """
            SELECT
                r.receipt_date, d.fish_code, f.name AS fish_name,
                d.fish_name AS fish_name_detail, d.container, d.quantity,
                d.weight, d.unit_price, d.weight * d.unit_price AS amount,
                d.destination AS buyer_code, b.name AS buyer_name
            FROM fish_receipts r
            JOIN fish_receipt_details d ON r.id = d.receipt_id
            LEFT JOIN fish_types f ON d.fish_code = f.code
            LEFT JOIN buyers b ON d.destination = b.code
            WHERE r.receipt_date BETWEEN ? AND ? AND r.fisherman_name = ?
            ORDER BY r.receipt_date, d.id
        """
        c.execute(query, (first_day, last_day, fisherman))

        for row in c.fetchall():
            receipt_date, fish_code, fish_name, fish_name_detail, container_code, quantity, weight, unit_price, amount, buyer_code, buyer_name = row
            try:
                formatted_date = datetime.strptime(receipt_date, '%Y-%m-%d').strftime('%Y/%m/%d')
            except Exception:
                formatted_date = receipt_date

            container_name = containers.get(container_code, "ばら") if container_code in containers else "ばら"
            display_name = fish_name or ""
            if fish_name_detail:
                display_name = f"{display_name} {fish_name_detail}" if display_name else fish_name_detail

            results.append({
                "receipt_date": formatted_date,
                "fish_code": fish_code or "",
                "fish_name": fish_name or "",
                "fish_name_detail": fish_name_detail or "",
                "display_name": display_name or "不明",
                "container_code": container_code,
                "container_name": container_name,
                "quantity": quantity or 0,
                "weight": weight or 0,
                "unit_price": unit_price or 0,
                "amount": amount or 0,
                "buyer_code": buyer_code or "",
                "buyer_name": buyer_name or "市場",
            })
            total_amount += amount or 0

    conn.close()

    return render_template(
        "data_compare.html",
        results=results,
        total_amount=total_amount,
        fishers=buyers,
        fishermen=fishermen,
        selected_fisher_id=fisher_id,
        fisherman=fisherman,
        target_month=target_month,
    )


@data_compare_bp.route('/api/compare_data')
def get_compare_data():
    month = request.args.get('month')
    fisherman = request.args.get('fisherman')

    conn = get_connection()
    c = conn.cursor()

    try:
        year, month_num = map(int, month.split('-'))
        first_day = f"{year}-{month_num:02d}-01"
        _, last_day_of_month = calendar.monthrange(year, month_num)
        last_day = f"{year}-{month_num:02d}-{last_day_of_month}"

        c.execute("SELECT code, name FROM containers ORDER BY code")
        containers = {row[0]: row[1] for row in c.fetchall()}

        query = """
            SELECT
                r.receipt_date, d.fish_code, f.name AS fish_name,
                d.fish_name AS fish_name_detail, d.container, d.quantity,
                d.weight, d.unit_price, d.weight * d.unit_price AS amount,
                d.destination AS buyer_code, b.name AS buyer_name
            FROM fish_receipts r
            JOIN fish_receipt_details d ON r.id = d.receipt_id
            LEFT JOIN fish_types f ON d.fish_code = f.code
            LEFT JOIN buyers b ON d.destination = b.code
            WHERE r.receipt_date BETWEEN ? AND ? AND r.fisherman_name = ?
            ORDER BY r.receipt_date, d.id
        """
        c.execute(query, (first_day, last_day, fisherman))

        results = []
        for row in c.fetchall():
            receipt_date, fish_code, fish_name, fish_name_detail, container_code, quantity, weight, unit_price, amount, buyer_code, buyer_name = row
            try:
                formatted_date = datetime.strptime(receipt_date, '%Y-%m-%d').strftime('%Y-%m-%d')
            except Exception:
                formatted_date = receipt_date

            container_name = containers.get(container_code, "ばら") if container_code in containers else "ばら"
            display_name = fish_name or ""
            if fish_name_detail:
                display_name = f"{display_name} {fish_name_detail}" if display_name else fish_name_detail

            results.append({
                "receipt_date": formatted_date,
                "fish_code": fish_code or "",
                "fish_name": fish_name or "",
                "fish_name_detail": fish_name_detail or "",
                "display_name": display_name or "不明",
                "container_code": container_code,
                "container_name": container_name,
                "quantity": quantity or 0,
                "weight": weight or 0,
                "unit_price": unit_price or 0,
                "amount": amount or 0,
                "buyer_code": buyer_code or "",
                "buyer_name": buyer_name or "市場",
                "price": "市場",
            })

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()
