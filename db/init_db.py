# db/init_db.py
import os, psycopg2
db_url = os.getenv("DATABASE_URL")
with open("db/migrations/0001_init.sql") as f:
    sql = f.read()
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute(sql)
conn.commit()
cur.close()
conn.close()
