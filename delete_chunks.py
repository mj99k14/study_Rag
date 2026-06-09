import sys
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

PG_URL = "postgresql://{user}:{pw}@{host}:{port}/{db}".format(
    user=os.getenv("PG_USER", "postgres"),
    pw=os.getenv("PG_PASSWORD", ""),
    host=os.getenv("PG_HOST", "localhost"),
    port=os.getenv("PG_PORT", "5432"),
    db=os.getenv("PG_DB", "pdfrag"),
)

def delete_source(source_pattern: str):
    conn = psycopg2.connect(PG_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pdf_chunks WHERE source LIKE %s", (f"%{source_pattern}%",))
    count = cur.fetchone()[0]
    cur.execute("DELETE FROM pdf_chunks WHERE source LIKE %s", (f"%{source_pattern}%",))
    print(f"삭제 완료: {count}개 청크 ({source_pattern})")
    conn.close()

def delete_all():
    conn = psycopg2.connect(PG_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pdf_chunks")
    count = cur.fetchone()[0]
    cur.execute("DELETE FROM pdf_chunks")
    print(f"전체 삭제 완료: {count}개 청크")
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        delete_source(sys.argv[1])
    else:
        delete_all()
