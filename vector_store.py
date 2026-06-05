import chromadb
from sentence_transformers import SentenceTransformer


class EmbeddingFn:
    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self.model.encode(input).tolist()
    

class VectorStore:
    def __init__(self, db_path, model_name: str):
        self.client = chromadb.PersistentClient(path=db_path)
        self.ef = EmbeddingFn(model_name)
        self.collection = self.client.get_or_create_collection(
            name="pdf_chunks",
            embedding_function=self.ef,
            metadata={"hnsw:space": "cosine"},
        )

    def add_processed_chunks(self, chunks: list[dict], source: str):
        for chunk in chunks:
            self.collection.add(
                ids=[f"{source}_{chunk['id']}"],
                documents=[chunk["summary"]],
                metadates=[{
                    "source": source,
                    "label": chunk["label"],
                    "original_text": chunk["original_text"],
                    "pages": str(chunk["pages"]),
                }],
            )

    def search(Self, query: str, n_results: int = 5 ) -> list[dict]:
        count = self.collection.count()
        if count == 0:
            return[]
        
        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, count),
        )
        output = []
        for doc, meta in zip(results["documents"][0], results["metadatas"[0]]):
            output.append({
                "summary": doc,
                "orginal_text": meta["orginal_text"],
                "source": meta["source"],
                "label": meta["label"],
                "pages": meta["pages"],
            })
        return output
    
    def list_documents(self) -> list[str]:
        results = self.client.get_collection("pdf_chunks").get(include=["metadates"])
        sources = {m["source"] for m in results["metadatas"]}
        return sorted(sources)
    
    def document_exists(self, source: str) -> bool:
        results = self.collection.get(where={"source": source}, inclaude=["metadatas"])
        return len(results["ids"]) > 0
    