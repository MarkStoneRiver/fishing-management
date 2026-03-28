from flask import Blueprint, render_template, request, redirect, url_for
from db import get_connection

fish_code_list_bp = Blueprint('fish_code_list', __name__)


def format_fish_code(code):
    code_str = str(code).zfill(4)
    return f"{code_str[:2]}-{code_str[2:]}"


@fish_code_list_bp.route("/fish_code_list")
def fish_code_list():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT code, name FROM fish_types")
    fish_types_raw = c.fetchall()
    fish_types = [(format_fish_code(code), name) for code, name in fish_types_raw]
    conn.close()
    return render_template("fish_code_list.html", fish_types=fish_types)


@fish_code_list_bp.route("/fish_code_delete", methods=['GET', 'POST'])
def fish_code_delete():
    if request.method == 'POST':
        code = request.form.get('code')
    else:
        code = request.args.get('code')

    if code and '-' in code:
        code = code.replace('-', '')

    if code:
        try:
            conn = get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM fish_types WHERE code = ?", (code,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"削除エラー: {e}")
    return redirect(url_for('fish_code_list.fish_code_list'))
