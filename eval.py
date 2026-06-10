"""
RAG 검색 정확도 평가 스크립트 (Retrieval Evaluation)
- 각 질문에 '정답 청크 레이블'을 지정
- 검색 결과 top-5 안에 정답 청크가 있으면 Hit
- 최종 Hit Rate 리포트
"""
from dotenv import load_dotenv
load_dotenv()

from vector_store import VectorStore

store = VectorStore(
    pg_url="postgresql://postgres:pdfrag1234@localhost:5432/pdfrag",
    model_name="paraphrase-multilingual-mpnet-base-v2",
)

# (질문, 정답청크레이블, 정답내용)
TEST_CASES = [
    (
        "2026년 해외취업연수사업 총 모집 인원은 몇 명이야?",
        "Ⅰ. 사업 개요 및 2026년 운영 방향",
        "총 2,700명 (트랙Ⅰ 2,000명, 트랙Ⅱ 500명, 新청해진대학 200명)",
    ),
    (
        "1차 지원금과 2차 지원금 비율은?",
        "Ⅶ. 약정체결 및 지원금 지급·정산",
        "1차 70%, 2차 30%",
    ),
    (
        "트랙Ⅱ 연수과정 최소 시수 조건은?",
        "Ⅲ. 공모 유형 (트랙Ⅰ·Ⅱ·패스트트랙·청해진대학)",
        "800시수 이상",
    ),
    (
        "제안서 접수 마감일은 언제야?",
        "Ⅳ. 접수 및 선정 일정",
        "2026년 1월 16일 18:00까지",
    ),
    (
        "운영기관이 참여 제외되는 사유는?",
        "Ⅴ. 운영기관 구성 및 자격 요건",
        "사업 정지 이상 행정처분 후 1년 미경과, 2년 연속 최하등급 등",
    ),
    (
        "트랙Ⅰ 1인당 최대 정부지원금은?",
        "Ⅵ. 연수 요건 및 정부지원금 규모",
        "최대 800만원",
    ),
    (
        "취업 인정 일반국가 연봉 기준은?",
        "Ⅷ-1. 취업 인정 기준 (비자·연봉·증빙)",
        "2,600만원 이상",
    ),
    (
        "해외취업연수 대상자 선발 제외 기준을 알려줘",
        "Ⅷ-2. 연수생 선발 자격·제외 기준 및 절차",
        "최근 1년 이내 공단 해외취업연수 참여자, 2회 이상 참여자 등",
    ),
    (
        "연수생 나이 지원 자격은?",
        "Ⅷ-2. 연수생 선발 자격·제외 기준 및 절차",
        "만 15~34세 (군복무 기간 최대 3세 연장)",
    ),
    (
        "숙박비 지원 금액은 얼마야?",
        "Ⅸ. 연수 운영·결과 보고 및 숙박비 지원",
        "월 최대 20만원 (취약계층 청년 30만원)",
    ),
    (
        "운영기관 심사 배점 구성은?",
        "붙임1. 운영기관 심사기준",
        "과정개설 20점, 과정운영 50점, 취업지원 30점 (총 100점)",
    ),
    (
        "취업비자 인정 국가는 몇 개국이야?",
        "붙임2~4. 취업비자 인정기준 및 지원 확대 국가·직종",
        "18개국",
    ),
]

N = 5  # top-N 안에 정답 청크 있으면 Hit

hits = 0
misses = []

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

print(f"{'='*60}")
print(f"RAG 검색 정확도 평가 (top-{N} Hit Rate)")
print(f"{'='*60}\n")

for i, (question, expected_label, correct_answer) in enumerate(TEST_CASES, 1):
    results = store.search(question, n_results=N)
    retrieved_labels = [r["label"] for r in results]
    hit = expected_label in retrieved_labels
    rank = retrieved_labels.index(expected_label) + 1 if hit else None

    if hit:
        hits += 1
        status = f"[HIT] rank {rank}"
    else:
        status = "[MISS]"
        misses.append((i, question, expected_label, retrieved_labels))

    print(f"[Q{i:02d}] {status}")
    print(f"      질문: {question}")
    print(f"      정답 청크: {expected_label}")
    if hit:
        print(f"      정답 내용: {correct_answer}")
    else:
        print(f"      검색된 청크: {retrieved_labels}")
    print()

print(f"{'='*60}")
print(f"Hit Rate: {hits}/{len(TEST_CASES)} ({hits/len(TEST_CASES)*100:.1f}%)")
if misses:
    print(f"\n미스 목록:")
    for idx, q, expected, got in misses:
        print(f"  Q{idx:02d}: '{q[:30]}...' → 기대={expected}")
print(f"{'='*60}")
