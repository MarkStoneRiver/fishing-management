# 漁獲システム (Docker版) セットアップガイド

## 概要
このシステムはFlask + SQLiteで動作するWebアプリケーションです。
Dockerコンテナで動かすことで、LAN内の複数PCのブラウザからアクセスし、同じDBを共有できます。

### インストール済みツール

| ツール | URL | 用途 |
|---|---|---|
| **Portainer** | `http://サーバーIP:9000/` | DockerコンテナのGUI管理ツール |
| **File Browser** | `http://サーバーIP:8080/` | サーバー上のファイルをブラウザから操作 |

```
自宅サーバー（Ubuntu + Docker）
  └── コンテナ: Flaskアプリ (ポート 3002)
          ↕
      /mnt/nas_data/fishery/data/gyokaku.db（NASに永続保存）

各PCのブラウザ → http://[サーバーのIP]:3002/
```

---

## ① Ubuntuサーバーへのファイル転送

### 【推奨】File Browser を使う方法（ターミナル不要）

1. ブラウザで File Browser を開く:
   ```
   http://サーバーのIP:8080/
   ```
2. 転送先フォルダ（例: `/home/ユーザー名/`）に移動
3. 画面上部の **「Upload」** ボタンをクリック
4. `Docker_Amount_Fishes` フォルダ内のファイルを選択してアップロード

> **フォルダごとアップロードする場合**: ブラウザによっては「フォルダのアップロード」に対応しています。  
> 非対応の場合は、先にFile BrowserでフォルダをGUI上で作成し、ファイルを個別にアップロードしてください。

---

### 【その他の方法】

| 方法 | コマンド / 操作 |
|---|---|
| SCP（Windows PowerShell） | `scp -r H:\Antigravity_Projects\Docker_Amount_Fishes ユーザー名@192.168.x.x:/home/ユーザー名/` |
| USBメモリ | ファイルをUSBにコピーしてサーバーで貼り付け |

---

## ② Ubuntuサーバーの初期設定

### Dockerのインストール
サーバーのターミナルで以下を実行:

```bash
# パッケージリストを更新
sudo apt update

# Dockerをインストール
sudo apt install -y docker.io docker-compose-plugin

# Dockerサービスを起動・自動起動設定
sudo systemctl enable --now docker

# 現在のユーザーをdockerグループに追加（sudoなしでdockerを使えるようにする）
sudo usermod -aG docker $USER

# グループ変更を反映（一度ログアウトして再ログインでもOK）
newgrp docker
```

### インストール確認
```bash
docker --version
docker compose version
```

---

## ③ アプリの起動

```bash
# Docker_Amount_Fishes フォルダに移動
cd /home/ユーザー名/Docker_Amount_Fishes

# NASマウントポイントのディレクトリが存在するか確認（存在しない場合は作成）
mkdir -p /mnt/nas_data/fishery/data

# コンテナをビルドして起動（初回はビルドに数分かかります）
docker compose up -d --build
```

起動確認:
```bash
docker ps
# NAMES: gyokaku_app が Running と表示されればOK
```

---

## ④ 各PCからのアクセス方法

1. **サーバーのIPアドレスを確認する**（サーバー上で実行）:
   ```bash
   ip addr show | grep inet
   # 例: 192.168.1.100 のようなローカルIPアドレスが表示されます
   ```

2. **各PCのブラウザでアクセス**:
   ```
   http://192.168.1.100:3002/
   ```
   ※ `192.168.1.100` の部分をサーバーの実際のIPに変更してください

---

## ⑤ ファイアウォールの設定（必要な場合）

Ubuntuにufwが有効になっている場合は、ポートを開放します:
```bash
sudo ufw allow 3002/tcp
sudo ufw reload
```

---

## ⑥ よく使うコマンド

| 操作 | コマンド |
|---|---|
| アプリを起動 | `docker compose up -d` |
| アプリを停止 | `docker compose down` |
| ログを見る | `docker compose logs -f` |
| 再起動 | `docker compose restart` |
| アプリを更新（コード変更後） | `docker compose up -d --build` |

---

## ⑦ データのバックアップ

