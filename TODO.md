# PDF RAG MCP 서버 — 구현 계획

## 전체 파이프라인

```
PDF 파일
  └─ [사람] chunks.json 으로 페이지 범위 직접 지정
       └─ pdf_extractor.py  →  페이지 범위별 텍스트 추출
            └─ chunk_processor.py  →  각 청크를 Claude API로 요약
                 └─ vector_store.py  →  원본 + 요약 임베딩해서 ChromaDB 저장
                      └─ mcp_server.py  →  FastMCP 도구로 검색 노출
                           └─ Claude Desktop  →  Q&A
```

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
├── .env
├── .env.example
├── pdfs/                  # PDF 파일 보관
├── chunks/                # 사람이 작성하는 chunks.json 파일들
└── chroma_db/             # ChromaDB 자동 생성 (gitignore)
```

---

## 단계별 TODO

---

### Phase 1: 환경 세팅

- [ ] `requirements.txt` 작성
  ```
  mcp[cli]>=1.0.0
  anthropic>=0.40.0
  pymupdf>=1.24.0
  chromadb>=0.5.0
  sentence-transformers>=3.0.0
  python-dotenv>=1.0.0
  uvicorn>=0.30.0
  ```
- [ ] 가상환경 생성 및 패키지 설치
  ```bash
  python -m venv .venv
  .venv\Scripts\activate
  pip install -r requirements.txt
  ```
- [ ] `.env.example` 작성
  ```
  ANTHROPIC_API_KEY=sk-ant-...
  PDF_DIR=./pdfs
  CHUNK_DIR=./chunks
  DB_DIR=./chroma_db
  EMBED_MODEL=paraphrase-multilingual-mpnet-base-v2
  MCP_PORT=8000
  ```
- [ ] `.gitignore` 작성 (`chroma_db/`, `pdfs/`, `.env`, `.venv/`)
- [ ] `pdfs/`, `chunks/` 폴더 생성

---

### Phase 2: PDF 텍스트 추출기 (`pdf_extractor.py`)

**목표**: PDF의 특정 페이지 범위에서 텍스트만 뽑아내는 도구

- [ ] `PDFExtractor` 클래스 작성
  - `extract_pages(filepath, start_page, end_page) -> str`
    - 지정한 페이지 범위의 텍스트를 하나의 문자열로 반환
    - 페이지 번호는 1부터 시작
  - 내부 `_clean(text)` : 불필요한 공백/줄바꿈 정리
- [ ] 단독 실행 테스트
  ```bash
  python pdf_extractor.py  # 테스트용 main 블록
  ```

---

### Phase 3: chunks.json 형식 설계 + 직접 작성

**목표**: 사람이 PDF를 읽고 의미 단위로 청크 경계를 직접 지정

- [ ] `chunks/` 폴더 아래 PDF마다 json 파일 하나씩 작성
  ```
  chunks/
  ├── lecture01.json
  ├── paper_abc.json
  └── ...
  ```
- [ ] `chunks.json` 형식 정의
  ```json
  {
    "source": "lecture01.pdf",
    "chunks": [
      { "id": "ch01", "label": "1장 서론",      "pages": [1, 5]  },
      { "id": "ch02", "label": "2장 방법론",     "pages": [6, 14] },
      { "id": "ch03", "label": "3장 실험 결과",  "pages": [15, 22] },
      { "id": "ch04", "label": "4장 결론",       "pages": [23, 27] }
    ]
  }
  ```
  - `pages`: `[시작페이지, 끝페이지]` (양 끝 포함)
  - `label`: 청크 설명 (검색 결과에 출처로 표시됨)
- [ ] 테스트용 PDF 하나로 실제 chunks.json 직접 작성해보기

---

### Phase 4: LLM 처리기 (`chunk_processor.py`)

**목표**: 각 청크 텍스트를 Claude API로 요약 생성

- [ ] `ChunkProcessor` 클래스 작성
  - `__init__(api_key)` : Anthropic 클라이언트 초기화
  - `process(chunk_id, label, text) -> Dict`
    - Claude에 요약 요청
    - 반환: `{"id", "label", "original_text", "summary", "source", "pages"}`
  - 내부 `_build_prompt(label, text) -> str`
    - 프롬프트 예시:
      ```
      아래는 문서의 [{label}] 섹션입니다.
      핵심 내용을 3~5문장으로 요약하고, 주요 개념/키워드를 추출해주세요.

      [텍스트]
      {text}
      ```
- [ ] 사용할 모델: `claude-haiku-4-5-20251001` (빠름, 저렴)
- [ ] 단독 실행 테스트 (청크 하나 넣어서 요약 확인)

---

### Phase 5: 벡터 스토어 구현 (`vector_store.py`)

**목표**: 원본 텍스트 + LLM 요약을 임베딩해서 ChromaDB에 저장

- [ ] `VectorStore` 클래스 작성
  - `__init__(db_path, model_name)` : ChromaDB + SentenceTransformer 초기화
  - `add_processed_chunks(chunks, source)` : 가공된 청크 저장
    - **임베딩 대상**: `요약문` (검색 품질이 원본보다 좋음)
    - **저장 내용**: 원본 텍스트 + 요약 + 레이블 + 페이지 정보 (메타데이터)
  - `search(query, n_results) -> List[Dict]` : 코사인 유사도 검색
    - 반환: 원본 텍스트 + 요약 + 출처 정보
  - `list_documents() -> List[str]` : 저장된 소스 목록
  - `document_exists(source) -> bool` : 중복 로드 방지
- [ ] 임베딩 함수: SentenceTransformer 직접 구현 (chromadb 버전 의존성 회피)
  ```python
  class EmbeddingFn:
      def __init__(self, model_name): self.model = SentenceTransformer(model_name)
      def __call__(self, input: list[str]) -> list[list[float]]:
          return self.model.encode(input).tolist()
  ```
- [ ] 단독 실행으로 저장/검색 테스트

---

### Phase 6: 파이프라인 실행 스크립트 (`ingest.py`)

**목표**: chunks/ 폴더를 읽어서 전체 파이프라인 한 번에 실행

- [ ] `ingest.py` 작성
  ```
  실행 흐름:
  1. chunks/ 폴더의 모든 .json 파일 읽기
  2. 각 json에서 source PDF와 청크 목록 로드
  3. 이미 DB에 있는 source면 건너뜀
  4. PDFExtractor로 페이지별 텍스트 추출
  5. ChunkProcessor로 LLM 요약 생성
  6. VectorStore에 저장
  ```
- [ ] 실행 방법
  ```bash
  python ingest.py              # 전체 chunks/ 처리
  python ingest.py lecture01    # 특정 파일만 처리
  ```
- [ ] 처리 결과 출력 예시
  ```
  [lecture01.pdf] ch01 서론 (p.1-5) → 요약 생성 완료
  [lecture01.pdf] ch02 방법론 (p.6-14) → 요약 생성 완료
  ...
  총 4개 청크 저장 완료
  ```

---

### Phase 7: MCP 서버 구현 (`mcp_server.py`)

**목표**: FastMCP로 도구 노출

- [ ] 환경변수 로드 (`python-dotenv`)
- [ ] `VectorStore` 인스턴스 생성
- [ ] 도구 구현
  - `search_knowledge(query, n_results=5)` : 검색 결과 반환
    ```
    반환 형식:
    [1] 출처: lecture01.pdf — 2장 방법론 (p.6-14)
    [요약] ...
    [원본] ...
    ```
  - `list_documents()` : 로드된 문서 목록
- [ ] 실행 모드 분기
  ```bash
  python mcp_server.py        # stdio (로컬 Claude Desktop)
  python mcp_server.py sse    # SSE (Docker/서버)
  ```
- [ ] FastMCP 설정
  ```python
  mcp = FastMCP("PDF RAG", host="0.0.0.0", port=PORT)
  ```

---

### Phase 8: 로컬 Claude Desktop 연결 테스트

- [ ] `%APPDATA%\Claude\claude_desktop_config.json` 수정
  ```json
  {
    "mcpServers": {
      "pdfrag": {
        "command": "C:/Users/YJU/Desktop/PDFRAG/.venv/Scripts/python.exe",
        "args": ["C:/Users/YJU/Desktop/PDFRAG/mcp_server.py"]
      }
    }
  }
  ```
- [ ] `ingest.py` 실행해서 DB 채우기
- [ ] Claude Desktop 재시작 후 `search_knowledge` 도구 확인
- [ ] 질문 테스트: PDF 내용 기반 Q&A 확인

---

### Phase 9: Docker 설정

- [ ] `Dockerfile` 작성
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  RUN python -c "from sentence_transformers import SentenceTransformer; \
      SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"
  COPY . .
  RUN mkdir -p pdfs chunks chroma_db
  EXPOSE 8000
  CMD ["python", "mcp_server.py", "sse"]
  ```
