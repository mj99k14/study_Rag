import json
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS pdf_chunks (
    id            TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    label         TEXT NOT NULL,
    pages         TEXT NOT NULL,
    summary       TEXT NOT NULL,
    original_text TEXT NOT NULL,
    embedding     JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pdf_chunks_source ON pdf_chunks (source);
"""


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


class VectorStore:
    def __init__(self, pg_url: str, model_name: str):
        self.conn = psycopg2.connect(pg_url)
        self.conn.autocommit = True
        with self.conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
        self.model = SentenceTransformer(model_name)

    def add_processed_chunks(self, chunks: list[dict], source: str):
        summaries = [c["summary"] for c in chunks]
        embeddings = self.model.encode(summaries).tolist()
        rows = [
            (
                f"{source}_{c['id']}",
                source,
                c["label"],
                str(c["pages"]),
                c["summary"],
                c["original_text"],
                json.dumps(emb),
            )
            for c, emb in zip(chunks, embeddings)
        ]
        with self.conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO pdf_chunks (id, source, label, pages, summary, original_text, embedding)
                VALUES %s
                ON CONFLICT (id) DO UPDATE SET
                    summary       = EXCLUDED.summary,
                    original_text = EXCLUDED.original_text,
                    embedding     = EXCLUDED.embedding
                """,
                rows,
            )

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT source, label, pages, summary, original_text, embedding FROM pdf_chunks"
            )
            rows = cur.fetchall()

        if not rows:
            return []

        query_vec = self.model.encode([query])[0]
        scored = []
        for source, label, pages, summary, original_text, emb_json in rows:
            emb = np.array(json.loads(emb_json) if isinstance(emb_json, str) else emb_json)
            score = _cosine_similarity(query_vec, emb)
            scored.append((score, source, label, pages, summary, original_text))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "summary": s,
                "original_text": ot,
                "source": src,
                "label": lbl,
                "pages": pg,
            }
            for _, src, lbl, pg, s, ot in scored[:n_results]
        ]

    def list_documents(self) -> list[str]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT DISTINCT source FROM pdf_chunks ORDER BY source")
            return [row[0] for row in cur.fetchall()]

    def document_exists(self, source: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pdf_chunks WHERE source = %s LIMIT 1", (source,))
            return cur.fetchone() is not None
