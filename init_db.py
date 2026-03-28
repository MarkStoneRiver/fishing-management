import sqlite3
from db import DB_PATH

DB_FILE = DB_PATH


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 魚種マスタ
    c.execute('''
        CREATE TABLE IF NOT EXISTS fish_types (
            id INTEGER PRIMARY KEY,
            code INTEGER,
            name TEXT,
            per_unit_weight REAL
        )
    ''')

    # 容器マスタ
    c.execute('''
        CREATE TABLE IF NOT EXISTS containers (
            id INTEGER PRIMARY KEY,
            code INTEGER,
            name TEXT
        )
    ''')

    # 売先マスタ
    c.execute('''
        CREATE TABLE IF NOT EXISTS buyers (
            id INTEGER PRIMARY KEY,
            code INTEGER,
            name TEXT
        )
    ''')

    # 会社テーブル
    c.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 伝票ヘッダーテーブル
    c.execute('''
        CREATE TABLE IF NOT EXISTS fish_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_no TEXT NOT NULL,
            receipt_date DATE NOT NULL,
            company_id INTEGER NOT NULL,
            fisherman_name TEXT NOT NULL,
            market_name TEXT DEFAULT '羅臼地方卸売市場',
            total_weight REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    ''')

    # 鮮魚受入伝票明細テーブルの作成
    c.execute('''
        CREATE TABLE IF NOT EXISTS fish_receipt_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_id INTEGER NOT NULL,
            line_no INTEGER NOT NULL,
            fish_code INTEGER NOT NULL,
            fish_name TEXT NOT NULL,
            container INTEGER NOT NULL,
            quantity REAL NOT NULL,
            weight REAL NOT NULL,
            unit_price INTEGER NOT NULL,
            destination INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (receipt_id) REFERENCES fish_receipts(id)
        )
    ''')

    # 売買仕切書取込データ
    c.execute('''
        CREATE TABLE IF NOT EXISTS receipt_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_date TEXT,
            filename TEXT,
            fish_code INTEGER,
            container TEXT,
            quantity INTEGER,
            weight REAL,
            unit_price REAL,
            amount REAL,
            buyer TEXT
        )
    ''')

    # 初期魚種コードデータの挿入
    c.execute('DELETE FROM fish_types')

    fish_types_data = [
        (100, 'ほっけ'), (151, 'まぼっけ'), (152, 'しまぼっけ'),
        (251, 'さくらます'), (252, 'からふとます'), (253, 'ますのすけ'),
        (301, 'いか'), (302, 'いか(網)'), (304, 'いか(発砲)'),
        (400, 'すけそ'), (401, 'すけそ(刺網)'), (403, 'すけそ小(刺網)'),
        (404, 'すけそ特大(刺網)'), (411, 'すけそ(底縄)'), (413, 'すけそ小(底縄)'),
        (414, 'すけそ特大(底縄)'), (421, 'すけそ(浮縄)'), (423, 'すけそ小(浮縄)'),
        (424, 'すけそ特大(浮縄)'), (500, 'たら'), (551, 'たら(刺網)'),
        (561, 'たら(底縄)'), (571, 'たら(浮縄)'), (600, 'かれい'),
        (651, 'そうはち'), (652, 'くろがれい'), (653, 'まがれい'),
        (604, 'すながれい'), (605, 'やなぎがれい'), (656, 'まつかわ'),
        (657, 'あぶらがれい'), (658, 'さめがれい'), (659, 'いしがれい'),
        (660, 'ばばがれい'), (661, 'あかがれい'), (662, 'あさばがれい'),
        (663, 'かわがれい'), (700, 'めんめ'), (751, 'めんめ(網)'),
        (752, 'めんめ(釣)'), (800, 'えび'), (801, 'ぼたんえび'),
        (802, 'ほっかいしまえび'), (803, 'なんばんえび'), (804, 'ぶどうえび'),
        (805, 'がさえび'), (900, 'うに'), (901, '殻付うに'),
        (902, '塩水うに'), (1050, 'おひょう'), (1100, 'かに'),
        (1101, 'たらばがに'), (1102, 'けがに'), (1103, 'あぶらがに'),
        (1104, 'ずわいがに'), (1105, 'いばらがに'), (1106, 'べにずわいがに'),
        (1200, 'たこ'), (1201, 'まだこ'), (1202, 'しおだこ'),
        (1203, 'やなぎだこ'), (1300, 'あきさけ'), (1301, 'あきさけ(おす)'),
        (1302, 'あきさけ(めす)'), (1311, 'あきさけ(おす銀)'),
        (1312, 'あきさけ(おすAB)'), (1313, 'あきさけ(おすC)'),
        (1314, 'あきさけ(おすP銀A)'), (1315, 'あきさけ(おすPBC)'),
        (1316, 'あきさけ(おす特大)'), (1317, 'あきさけ(おすキズ)'),
        (1318, 'あきさけ(おすメジカ)'), (1320, 'あきさけ(おすBB)'),
        (1330, 'あきさけ(めす銀A)'), (1331, 'あきさけ(めすBC)'),
        (1332, 'あきさけ(めすB)'), (1333, 'あきさけ(めすC)'),
        (1334, 'あきさけ(めすP銀A)'), (1335, 'あきさけ(めすPBC)'),
        (1336, 'あきさけ(めすキズ)'), (1337, 'あきさけ(めすヌケ)'),
        (1338, 'あきさけ(めすメジカ)'), (1339, 'あきさけ(めすPB)'),
        (1340, 'あきさけ(めすPC)'), (1355, 'ぎんざけ'),
        (1356, 'べにざけ'), (1310, 'あきさけ 羅皇'), (1450, 'ときさけ'),
        (1460, 'けいじ'), (1500, 'さんま'), (1650, 'めぬけ'),
        (1700, 'そい'), (1751, 'あおぞい'), (1752, 'しまぞい'),
        (1703, 'くろぞい'), (1754, 'あかぞい'), (1850, 'からすがれい'),
        (1900, 'つぶ'), (1901, 'まつぶ'), (1902, 'あかつぶ'),
        (1903, 'らうすばい'), (1904, 'けつぶ'), (1905, 'せんきんつぶ'),
        (2000, 'その他'), (2001, 'さめ'), (2002, 'はも'),
        (2003, 'はたはた'), (2004, 'こまい'), (2055, 'きわだ'),
        (2006, 'がや'), (2007, 'かすべ'), (2008, 'こんべ'),
        (2009, 'どすいか'), (2060, 'まぐろ'), (2061, 'ぶり'),
        (2012, 'しいら'), (2013, 'わらずか'), (2014, 'かじか'),
        (2015, 'おおなご'), (2016, 'こなご'), (2017, 'ちか'),
        (2018, 'さば'), (2019, 'あぶらこ'), (2020, 'なまこ'),
        (2021, 'ふぐ'), (2022, 'にしん'), (2023, 'ほたて'),
        (2024, 'いわし'), (2025, 'きゅうり'), (2026, 'めだい'),
        (2027, 'ほや'), (2029, '貝類'), (2030, 'ざつさかな'),
        (2031, '八角'),
    ]

    c.executemany('INSERT INTO fish_types (code, name) VALUES (?, ?)', fish_types_data)

    # 容器マスタ
    c.execute('DELETE FROM containers')
    containers_data = [
        (0, 'タンク'), (1, 'ポリ'), (2, '木'),
        (3, 'うに折'), (4, 'ハッポー'), (5, 'バラ'), (9, 'その他'),
    ]
    c.executemany('INSERT INTO containers (code, name) VALUES (?, ?)', containers_data)

    # 売先マスタ
    c.execute('DELETE FROM buyers')
    buyers_data = [
        (101, '根室食品工場'), (103, 'マルヒ水産'), (104, '市岡商店'),
        (105, '羅臼組合'), (106, '釧路東水冷凍'), (109, '羅臼海産'),
        (110, '渋谷商店'), (111, '池田水産'), (112, '関商店'),
        (113, '川口水産'), (114, '斎藤水産'), (115, '新谷水産'),
        (117, '中西商店'), (118, '中浦商店'), (119, '浜田商店'),
        (120, '稲川水産'), (121, '青木商店'), (122, '和賀商店'),
        (123, '村田水産'), (125, '伊藤商店'), (126, '岡本水産'),
        (127, '葵原商店'), (128, '隈園水産'), (129, '惣万水産'),
        (130, '佐賀冷蔵'), (132, '標津組合'), (133, '笹谷商店'),
        (135, '沢田水産'), (136, '富山商店'), (137, '津山商店'),
        (138, '和田商店'), (139, '野尻商店'), (140, '川合水産'),
        (141, '野付物産'), (143, '三好水産'), (146, 'ウロコ冷凍'),
        (148, '村上物産'), (149, '力ネヒロ'), (150, '合坂水産'),
        (151, '事代漁業KK'), (155, '結城商店'), (157, '前川商店'),
        (158, '旭旭正海産'), (160, '小川商店'), (161, '山崎水産'),
        (163, '豊島商店'), (164, '神内商店'), (165, '輪島水産'),
        (166, '道漁連諸口'), (167, '根室缶詰'), (169, '岩田商店'),
        (170, '五十嵐商店'), (172, '羅臼組合諸口'), (173, '生産者諸口'),
        (174, '舟木商店'), (175, '浩道丸水産'), (176, '高嶋商店'),
        (177, '市場活魚口'), (178, '石田水産'), (179, 'カネマル水産'),
        (180, '西家商店'), (181, '池吉池'), (182, '芦崎商店'),
    ]
    c.executemany('INSERT INTO buyers (code, name) VALUES (?, ?)', buyers_data)

    conn.commit()
    conn.close()

    print("✅ 魚種コードを登録しました。")
    print("✅ 容器マスタを登録しました。")
    print("✅ 売先マスタを登録しました。")


if __name__ == "__main__":
    init_db()
