# PDF RAG MCP 서버 — 구현 기록

## 프로젝트 목표

PDF 문서를 지식베이스로 사용해서 Claude Desktop에서 Q&A가 가능한 MCP 서버 구축.  
"2026년 해외취업연수사업 운영기관 모집공고" PDF를 대상으로 개발 및 검증.

---

## RAG 타입 선택 이유

| 타입 | 설명 | 선택 여부 |
|------|------|-----------|
| Naive RAG | 원본 텍스트를 그대로 임베딩 | ❌ 검색 품질 낮음 |
| **Advanced RAG** | **LLM 요약문을 임베딩 대상으로 사용** | ✅ **채택** |
| GraphRAG | 지식 그래프 구축 후 탐색 | ❌ 구축 비용 큼 |
| Agentic RAG | LLM이 반복 검색·추론 | ✅ search_knowledge 내부에 통합 구현 |

**Advanced RAG를 선택한 이유**:  
원본 텍스트보다 LLM이 생성한 요약이 사용자 질문과 의미적으로 더 가깝게 매칭된다.  
예: "최소 인원이 몇 명이야?" → 요약에 "최소 연수인원 10명" 명시 → 벡터 유사도 향상

---

## 전체 아키텍처 흐름

```
[인제스트 파이프라인] — 사전 처리 (1회 실행)

PDF 파일
  └─ 사람이 chunks.json에 페이지 범위 직접 지정
       └─ pdf_extractor.py
            ├─ PyMuPDF(fitz): 일반 텍스트 추출
            └─ pdfplumber: 표(table) 구조 추가 추출 → [표] 마커로 병합
                 └─ chunk_processor.py
                      └─ Claude Haiku API: 도메인 특화 프롬프트로 섹션 요약 생성
                           └─ vector_store.py
                                ├─ sentence-transformers: 요약문 임베딩
                                └─ PostgreSQL: (id, label, pages, summary, original_text, embedding) 저장


[검색 파이프라인] — 실시간 질의

Claude Desktop
  └─ MCP 도구 호출 (search_knowledge)
       └─ vector_store.search()
            ├─ 벡터 검색: 코사인 유사도로 청크 랭킹
            ├─ 키워드 검색: 한국어 조사 제거 후 substring 매칭
            └─ RRF(Reciprocal Rank Fusion): 두 랭킹 합산
                 └─ 검색 결과 (요약 + 원본 텍스트 2000자) 반환
                      └─ Claude Desktop이 결과 읽고 최종 답변 생성
```

---

## 파일별 역할 설명

### `pdf_extractor.py`
PDF에서 텍스트를 추출하는 도구.

- **PyMuPDF(fitz)**: 일반 텍스트 추출. 속도 빠르고 한국어 잘 처리
- **pdfplumber**: 표(table) 구조 추가 추출. fitz는 표 셀을 일렬로 나열하는데, pdfplumber는 `구분 | 오리엔테이션 | 필수 연수과목` 형태로 구조 보존
- 두 결과를 합쳐서 반환 (중복 있어도 LLM 요약 품질이 더 중요)

### `chunk_processor.py`
추출된 텍스트를 Claude Haiku로 요약하는 도구.

**왜 요약을 임베딩하나?**  
원본 텍스트 "○(최소 연수인원) 10명(과정별 10명 이상 구성 시 개설 가능)"은  
사용자 질문 "최소 인원이 몇 명이야?"와 벡터 유사도가 낮다.  
요약에 "최소 연수인원 10명"이 명시되면 벡터 검색이 더 잘 된다.

**프롬프트 구조** (도메인 특화):
```
- 문서 맥락: '해외취업연수사업 운영기관 모집공고'
- 예상 질문 유형 명시 (인원수, 지원금, 자격요건 등)
- 출력 형식: ## 요약 / ## 주요 수치 및 조건 / ## 검색 키워드
- max_tokens: 800
```

### `vector_store.py`
임베딩 저장 및 **하이브리드 검색** 담당.

**왜 하이브리드 검색인가?**  
벡터 검색은 의미 유사도 기반이라 숫자("10명"), 고유명사("트랙Ⅱ") 같은 정확한 키워드 검색에 약하다.  
키워드 검색을 병행하면 이를 보완할 수 있다.

**RRF(Reciprocal Rank Fusion) 방식**:
```
벡터 랭킹:    ch05(1위) ch07(2위) ch09(3위) ...
키워드 랭킹:  ch07(1위) ch05(2위) ch08(3위) ...

RRF 점수 = Σ 1/(K + rank)  (K=60 표준값)
→ 두 랭킹에서 모두 상위권인 청크가 최종 상위로 올라옴
```

