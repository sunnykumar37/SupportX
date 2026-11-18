import math
import re
from dataclasses import dataclass
from pathlib import Path

from .config import KB_DIR, settings


@dataclass
class KnowledgeChunk:
    source: str
    text: str
    score: float = 0.0


def split_text(text: str, size: int = 80) -> list[str]:
    words = text.split()
    return [" ".join(words[index:index + size]) for index in range(0, len(words), size)]


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class KnowledgeBase:
    def __init__(self, directory: Path = KB_DIR):
        self.directory = directory
        self.chunks: list[KnowledgeChunk] = []
        self._load_documents()
        self._chroma = None
        self._embedding_model = None
        self._build_optional_vector_store()

    def _load_documents(self) -> None:
        for path in sorted(self.directory.glob("*.md")):
            for chunk in split_text(path.read_text(encoding="utf-8")):
                self.chunks.append(KnowledgeChunk(source=path.name, text=chunk))
        if not self.chunks:
            raise RuntimeError(f"No knowledge-base documents found in {self.directory}")

    def _build_optional_vector_store(self) -> None:
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            client = chromadb.EphemeralClient()
            collection = client.get_or_create_collection("supportx-kb")
            embeddings = self._embedding_model.encode([chunk.text for chunk in self.chunks]).tolist()
            collection.add(ids=[str(i) for i in range(len(self.chunks))], documents=[chunk.text for chunk in self.chunks], metadatas=[{"source": chunk.source} for chunk in self.chunks], embeddings=embeddings)
            self._chroma = collection
        except (ImportError, OSError, RuntimeError):
            self._chroma = None

    def retrieve_knowledge(self, query: str, top_k: int = 3) -> list[KnowledgeChunk]:
        if self._chroma is not None and self._embedding_model is not None:
            embedding = self._embedding_model.encode([query]).tolist()
            result = self._chroma.query(query_embeddings=embedding, n_results=min(top_k, len(self.chunks)))
            return [KnowledgeChunk(source=source, text=text, score=1.0 - (distance or 0.0)) for source, text, distance in zip(result["metadatas"][0], result["documents"][0], result["distances"][0])]
        query_tokens = _tokens(query)
        scored = []
        for chunk in self.chunks:
            tokens = _tokens(chunk.text)
            score = len(query_tokens & tokens) / math.sqrt(max(1, len(query_tokens) * len(tokens)))
            scored.append(KnowledgeChunk(chunk.source, chunk.text, score))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]



class TechnicalTools:
    def __init__(self, knowledge_base: KnowledgeBase):
        self.knowledge_base = knowledge_base

    def retrieve_knowledge(self, query: str) -> list[KnowledgeChunk]:
        return self.knowledge_base.retrieve_knowledge(query)

    def run_troubleshooting_check(
        self, message: str, passages: list[KnowledgeChunk]
    ) -> bool:
        return any(
            passage.score >= settings.retrieval_threshold
            for passage in passages
        )