- [ ] `docker-compose.yml` 작성
  ```yaml
  services:
    pdfrag:
      build: .
      ports:
        - "8000:8000"
      volumes:
        - ./pdfs:/app/pdfs
        - ./chunks:/app/chunks
        - ./chroma_db:/app/chroma_db
      env_file: .env
      restart: unless-stopped
  ```
- [ ] 로컬 Docker 빌드/실행 테스트
  ```bash
  docker-compose up --build
  ```

---

### Phase 10: 서버 배포 및 원격 연결

- [ ] 교수님 서버에 프로젝트 복사
- [ ] `docker-compose up -d` 실행
- [ ] Claude Desktop SSE URL로 변경
  ```json
  {
    "mcpServers": {
      "pdfrag": {
        "url": "http://<서버-IP>:8000/sse"
      }
    }
  }
  ```
- [ ] 원격 Q&A 테스트

---

## 구현 순서 요약

```
Phase 1 (환경)
  → Phase 2 (PDF 추출기)
    → Phase 3 (chunks.json 직접 작성)
      → Phase 4 (LLM 요약기)
        → Phase 5 (벡터 스토어)
          → Phase 6 (ingest 파이프라인)
            → Phase 7 (MCP 서버)
              → Phase 8 (로컬 테스트)
                → Phase 9 (Docker)
                  → Phase 10 (서버 배포)
```

## 주의사항

- Anthropic API 키 필요 — `.env`에 `ANTHROPIC_API_KEY` 설정
- `sentence-transformers` 첫 실행 시 모델 다운로드 (~1GB)
- `ingest.py`는 mcp_server 실행 전에 먼저 돌려야 DB가 채워짐
- Docker에서 `pdfs/`, `chunks/`, `chroma_db/` 반드시 볼륨 마운트
- 청크 경계를 잘 나눌수록 검색 품질이 올라감 — 장/절 단위 권장
