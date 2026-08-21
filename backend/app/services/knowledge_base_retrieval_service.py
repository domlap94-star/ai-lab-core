from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_base_vector_service import KnowledgeBaseVectorService


class KnowledgeBaseRetrievalService:
    """One semantic result contract for lexical and future vector consumers."""
    def __init__(self, db: Session, *, vector_service=None) -> None:
        self.db = db
        self.lexical = KnowledgeBaseService(db)
        self.vector = vector_service or KnowledgeBaseVectorService(db)

    def search(self, query: str, *, limit: int = 20, method: str = "hybrid",
               include_superseded: bool = False) -> list[dict]:
        lexical = self.lexical.search(query, limit)
        if not include_superseded:
            lexical = [row for row in lexical if row["status"] == "current"]
        if method == "lexical": return lexical[:limit]
        vector = self.vector.search(query, limit=limit, include_superseded=include_superseded)
        if method == "vector": return vector[:limit]
        seen: set[tuple[int, int | None, str]] = set(); result = []
        for row in [*lexical, *vector]:
            key = (int(row["knowledge_base_item_id"]), row.get("page"), str(row["excerpt"]))
            if key not in seen:
                seen.add(key); result.append(row)
            if len(result) >= limit: break
        return result
