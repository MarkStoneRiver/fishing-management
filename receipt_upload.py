# receipt_upload.py
# このモジュールは現在使用しません（OCR機能は無効化済み）
from flask import Blueprint, render_template

receipt_upload_bp = Blueprint('receipt_upload', __name__, url_prefix='/receipt_upload')


@receipt_upload_bp.route('/', methods=['GET', 'POST'])
def receipt_upload():
    """伝票自動取込（OCR）機能は現在無効です。"""
    return render_template('receipt_upload.html',
                           message='この機能は現在ご利用できません。',
                           error=True)