DBファイルは `/mnt/nas_data/fishery/data/gyokaku.db` に保存されます。
このファイルをコピーするだけでバックアップになります。

```bash
# バックアップ例（毎日自動バックアップしたい場合はcronに登録）
cp /mnt/nas_data/fishery/data/gyokaku.db ~/backup_gyokaku_$(date +%Y%m%d).db
```

---

## ⑧ 自動起動設定（OS起動時に自動でアプリを起動）

`docker-compose.yml` に `restart: always` が設定されているため、
Dockerが起動すれば自動的にアプリも起動します。

Dockerを自動起動するには:
```bash
sudo systemctl enable docker
```

---

## ⑨ トラブルシューティング

### アクセスできない場合
```bash
# コンテナが起動しているか確認
docker ps

# ログを確認
docker compose logs
```

### DBが初期化されない場合
```bash
# NASマウントポイントの権限を確認
ls -la /mnt/nas_data/fishery/data/

# 権限を修正
chmod 755 /mnt/nas_data/fishery/data/
```

### ポートが使用中のエラーが出る場合
別のポートに変更する（例: 8080番）:
`docker-compose.yml` の `ports` を以下のように変更:
```yaml
ports:
  - "8080:5000"
```
アクセスURLが `http://サーバーIP:8080/` になります。

### NASがマウントされていない場合
```bash
# マウント状態を確認
mount | grep nas_data

# マウントされていない場合は手動でマウント（環境に合わせて変更）
sudo mount -t cifs //NASのIP/共有名 /mnt/nas_data/fishery -o username=ユーザー名
```

---

## ⑩ Portainerを使ったDocker管理（GUIで操作）

Portainerがインストール済みの場合、ターミナルを使わずにブラウザ上でDockerの操作が可能です。

### Portainerへのアクセス
```
http://サーバーのIP:9000/
```

---

### アプリの初回デプロイ（Stacks機能を使う）

Portainerの **Stacks** は `docker-compose.yml` をGUIから実行できる機能です。

1. Portainerにログインし、左メニューの **「Stacks」** をクリック
2. **「+ Add stack」** ボタンをクリック
3. 以下を入力:
   - **Name**: `gyokaku-app`（任意の名前）
   - **Build method**: `Upload` を選択
   - `docker-compose.yml` ファイルをアップロード
4. **「Deploy the stack」** ボタンをクリック

> **補足**: `docker-compose.yml` はFile Browserでサーバーにアップロードしておき、  
> **Build method** を `Repository` や `Web editor` に切り替えて内容を貼り付けてもOKです。

---

### コンテナの起動・停止・再起動

1. 左メニューの **「Containers」** をクリック
2. コンテナ一覧から **`gyokaku_app`** を探す
3. 右側のボタンで操作:

| 操作 | ボタン |
|---|---|
| 起動 | ▶ Start |
| 停止 | ■ Stop |
| 再起動 | 🔄 Restart |
| ログ確認 | 📋 Logs |

---

### アプリの更新（コード変更後に再ビルド）

コードを更新した場合は、Stack単位で再デプロイします:

1. 左メニューの **「Stacks」** をクリック
2. **`gyokaku-app`** をクリックして詳細画面へ
3. 「Update the stack」セクションで **「Re-pull image and redeploy」** にチェック
4. **「Update the stack」** ボタンをクリック

> ⚠️ コードの変更は事前にFile Browserでサーバー上のファイルを上書きしてください。

---

### ログの確認

1. 左メニューの **「Containers」** をクリック
2. コンテナ名 **`gyokaku_app`** をクリック
3. 上部メニューの **「Logs」** タブをクリック
4. リアルタイムでログが表示されます（`Auto-refresh logs` をONにすると自動更新）

---

### File Browserを使ったファイル管理

File BrowserはサーバーのファイルをブラウザのGUIで操作できるツールです。

```
http://サーバーのIP:8080/
```

主な用途:
- Windowsから `docker-compose.yml` やアプリファイルをアップロード
- NAS上の `gyokaku.db` をダウンロード（バックアップ）
- ログファイルの閲覧

> **SCPやターミナルを使わずに**、すべてのファイル操作をブラウザから行える点が便利です。
