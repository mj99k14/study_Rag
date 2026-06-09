import re
import fitz
import pdfplumber

# pdf 파일열고, 지정한 페이지 텍스트 꺼내기 배열에 담아서 문자열 합치기
# pdfplumber로 표(table)도 별도 추출해서 합침
class PDFExtractor:
    def extract_pages(self, filepath: str, start_page: int, end_page: int) -> str:
        texts = []
        doc = fitz.open(filepath)

        with pdfplumber.open(filepath) as pdf:
            for page_num in range(start_page - 1, end_page):
                if page_num >= len(doc):
                    break

                # PyMuPDF로 일반 텍스트 추출
                texts.append(doc[page_num].get_text())

                # pdfplumber로 표 추출 (표 구조가 있는 경우만)
                if page_num < len(pdf.pages):
                    tables = pdf.pages[page_num].extract_tables()
                    for table in tables:
                        if table:
                            texts.append(f"\n[표]\n{self._format_table(table)}\n")

        doc.close()
        return self._clean("\n".join(texts))

    def _format_table(self, table: list) -> str:
        rows = []
        for row in table:
            cells = [str(cell or "").strip() for cell in row]
            rows.append(" | ".join(cells))
        return "\n".join(rows)

    def _clean(self, text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
