from flask import Blueprint, render_template, request
from db import get_connection
from datetime import datetime, timedelta
import json
import random

fish_graph_bp = Blueprint('fish_graph', __name__)


@fish_graph_bp.route('/fish_graph', methods=['GET'])
def fish_graph():
    # URLパラメータを取得
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    data_type = request.args.get('data_type', 'weight')

    # 魚種コードは複数選択可能なため、getlistを使用
    selected_fish_codes = request.args.getlist('fish_code')

    # データタイプに基づいたラベルとデータフィールドを設定
    if data_type == 'weight':
        y_axis_label = '重量 (kg)'
        data_field = 'total_weight'
        graph_title = '魚種別水揚げ重量推移'
    elif data_type == 'quantity':
        y_axis_label = '尾数'
        data_field = 'total_quantity'
        graph_title = '魚種別水揚げ尾数推移'
    else:  # amount
        y_axis_label = '金額 (円)'
        data_field = 'total_amount'
        graph_title = '魚種別水揚げ金額推移'

    # 日付が指定されていない場合は今月を設定
    if not start_date:
        today = datetime.today()
        start_date = datetime(today.year, today.month, 1).strftime('%Y-%m-%d')

    if not end_date:
        end_date = datetime.today().strftime('%Y-%m-%d')

    # データベース接続
    conn = get_connection()

    # 指定された期間に存在する魚種一覧を取得
    fish_types_query = """
    SELECT DISTINCT ft.code, ft.name
    FROM fish_types ft
    JOIN fish_receipt_details d ON ft.code = d.fish_code
    JOIN fish_receipts r ON d.receipt_id = r.id
    WHERE r.receipt_date BETWEEN ? AND ?
    ORDER BY ft.code
    """
    fish_types_cursor = conn.execute(fish_types_query, (start_date, end_date))
    fish_types = [(str(row['code']), row['name']) for row in fish_types_cursor.fetchall()]

    # 指定された期間の魚種ごとの日別データを取得
    fish_code_condition = ""
    if selected_fish_codes and '' not in selected_fish_codes:
        placeholders = ','.join(['?' for _ in selected_fish_codes])
        fish_code_condition = f" AND d.fish_code IN ({placeholders})"

    query = f"""
    SELECT
        d.fish_code,
        ft.name as fish_type_name,
        r.receipt_date,
        SUM(CASE WHEN '{data_field}' = 'total_weight' THEN d.weight
                 WHEN '{data_field}' = 'total_quantity' THEN d.quantity
                 WHEN '{data_field}' = 'total_amount' THEN d.weight * d.unit_price
                 ELSE 0 END) as data_value
    FROM
        fish_receipts r
    JOIN
        fish_receipt_details d ON r.id = d.receipt_id
    JOIN
        fish_types ft ON d.fish_code = ft.code
    WHERE
        r.receipt_date BETWEEN ? AND ?
        {fish_code_condition}
    GROUP BY
        d.fish_code, r.receipt_date
    ORDER BY
        r.receipt_date, d.fish_code
    """

    params = [start_date, end_date]
    if selected_fish_codes and '' not in selected_fish_codes:
        params.extend(selected_fish_codes)

    cursor = conn.execute(query, tuple(params))
    results = cursor.fetchall()

    # 日付の一覧を作成（開始日から終了日まで）
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)

    # 魚種ごとのデータを整理
    fish_data = {}
    for row in results:
        if row['fish_code'] not in fish_data:
            fish_data[row['fish_code']] = {
                'name': row['fish_type_name'],
                'data': {date: 0 for date in dates}
            }
        fish_data[row['fish_code']]['data'][row['receipt_date']] = row['data_value']

    # Chart.js用のデータセット作成
    datasets = []
    colors = [
        'rgba(255, 99, 132, 0.7)',
        'rgba(54, 162, 235, 0.7)',
        'rgba(255, 206, 86, 0.7)',
        'rgba(75, 192, 192, 0.7)',
        'rgba(153, 102, 255, 0.7)',
        'rgba(255, 159, 64, 0.7)',
        'rgba(199, 199, 199, 0.7)',
        'rgba(83, 102, 255, 0.7)',
        'rgba(40, 159, 64, 0.7)',
        'rgba(210, 105, 30, 0.7)'
    ]

    color_index = 0
    for fish_code, info in fish_data.items():
        color = colors[color_index % len(colors)]
        datasets.append({
            'label': f"{fish_code} - {info['name']}",
            'data': list(info['data'].values()),
            'fill': False,
            'borderColor': color,
            'backgroundColor': color,
            'tension': 0.1
        })
        color_index += 1

    has_data = len(datasets) > 0

    conn.close()

    return render_template(
        'fish_graph.html',
        start_date=start_date,
        end_date=end_date,
        data_type=data_type,
        dates=dates,
        datasets=datasets,
        y_axis_label=y_axis_label,
        graph_title=graph_title,
        has_data=has_data,
        fish_types=fish_types,
        selected_fish_codes=selected_fish_codes
    )
