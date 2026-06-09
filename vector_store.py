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

# 한국어 조사/어미 — 긴 것부터 매칭해야 오탐 방지
_KO_ENDINGS = ["에서", "으로", "에게", "이야", "는", "은", "가", "이", "을", "를", "의", "에", "로", "과", "와", "도", "만"]


def _strip_ko_postposition(token: str) -> str:
    for ending in sorted(_KO_ENDINGS, key=len, reverse=True):
        if token.endswith(ending) and len(token) - len(ending) >= 2:
            return token[:-len(ending)]
    return token


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
                "SELECT id, source, label, pages, summary, original_text, embedding FROM pdf_chunks"
            )
            rows = cur.fetchall()

        if not rows:
            return []

        # ── 벡터 검색 ──────────────────────────────────────────────
        query_vec = self.model.encode([query])[0]
        data: dict[str, dict] = {}
        vector_ranked: list[tuple[float, str]] = []

        for row_id, source, label, pages, summary, original_text, emb_json in rows:
            emb = np.array(json.loads(emb_json) if isinstance(emb_json, str) else emb_json)
            vscore = _cosine_similarity(query_vec, emb)
            data[row_id] = {
                "source": source, "label": label, "pages": pages,
                "summary": summary, "original_text": original_text,
            }
            vector_ranked.append((vscore, row_id))

        vector_ranked.sort(key=lambda x: x[0], reverse=True)

        # ── 키워드 검색 (조사 제거 후 substring 매칭) ─────────────
        tokens = [_strip_ko_postposition(t) for t in query.split() if len(t) >= 2]
        keyword_ranked: list[tuple[int, str]] = []
        for row_id, d in data.items():
            combined = d["summary"] + " " + d["original_text"]
            kscore = sum(1 for t in tokens if t in combined)
            keyword_ranked.append((kscore, row_id))

        keyword_ranked.sort(key=lambda x: x[0], reverse=True)

        # ── RRF (Reciprocal Rank Fusion) ──────────────────────────
        # 각 순위마다 1/(K+rank) 점수를 더함 — K=60은 표준 기본값
        K = 60
        rrf: dict[str, float] = {}
        for rank, (_, rid) in enumerate(vector_ranked):
            rrf[rid] = rrf.get(rid, 0.0) + 1.0 / (K + rank + 1)
        for rank, (kscore, rid) in enumerate(keyword_ranked):
            if kscore > 0:  # 키워드 히트가 있는 청크만 가산
                rrf[rid] = rrf.get(rid, 0.0) + 1.0 / (K + rank + 1)

        sorted_ids = sorted(rrf, key=lambda x: rrf[x], reverse=True)
        return [data[rid] for rid in sorted_ids[:n_results]]

    def list_documents(self) -> list[str]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT DISTINCT source FROM pdf_chunks ORDER BY source")
            return [row[0] for row in cur.fetchall()]

    def document_exists(self, source: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pdf_chunks WHERE source = %s LIMIT 1", (source,))
            return cur.fetchone() is not None
