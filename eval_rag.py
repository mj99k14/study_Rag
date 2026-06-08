import os
from dotenv import load_dotenv
from vector_store import VectorStore
import anthropic

load_dotenv()

store = VectorStore(
    os.getenv("DB_DIR", "./chroma_db"),
    os.getenv("EMBED_MODEL", "paraphrase-multilingual-mpnet-base-v2"),
)
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# 질문 + 정답 쌍
test_cases = [
    {
        "question": "운영기관 자격 요건이 뭐야?",
        "ground_truth": "국외 직업소개사업자 자격을 갖춰야 하며 교육훈련기관, 직업소개기관, 국내대학 등 유형별로 자격요건이 다르다.",
    },
    {
        "question": "연수생 나이 제한이 어떻게 돼?",
        "ground_truth": "만 15세 이상 34세 이하 대한민국 국민이어야 한다.",
    },
    {
        "question": "정부지원금은 몇 번에 나눠서 지급해?",
        "ground_truth": "1차 70%, 2차 30%로 나눠서 지급한다.",
    },
    {
        "question": "취업 인정을 받으려면 연봉이 얼마 이상이어야 해?",
        "ground_truth": "공통 기준으로 연봉 2600만원 이상이어야 한다.",
    },
    {
        "question": "숙박비 지원은 얼마야?",
        "ground_truth": "월 최대 20만원, 취약계층은 30만원이다.",
    },
]


def generate_answer(question: str, contexts: list[dict]) -> str:
    context_text = "\n\n".join(
        f"[{r['label']}]\n{r['summary']}" for r in contexts
    )
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"아래 문서를 참고해서 질문에 한 문장으로 간결하게 답해줘.\n\n{context_text}\n\n질문: {question}",
        }],
    )
    return message.content[0].text


def score_answer(answer: str, ground_truth: str) -> float:
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": (
                f"정답: {ground_truth}\n"
                f"생성된 답변: {answer}\n\n"
                f"생성된 답변이 정답의 핵심 내용을 포함하고 있으면 1, 아니면 0을 숫자만 출력해."
            ),
        }],
    )
    try:
        return float(message.content[0].text.strip())
    except ValueError:
        return 0.0


print("=== RAG 평가 시작 ===\n")
scores = []

for tc in test_cases:
    results = store.search(tc["question"], n_results=3)
    answer = generate_answer(tc["question"], results)
    score = score_answer(answer, tc["ground_truth"])
    scores.append(score)

    print(f"Q: {tc['question']}")
    print(f"A: {answer}")
    print(f"정답: {tc['ground_truth']}")
    print(f"점수: {score}")
    print()

print(f"=== 최종 점수: {sum(scores)}/{len(scores)} ({sum(scores)/len(scores)*100:.0f}%) ===")
