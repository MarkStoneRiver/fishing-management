from flask import Blueprint, render_template, request, redirect, url_for
from db import get_connection

buyers_bp = Blueprint('buyers', __name__, url_prefix='/buyers')


@buyers_bp.route('/', methods=['GET'])
def index():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, code, name FROM buyers ORDER BY code')
    buyers = c.fetchall()
    conn.close()

    message = request.args.get('message')
    error = request.args.get('error')
    new_buyer = request.args.get('new') == 'true'

    return render_template('buyers.html', buyers=buyers, message=message, error=error, new_buyer=new_buyer)


@buyers_bp.route('/new', methods=['GET'])
def new():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, code, name FROM buyers ORDER BY code')
    buyers = c.fetchall()
    conn.close()
    return render_template('buyers.html', buyers=buyers, new_buyer=True)


@buyers_bp.route('/', methods=['POST'])
def add_buyer():
    code = request.form.get('code')
    name = request.form.get('name')

    if not code or not name:
        return redirect(url_for('buyers.index', error='コードと買受人名を入力してください'))

    conn = get_connection()
    c = conn.cursor()

    c.execute('SELECT id FROM buyers WHERE code = ?', (code,))
    existing = c.fetchone()
    if existing:
        conn.close()
        return redirect(url_for('buyers.index', error='入力されたコードは既に使用されています'))

    try:
        c.execute('INSERT INTO buyers (code, name) VALUES (?, ?)', (code, name))
        conn.commit()
        conn.close()
        return redirect(url_for('buyers.index', message='買受人を登録しました'))
    except Exception as e:
        conn.close()
        return redirect(url_for('buyers.index', error=f'エラーが発生しました: {str(e)}'))


@buyers_bp.route('/edit/<int:id>', methods=['GET'])
def edit(id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, code, name FROM buyers WHERE id = ?', (id,))
    buyer = c.fetchone()

    if not buyer:
        conn.close()
        return redirect(url_for('buyers.index', error='指定された買受人が見つかりません'))

    c.execute('SELECT id, code, name FROM buyers ORDER BY code')
    buyers = c.fetchall()
    conn.close()
    return render_template('buyers.html', buyers=buyers, edit_buyer=buyer)


@buyers_bp.route('/update/<int:id>', methods=['POST'])
def update(id):
    code = request.form.get('code')
    name = request.form.get('name')

    if not code or not name:
        return redirect(url_for('buyers.index', error='コードと買受人名を入力してください'))

    conn = get_connection()
    c = conn.cursor()

    c.execute('SELECT id FROM buyers WHERE id = ?', (id,))
    buyer = c.fetchone()
    if not buyer:
        conn.close()
        return redirect(url_for('buyers.index', error='指定された買受人が見つかりません'))

    c.execute('SELECT id FROM buyers WHERE code = ? AND id != ?', (code, id))
    existing = c.fetchone()
    if existing:
        conn.close()
        return redirect(url_for('buyers.index', error='入力されたコードは既に他の買受人で使用されています'))

    try:
        c.execute('UPDATE buyers SET code = ?, name = ? WHERE id = ?', (code, name, id))
        conn.commit()
        conn.close()
        return redirect(url_for('buyers.index', message='買受人情報を更新しました'))
    except Exception as e:
        conn.close()
        return redirect(url_for('buyers.index', error=f'エラーが発生しました: {str(e)}'))


@buyers_bp.route('/delete/<int:id>', methods=['GET'])
def delete(id):
    conn = get_connection()
    c = conn.cursor()

    c.execute('SELECT name FROM buyers WHERE id = ?', (id,))
    buyer = c.fetchone()
    if not buyer:
        conn.close()
        return redirect(url_for('buyers.index', error='指定された買受人が見つかりません'))

    c.execute('SELECT COUNT(*) as count FROM fish_receipt_details WHERE destination = (SELECT code FROM buyers WHERE id = ?)', (id,))
    result = c.fetchone()
    if result and result['count'] > 0:
        conn.close()
        return redirect(url_for('buyers.index', error=f'買受人「{buyer["name"]}」は伝票で使用されているため削除できません'))

    try:
        c.execute('DELETE FROM buyers WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        return redirect(url_for('buyers.index', message=f'買受人「{buyer["name"]}」を削除しました'))
    except Exception as e:
        conn.close()
        return redirect(url_for('buyers.index', error=f'エラーが発生しました: {str(e)}'))
