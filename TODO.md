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

- [x] `requirements.txt` 작성
- [x] 가상환경 생성 및 패키지 설치 (`.venv`)
- [x] `.env.example` 작성
- [x] `.gitignore` 작성
- [x] `pdfs/`, `chunks/` 폴더 생성

---

### Phase 2: PDF 텍스트 추출기 (`pdf_extractor.py`)

**목표**: PDF의 특정 페이지 범위에서 텍스트만 뽑아내는 도구

- [x] `PDFExtractor` 클래스 작성
- [x] 단독 실행 테스트

---

### Phase 3: chunks.json 형식 설계 + 직접 작성

**목표**: 사람이 PDF를 읽고 의미 단위로 청크 경계를 직접 지정

- [x] `chunks/` 폴더 아래 PDF마다 json 파일 작성
- [x] `chunks.json` 형식 정의 및 테스트용 PDF 작성

---

### Phase 4: LLM 처리기 (`chunk_processor.py`)

**목표**: 각 청크 텍스트를 Claude API로 요약 생성

- [x] `ChunkProcessor` 클래스 작성 (`claude-haiku-4-5-20251001`)
- [x] 단독 실행 테스트

---

### Phase 5: 벡터 스토어 구현 (`vector_store.py`)

**목표**: 원본 텍스트 + LLM 요약을 임베딩해서 벡터 DB에 저장

- [x] ChromaDB 기반 `VectorStore` 클래스 작성 (완료)
- [x] 단독 실행 저장/검색 테스트 통과
- **[BLOCKED]** Claude Desktop 샌드박스(CodexSandboxUsers)에서 ChromaDB Rust 바인딩이 `os error 5` (Access Denied)로 실패 → **PostgreSQL로 교체 결정**

---

### Phase 6: 파이프라인 실행 스크립트 (`ingest.py`)

**목표**: chunks/ 폴더를 읽어서 전체 파이프라인 한 번에 실행

- [x] `ingest.py` 작성 (전체 처리 / 특정 파일만 처리 옵션 포함)
- [x] 실행 테스트 (ChromaDB 기준으로 동작 확인)

---

### Phase 7: MCP 서버 구현 (`mcp_server.py`)

**목표**: FastMCP로 도구 노출

- [x] 환경변수 로드, `VectorStore` 인스턴스 생성
- [x] `search_knowledge`, `list_documents` 도구 구현
- [x] stdio / SSE 실행 모드 분기
- [x] stdout 오염 방지 (`sys.stdout = sys.stderr` 처리)

---

### Phase 8: 로컬 Claude Desktop 연결 테스트

- [x] `claude_desktop_config.json` 수정 (`.venv` 경로 + `cwd` 설정 완료)
- **[BLOCKED]** ChromaDB가 Claude Desktop 샌드박스에서 동작 안 함 → Phase 8.5로 해결

---

### Phase 8.5: ChromaDB → PostgreSQL 마이그레이션 ← **지금 여기**

**이유**: Claude Desktop이 MCP 프로세스를 `CodexSandboxUsers` 샌드박스로 실행하는데,
ChromaDB 1.5.x Rust 바인딩이 파일 잠금/메모리맵에서 `os error 5 (Access Denied)` 발생.
PostgreSQL은 TCP 네트워크 접속이라 샌드박스 제한 없이 동작 가능.

#### 8.5-A: PostgreSQL 비밀번호 재설정 (관리자 작업)

- [ ] **[사용자 직접]** `pg_hba.conf` 임시 수정
  - 파일 위치: `C:\Program Files\PostgreSQL\18\data\pg_hba.conf`
  - `scram-sha-256` → `trust` 로 아래 두 줄 변경
    ```
    # IPv4 local connections:
    host    all             all             127.0.0.1/32            trust
    # IPv6 local connections:
    host    all             all             ::1/128                 trust
    ```
- [ ] **[사용자 직접]** PostgreSQL 서비스 재시작
  ```powershell
  Restart-Service postgresql-x64-18
  ```
- [ ] **[사용자 직접]** 비밀번호 설정 (새 비밀번호로 변경)
  ```powershell
  & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "ALTER USER postgres WITH PASSWORD 'newpassword';"
  ```
- [ ] **[사용자 직접]** `pg_hba.conf` 원복 (`trust` → `scram-sha-256`)
- [ ] **[사용자 직접]** PostgreSQL 서비스 재시작
- [ ] **[사용자 직접]** 새 비밀번호로 접속 확인
  ```powershell
  & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "\l"
  ```

#### 8.5-B: pdfrag 데이터베이스 생성

- [ ] DB 및 pgvector 확장 생성
  ```sql
  CREATE DATABASE pdfrag;
  \c pdfrag
  CREATE EXTENSION IF NOT EXISTS vector;
  ```
  > ※ pgvector 없으면 float[] + numpy 코사인 유사도로 대체 가능

#### 8.5-C: `vector_store.py` PostgreSQL로 재작성 (Claude가 할 작업)

- [ ] `psycopg2-binary` 설치
  ```bash
  .venv\Scripts\pip install psycopg2-binary numpy
  ```
- [ ] `vector_store.py` 전면 재작성
  - `chromadb` 제거
  - `psycopg2` + `numpy` 코사인 유사도 사용
  - 테이블 자동 생성 (`pdf_chunks`)
  - 동일한 public 인터페이스 유지 (`add_processed_chunks`, `search`, `list_documents`, `document_exists`)
- [ ] `.env` 에 PostgreSQL 접속 정보 추가
  ```
  PG_HOST=localhost
  PG_PORT=5432
  PG_DB=pdfrag
  PG_USER=postgres
  PG_PASSWORD=<설정한 비밀번호>
  ```
- [ ] `requirements.txt` 업데이트 (`psycopg2-binary` 추가, `chromadb` 제거)

#### 8.5-D: 재테스트

- [ ] `ingest.py` 재실행 (PostgreSQL에 데이터 채우기)
- [ ] Claude Desktop 재시작
- [ ] `search_knowledge` 도구 정상 동작 확인
- [ ] PDF 내용 기반 Q&A 테스트

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
