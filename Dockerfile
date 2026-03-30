# syntax=docker/dockerfile:1
FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# DBを保存するディレクトリを作成
RUN mkdir -p /data

# 依存ライブラリをインストール
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# アプリのファイルをコピー
COPY . .

# 静的ファイルのアップロード先ディレクトリを作成
RUN mkdir -p /app/static/uploads

# ポートを開放
EXPOSE 5000

# 起動コマンド（gunicorn で本番起動）
CMD ["sh", "-c", "python3 init_db.py && gunicorn --bind 0.0.0.0:5000 --workers 1 --timeout 300 app:app"]