**한국어 조사 제거**: "연수인원은" → "연수인원"으로 변환 후 매칭

### `ingest.py`
전체 파이프라인을 한 번에 실행하는 스크립트.

```bash
python ingest.py          # chunks/ 전체 처리
python ingest.py 2026     # 2026.json만 처리
```

`document_exists()` 체크로 이미 처리된 문서는 건너뜀.  
재처리 필요 시: `python delete_chunks.py 2026` 먼저 실행.

### `mcp_server.py`
Claude Desktop과 연결되는 MCP 서버. 2개 도구 제공.

**`search_knowledge(question, n_results=5)`** ← Agentic RAG 통합  
Claude Desktop에 노출되는 유일한 검색 도구. 내부에서 3단계 처리:
```
Step 1: Claude Haiku가 질문을 검색어 3개로 분해
         "최소 연수인원은?" → ["최소 연수인원", "과정별 인원 제한", "연수생 모집 조건"]
Step 2: 각 검색어로 hybrid 검색, 중복 제거 후 합산
Step 3: Claude Haiku가 self-check 수행
         → [확인 가능] 원문에서 직접 찾을 수 있는 내용
         → [확인 불가] 원문에 없거나 추론 필요한 내용
Step 4: 검증 결과 + 청크 내용을 Claude Desktop에 전달
```
도구를 하나로 통합한 이유: Claude Desktop이 두 도구 중 하나를 선택할 때 잘못 고를 수 있어서,  
선택 자체를 없애고 항상 full pipeline을 실행하도록 변경.

**`list_documents()`**  
로드된 PDF 목록 반환.

**`instructions` (Generation Grounding)**  
규정 문서 특성상 Claude Desktop이 원문을 벗어나 추론하는 "Generation Grounding Failure"를 방지하기 위한 서버 수준 지침:
```
1. 검색 결과에서 동일하거나 가장 유사한 제목을 찾는다
2. 해당 제목 아래 내용만 사용한다
3. 다른 섹션 내용을 반대로 해석하거나 추론하지 않는다
4. 원문에 없는 항목은 추가하지 않는다
```

### `delete_chunks.py`
DB 청크 삭제 유틸리티.

```bash
python delete_chunks.py 2026   # 특정 문서만 삭제
python delete_chunks.py        # 전체 삭제
```

### `chunks/2026.json`
사람이 직접 작성하는 청킹 설정. 페이지 범위를 직접 지정하는 이유:  
LLM 자동 청킹보다 장/절 단위 수동 청킹이 의미 경계를 더 정확히 잡음.

**청킹 전략 교훈**: ch08이 "취업 인정 기준 + 선발 제외 기준" 두 주제를 포함했을 때,  
모델이 "선발 기준"을 뒤집어 "선발 제외 기준"으로 답변하는 오류 발생.  
→ ch08a(취업인정기준) / ch08b(선발·제외기준)으로 분리해서 해결.

---

## 발생했던 문제와 해결

| 문제 | 원인 | 해결 |
|------|------|------|
| ChromaDB `os error 5` | Claude Desktop 샌드박스에서 Rust 바인딩 접근 거부 | PostgreSQL로 교체 |
| "10명" 검색 실패 | 벡터 유사도가 숫자 키워드에 약함 | RRF 하이브리드 검색 도입 |
| OT 표 내용 잘림 | `original_text[:500]` 제한 | 2000자로 확대 |
| 선발 제외 기준 오답 | ch08이 두 주제 혼합 (Generation Grounding Failure) | 청크 분리 + instructions 추가 |
| pdfplumber 표 셀 비어있음 | 병합 셀(rowspan/colspan) 구조 한계 | fitz 텍스트로 내용 보완됨 |

---

## 실행 명령어 요약

```bash
# 의존성 설치
pip install -r requirements.txt

# DB 초기화 (처음 한 번)
python ingest.py 2026

# 재인제스트 (코드·청크 변경 시)
python delete_chunks.py 2026
python ingest.py 2026

# 로컬 MCP 서버 실행 (Claude Desktop이 자동 실행)
python mcp_server.py

# SSE 서버 모드 (Docker/원격)
python mcp_server.py sse
```

---

## 남은 작업

- [ ] Phase 9: Docker 설정 (`Dockerfile`, `docker-compose.yml`)
- [ ] Phase 10: 교수님 서버 배포 및 원격 SSE 연결 테스트
- [ ] 개선 가능: pgvector 확장 도입으로 DB 내 벡터 인덱스 활용 (데이터 증가 시)
- [ ] 개선 가능: 다른 PDF 문서 추가 시 chunks.json 작성 후 `python ingest.py <이름>` 실행
