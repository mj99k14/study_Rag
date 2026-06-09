import os
import sys
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from vector_store import VectorStore

load_dotenv()

EMBED_MODEL = os.getenv("EMBED_MODEL", "paraphrase-multilingual-mpnet-base-v2")
PORT = int(os.getenv("MCP_PORT", "8000"))
PG_URL = "postgresql://{user}:{pw}@{host}:{port}/{db}".format(
    user=os.getenv("PG_USER", "postgres"),
    pw=os.getenv("PG_PASSWORD", ""),
    host=os.getenv("PG_HOST", "localhost"),
    port=os.getenv("PG_PORT", "5432"),
    db=os.getenv("PG_DB", "pdfrag"),
)

_real_stdout = sys.stdout
sys.stdout = sys.stderr

store = VectorStore(pg_url=PG_URL, model_name=EMBED_MODEL)

sys.stdout = _real_stdout

mcp = FastMCP("PDF RAG", host="0.0.0.0", port=PORT)


@mcp.tool()
def search_knowledge(query: str, n_results: int = 5) -> str:
    """PDF 지식베이스에서 관련 내용을 검색합니다."""
    results = store.search(query, n_results)
    if not results:
        return "검색 결과가 없습니다. ingest.py를 먼저 실행해주세요."

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] 출처: {r['source']} — {r['label']} (p.{r['pages']})")
        lines.append(f"[요약] {r['summary']}")
        lines.append(f"[원본] {r['original_text'][:500]}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def list_documents() -> str:
    """로드된 PDF 문서 목록을 반환합니다."""
    docs = store.list_documents()
    if not docs:
        return "로드된 문서가 없습니다."
    return "\n".join(f"- {d}" for d in docs)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
