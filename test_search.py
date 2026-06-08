from dotenv import load_dotenv
import os
load_dotenv()

from vector_store import VectorStore

store = VectorStore(
    os.getenv("DB_DIR", "./chroma_db"),
    os.getenv("EMBED_MODEL", "paraphrase-multilingual-mpnet-base-v2"),
)

results = store.search("운영기관 자격 요건") 
for r in results:
    print(r["label"], r["pages"])
    print(r["summary"])
    print()
