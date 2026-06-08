import os
import json
from pathlib import Path
from dotenv import load_dotenv
from pdf_extractor import PDFExtractor
from chunk_processor import ChunkProcessor
from vector_store import VectorStore

load_dotenv()

PDF_DIR = Path(os.getenv("PDF_DIR", "./pdfs"))
CHUNK_DIR = Path(os.getenv("CHUNK_DIR", "./chunks"))
DB_DIR = Path(os.getenv("DB_DIR", "./chroma_db"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "paraphrase-multilingual-mpnet-base-v2")
API_KEY = os.getenv("ANTHROPIC_API_KEY")

extractor = PDFExtractor()
processor = ChunkProcessor(api_key=API_KEY)
store = VectorStore(db_path=str(DB_DIR), model_name=EMBED_MODEL)

def ingest_file(json_path: Path):
    with open(json_path, encoding="utf-8") as f:
        config = json.load(f)

    source = config["source"]
    pdf_path = PDF_DIR / source
    if not pdf_path.exists():
        print(f"[건너뜀] PDF 없음: {source}")
        return
    
    if store.document_exists(source):
        print(f"[건너뜀] 이미 로드됨: {source}")
        return

    print(f"\n[처리 중] {source}")
    processed = []
    for chunk in config["chunks"]:
        start, end = chunk["pages"]
        text = extractor.extract_pages(str(pdf_path), start, end)
        result = processor.process(
            chunk_id=chunk["id"],
            label=chunk["label"],
            text=text,
            source=source,
            pages=chunk["pages"],
        )
        processed.append(result)
        print(f"  {chunk['id']} {chunk['label']} (p.{start}-{end}) → 요약 완료")

    store.add_processed_chunks(processed, source)
    print(f"  총 {len(processed)}개 청크 저장 완료")

def main():
    import sys
    if len(sys.argv) > 1:
        target = sys.argv[1]
        json_path = CHUNK_DIR / f"{target}.json"
        if not json_path.exists():
            print(f"파일 없음: {json_path}")
            return
        ingest_file(json_path)
    else:
        json_files = list(CHUNK_DIR.glob("*.json"))
        if not json_files:
            print(f"{CHUNK_DIR} 폴더에 json 파일이 없습니다.")
            return
        for json_path in json_files:
            ingest_file(json_path)


if __name__ == "__main__":
    main()