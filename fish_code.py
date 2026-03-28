from flask import Blueprint, render_template, request, redirect, url_for
from db import get_connection

fish_code_bp = Blueprint('fish_code', __name__)


def format_fish_code(code):
    code_str = str(code).zfill(4)
    return f"{code_str[:2]}-{code_str[2:]}"


def parse_fish_code(code_str):
    if code_str and '-' in code_str:
        code_str = code_str.replace('-', '')
    return int(code_str) if code_str.isdigit() else 0


@fish_code_bp.route("/fish_code", methods=['GET', 'POST'])
def fish_code():
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        edit_code = request.form.get('edit_code')

        code = parse_fish_code(code)
        if edit_code:
            edit_code = parse_fish_code(edit_code)

        if not code or not name:
            return render_template("fish_code.html", error="正しく入力してください")

        conn = get_connection()
        c = conn.cursor()

        if edit_code:
            c.execute("UPDATE fish_types SET code = ?, name = ? WHERE code = ?", (code, name, edit_code))
        else:
            c.execute("SELECT COUNT(*) FROM fish_types WHERE code = ?", (code,))
            if c.fetchone()[0] > 0:
                conn.close()
                return render_template("fish_code.html", error="この魚種コードは既に登録されています")
            c.execute("INSERT INTO fish_types (code, name) VALUES (?, ?)", (code, name))

        conn.commit()
        conn.close()
        return redirect(url_for('fish_code_list.fish_code_list'))

    edit_code = request.args.get('edit_code')
    if edit_code:
        numeric_code = parse_fish_code(edit_code)
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT code, name FROM fish_types WHERE code = ?", (numeric_code,))
        fish_data = c.fetchone()
        conn.close()

        if fish_data:
            formatted_code = format_fish_code(fish_data[0])
            fish_type = (formatted_code, fish_data[1])
            return render_template("fish_code.html", fish_type=fish_type, edit_code=numeric_code)

    return render_template("fish_code.html")
