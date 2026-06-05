import re
import fitz

# pdf 파일열고, 지정한 페이지 텍스트 꺼내기 배열에 담아서 문자열 합치기
# -> 사람이 페이지범위를 정하면 텍스트 pdf꺼내야함 -> 이 class가 해줌
class PDFExtractor:
    # 사람기준으로 페이지를 가져오기위해서
    def extract_pages(self, filepath: str, start_page: int, end_page: int) -> str:
        # fitz.open() 으로 pdf 열고
        doc = fitz.open(filepath)
        texts = []

        for page_num in range(start_page - 1, end_page):
            if page_num >= len(doc):
                break
            texts.append(doc[page_num].get_text())

        doc.close()
        return self._clean("\n".join(texts))

    def _clean(self, text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()