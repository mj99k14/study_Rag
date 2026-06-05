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
            max_tokens=500,
            messages=[
                {
                     "role": "user",
                    "content": f"다음은 문서의 [{label}] 섹션입니다.\n"
                               f"핵심 내용을 3~5문장으로 요약하고 주요 키워드를 추출해주세요.\n\n{text}",
                }
            ]
        )
        return message.content[0].text
