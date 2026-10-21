import pytest

from app.core.errors import IndexIncompatibleError
from app.models.document import Document
from app.services.rag_service import RAGService


def test_index_compatibility_blocks_mismatched_documents(db_session, knowledge_space, fake_embedding, fake_vector_store) -> None:
    document = Document(
        space_id=knowledge_space.id,
        filename="x.md",
        original_filename="x.md",
        file_type="md",
        file_size=1,
        storage_path="x.md",
        status="ready",
        vector_status="indexed",
        embedding_fingerprint="old-fingerprint",
        index_version="old",
    )
    db_session.add(document)
    db_session.commit()

    service = RAGService()
    service.embedding_service = fake_embedding
    service.vector_store = fake_vector_store

    with pytest.raises(IndexIncompatibleError):
        service.ask_question(db_session, knowledge_space.id, "什么是 RAG？", "normal")
