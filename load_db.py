import sqlite3
import json
from pathlib import Path
exit()
DATA_DIR = Path(__file__).parent / "data"

with open(DATA_DIR/"cards.json", "r", encoding="UTF-8") as f:
    cards = json.load(f)

conn = sqlite3.connect(DATA_DIR/"demo.db")  # ① 连：文件不存在会自动创建
cur = conn.cursor()                # ② 拿游标
#cur.execute("...SQL...")           # ③ 执行（DDL / 增删查都走它）
cur.execute("""
    CREATE TABLE IF NOT EXISTS `public_affairs` (
        id INTEGER PRIMARY KEY,
        title TEXT,
        main_item TEXT,
        sub_item TEXT,
        time_limit TEXT,
        materials TEXT,
        form_fields TEXT,
        feedback_fields TEXT,
        accept_conditions TEXT,
        secondary_items TEXT,
        legal_basis TEXT,
        process TEXT,
        service_target TEXT,
        admin_level TEXT
    )
    """)

for card in cards:
    cur.execute("""
        INSERT INTO public_affairs (title, main_item, sub_item, time_limit, materials, form_fields, feedback_fields, 
        accept_conditions, secondary_items, legal_basis, process, service_target, admin_level) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, tuple(card.values()))

cur.execute("""
        SELECT count(*) FROM public_affairs
    """)

print(cur.fetchone()[0])

conn.commit()                      # ④ 提交
conn.close()                       # ⑤ 关




