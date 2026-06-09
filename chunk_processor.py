#사람이 청킹한걸 받아서 llm한태 작업하는 작업

import anthropic

class ChunkProcessor:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
    
    # 청크 정보를 받아서 -> summarize을 호출하고 딕셔너리로 묶음
    def process(self, chunk_id: str, label: str, text: str, source: str, pages: list) ->dict:
        summary = self._summarize(label, text)
        return{
            "id": chunk_id,
            "label": label,
            "original_text": text,
            "summary": summary,
            "source": source,
            "pages": pages,
        }
    
    # llm 호출하는 함수
    def _summarize(self, label: str, text: str) -> str:
        message = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"다음은 '해외취업연수사업 운영기관 모집공고' 문서의 [{label}] 섹션입니다.\n"
                        f"이 요약은 RAG 검색 인덱스로 사용됩니다. 담당자나 지원자가 아래와 같은 질문을 할 때 이 요약이 검색되어야 합니다:\n"
                        f"- 지원 자격 및 요건이 무엇인가?\n"
                        f"- 인원수 제한(최소/최대)은 얼마인가?\n"
                        f"- 정부지원금 규모와 지급 조건은?\n"
                        f"- 신청·선정 일정은 언제인가?\n"
                        f"- 운영기관이 갖춰야 할 조건은?\n\n"
                        f"다음 형식으로 작성하세요:\n\n"
                        f"## 요약\n"
                        f"이 섹션의 핵심 내용을 3~5문장으로 서술\n\n"
                        f"## 주요 수치 및 조건\n"
                        f"(해당 항목만 작성, 없으면 생략)\n"
                        f"- 인원: (최소/최대 인원수)\n"
                        f"- 금액: (지원금, 한도 등)\n"
                        f"- 기간: (연수 기간, 신청 기간 등)\n"
                        f"- 자격: (지원 자격, 제한 조건)\n"
                        f"- 비율: (퍼센트 조건 등)\n\n"
                        f"## 검색 키워드\n"
                        f"사용자가 검색할 만한 핵심 단어 5~10개\n\n"
                        f"---\n{text}"
                    ),
                }
            ]
        )
        return message.content[0].text
