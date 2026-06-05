# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 목표

PDF 문서를 지식베이스로 사용하는 RAG MCP 서버.  
Claude Desktop에서 MCP 도구를 통해 PDF 내용에 대한 Q&A가 가능하다.  
로컬은 stdio, 서버(Docker)는 SSE 모드로 동작한다.

## 기술 스택

| 역할 | 라이브러리 |
|------|-----------|
| PDF 파싱 | `PyMuPDF (fitz)` |
| 청킹 | **사람이 직접** (`chunks.json`으로 페이지 범위 지정) |
| LLM 요약 | `anthropic` — `claude-haiku-4-5-20251001` |
| 임베딩 | `sentence-transformers` — `paraphrase-multilingual-mpnet-base-v2` (한/영 지원) |
| 벡터 DB | `ChromaDB` (로컬 persistent) |
| MCP 서버 | `mcp[cli]` — `FastMCP` |
| 서버 배포 | Docker + docker-compose |

## 파일 구조

```
PDFRAG/
├── mcp_server.py          # FastMCP 서버 진입점
├── pdf_extractor.py       # PDF 페이지별 텍스트 추출
├── chunk_processor.py     # chunks.json + LLM 요약 생성
├── vector_store.py        # ChromaDB 저장/검색
├── ingest.py              # 파이프라인 실행 스크립트
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env                   # 환경변수 (gitignore)
├── .env.example
├── pdfs/                  # PDF 파일 보관 (gitignore)
├── chunks/                # 사람이 작성하는 chunks.json 파일들
└── chroma_db/             # ChromaDB 자동 생성 (gitignore)
```

## 실행 명령어

```bash
# 가상환경 생성 및 의존성 설치
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# DB 채우기 (MCP 서버 실행 전에 먼저 실행)
python ingest.py              # chunks/ 전체 처리
python ingest.py lecture01    # 특정 파일만

# 로컬 stdio 모드 (Claude Desktop 직접 연결)
python mcp_server.py

# SSE 서버 모드 (Docker 또는 원격)
python mcp_server.py sse

# Docker 빌드 및 실행
docker-compose up --build
```

## MCP 도구 (2개)

| 도구 | 설명 |
|------|------|
| `search_knowledge(query, n_results=5)` | 벡터 검색으로 관련 청크 반환 (원본 + 요약 포함) |
| `list_documents()` | 로드된 PDF 목록 반환 |

## chunks.json 형식

`chunks/` 폴더 아래 PDF마다 하나씩 작성:
```json
{
  "source": "lecture01.pdf",
  "chunks": [
    { "id": "ch01", "label": "1장 서론",     "pages": [1, 5]  },
    { "id": "ch02", "label": "2장 방법론",   "pages": [6, 14] },
    { "id": "ch03", "label": "3장 결론",     "pages": [15, 20] }
  ]
}
```

## 환경변수 (.env)

```
ANTHROPIC_API_KEY=sk-ant-...
PDF_DIR=./pdfs
CHUNK_DIR=./chunks
DB_DIR=./chroma_db
EMBED_MODEL=paraphrase-multilingual-mpnet-base-v2
MCP_PORT=8000
```

## Claude Desktop 설정

**로컬 stdio** — `%APPDATA%\Claude\claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "pdfrag": {
      "command": "python",
      "args": ["C:/Users/YJU/Desktop/PDFRAG/mcp_server.py"]
    }
  }
}
```

**원격 SSE (Docker 배포 후)**:
```json
{
  "mcpServers": {
    "pdfrag": {
      "url": "http://<서버-IP>:8000/sse"
    }
  }
}
```

## 아키텍처 흐름

```
PDF 파일
  └─ [사람] chunks.json 으로 페이지 범위 직접 지정
       └─ pdf_extractor.py  →  페이지 범위별 텍스트 추출 (PyMuPDF)
            └─ chunk_processor.py  →  Claude API로 각 청크 요약 생성
                 └─ vector_store.py  →  요약문 임베딩 + 원본/요약 ChromaDB 저장
                      └─ mcp_server.py  →  FastMCP 도구로 검색 노출
                           └─ Claude Desktop  →  MCP 프로토콜로 질의/응답
```

## 청킹 전략

- **사람이 직접** 장/절 단위로 페이지 범위를 `chunks.json`에 지정
- LLM 요약을 임베딩 대상으로 사용 (원본 텍스트보다 검색 품질 향상)
- 검색 결과에는 원본 텍스트 + 요약 + 출처(파일명, 레이블, 페이지) 포함

## Docker 포트

| 서비스 | 포트 |
|--------|------|
| MCP SSE 서버 | `8000` |

교수님 서버에 올릴 때 포트 충돌 시 `.env`의 `MCP_PORT` 값과 `docker-compose.yml`의 포트 매핑만 변경한다.
