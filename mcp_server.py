import os
import sys
import json
import re
import anthropic
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

API_KEY = os.getenv("ANTHROPIC_API_KEY")

_store: VectorStore | None = None

def get_store() -> VectorStore:
    global _store
    if _store is None:
        _real_stdout = sys.stdout
        sys.stdout = sys.stderr
        _store = VectorStore(pg_url=PG_URL, model_name=EMBED_MODEL)
        sys.stdout = _real_stdout
    return _store

mcp = FastMCP(
    "PDF RAG",
    host="0.0.0.0",
    port=PORT,
    instructions=(
        "이 서버는 PDF 문서 기반 RAG 검색을 제공합니다.\n\n"
        "규정·자격요건·제외기준·결격사유 관련 질문에는 반드시 아래 원칙을 따르세요:\n"
        "1. 검색 결과에서 동일하거나 가장 유사한 제목을 찾는다.\n"
        "2. 해당 제목 아래 내용만 사용한다.\n"
        "3. 다른 섹션의 내용을 반대로 해석하거나 추론하지 않는다.\n"
        "4. 원문에 없는 항목은 추가하지 않는다.\n\n"
        "근거가 없으면 '문서에서 확인되지 않음'이라고 답하세요.\n"
        "[검증] 태그가 포함된 경우, 해당 검증 결과를 반드시 참고하여 답변 범위를 제한하세요."
    ),
)


@mcp.tool()
def search_knowledge(question: str, n_results: int = 5) -> str:
    """PDF 지식베이스에서 관련 내용을 검색합니다."""
    client = anthropic.Anthropic(api_key=API_KEY)

    def decompose(q: str) -> list[str]:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": (
                f"다음 질문을 검색에 유리한 핵심 키워드 중심의 검색어 3개로 분해해줘.\n"
                f"JSON 배열로만 답해. 예: [\"검색어1\", \"검색어2\", \"검색어3\"]\n\n"
                f"질문: {q}"
            )}],
        )
        raw = resp.content[0].text.strip()
        m = re.search(r'\[.*?\]', raw, re.DOTALL)
        try:
            return json.loads(m.group()) if m else [q]
        except (json.JSONDecodeError, AttributeError):
            return [q]

    def run_search(queries: list[str], existing: set[str]) -> list[dict]:
        results: list[dict] = []
        for q in queries:
            for r in get_store().search(q, n_results=3):
                if r["label"] not in existing:
                    existing.add(r["label"])
                    results.append(r)
        return results

    # Step 1: 질문 분해 후 1차 검색
    queries = decompose(question)
    seen: set[str] = set()
    all_results = run_search(queries, seen)

    if not all_results:
        return "검색 결과가 없습니다."

    # Step 2: Self-check
    retrieved_summary = "\n".join(
        f"[{r['label']}]: {r['original_text'][:500]}"
        for r in all_results[:n_results]
    )
    check = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": (
            f"다음 검색된 원문을 보고, 질문에 대해 원문에서 직접 확인 가능한 내용과 불가능한 내용을 구분해줘.\n\n"
            f"질문: {question}\n\n"
            f"검색된 원문:\n{retrieved_summary}\n\n"
            f"형식:\n"
            f"[확인 가능] 원문에서 직접 찾을 수 있는 답변 내용 (원문 그대로 인용)\n"
            f"[확인 불가] 원문에 없거나 추론이 필요한 내용"
        )}],
    )
    verification = check.content[0].text.strip()

    # Step 3: 결과 부족하면 재검색
    retry_queries: list[str] = []
    quality = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{"role": "user", "content": (
            f"질문에 답하기에 검색 결과가 충분한가? YES 또는 NO만 답해.\n\n"
            f"질문: {question}\n검증결과:\n{verification}"
        )}],
    )
    if "NO" in quality.content[0].text.upper():
        retry_resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": (
                f"다음 질문에 대한 검색 결과가 불충분했습니다.\n"
                f"다른 관점이나 더 넓은 범위의 검색어 3개를 JSON 배열로만 제시해줘.\n\n"
                f"질문: {question}\n기존 검색어: {queries}"
            )}],
        )
        raw2 = retry_resp.content[0].text.strip()
        m2 = re.search(r'\[.*?\]', raw2, re.DOTALL)
        try:
            retry_queries = json.loads(m2.group()) if m2 else []
        except (json.JSONDecodeError, AttributeError):
            retry_queries = []

        if retry_queries:
            extra = run_search(retry_queries, seen)
            all_results.extend(extra)

    lines = [f"[검색어 분해] {queries}"]
    if retry_queries:
        lines.append(f"[재검색] {retry_queries}")
    lines.append(f"\n[검증]\n{verification}\n")
    for i, r in enumerate(all_results[:n_results], 1):
        lines.append(f"[{i}] 출처: {r['source']} — {r['label']} (p.{r['pages']})")
        lines.append(f"[요약] {r['summary']}")
        lines.append(f"[원본] {r['original_text'][:2000]}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def list_documents() -> str:
    """로드된 PDF 문서 목록을 반환합니다."""
    docs = get_store().list_documents()
    if not docs:
        return "로드된 문서가 없습니다."
    return "\n".join(f"- {d}" for d in docs)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
