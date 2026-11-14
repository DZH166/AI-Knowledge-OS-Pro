from __future__ import annotations

from app.models.chat_session import ChatMessage, ChatSession
from app.schemas.chat_schema import ChatResponse, ChatSessionMessageCreate
from app.services.chat_session_service import ChatSessionService, conversational_retrieval_query


def test_short_pronoun_follow_up_keeps_prior_question_for_retrieval() -> None:
    query = conversational_retrieval_query(
        "它的延迟是多少？",
        "Comparable retrieval latency for the streaming API?",
    )

    assert query.startswith("Comparable retrieval latency")
    assert query.endswith("它的延迟是多少？")


def test_standalone_question_is_not_rewritten() -> None:
    question = "Explain the evidence revision lifecycle and active pointers."
    assert conversational_retrieval_query(question, "A previous unrelated question") == question


def test_long_question_is_never_rewritten_even_when_it_contains_a_pronoun() -> None:
    question = "这是一个很长的独立问题，" + "需要说明检索、引用、版本和恢复边界。" * 6
    assert conversational_retrieval_query(question, "previous") == question


def test_follow_up_without_history_returns_the_current_question() -> None:
    assert conversational_retrieval_query("这个怎么配置？", None) == "这个怎么配置？"


def test_session_follow_up_passes_expanded_retrieval_query_but_answers_original(
    db_session, knowledge_space, monkeypatch
) -> None:
    session = ChatSession(space_id=knowledge_space.id, title="新的知识问答", answer_mode="normal")
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    db_session.add(ChatMessage(session_id=session.id, role="user", content="How is the retrieval latency measured?"))
    db_session.commit()

    captured: dict = {}

    def fake_ask_question(*, db, space_id, question, answer_mode, retrieval_query=None):  # noqa: ANN001
        captured.update({
            "space_id": space_id,
            "question": question,
            "answer_mode": answer_mode,
            "retrieval_query": retrieval_query,
        })
        return ChatResponse(answer="Measured with a fixed corpus.", citations=[], related_chunks=[], qa_log_id=1)

    monkeypatch.setattr("app.services.chat_session_service.rag_service.ask_question", fake_ask_question)

    response = ChatSessionService().ask_in_session(
        db_session,
        session.id,
        ChatSessionMessageCreate(question="它的延迟怎么测的？"),
    )

    assert response.answer == "Measured with a fixed corpus."
    assert captured["question"] == "它的延迟怎么测的？"
    assert captured["retrieval_query"].startswith("How is the retrieval latency measured?")
    assert "它的延迟怎么测的？" in captured["retrieval_query"]
    stored = db_session.query(ChatMessage).filter(ChatMessage.session_id == session.id, ChatMessage.role == "user").all()
    assert [message.content for message in stored] == [
        "How is the retrieval latency measured?",
        "它的延迟怎么测的？",
    ]
